"""Mini Core Banking System - Flask + SQLite.

Key ideas worth explaining in an interview:
  * Money stored as integer paise (no float errors)
  * Atomic UPDATE ... WHERE balance >= amount  -> no overdraw under concurrency
  * BEGIN IMMEDIATE transactions -> transfers are all-or-nothing (ACID)
  * Parameterised SQL (no SQL injection), hashed passwords, CSRF tokens
  * Role based access (customer / manager) and a simple fraud rule
"""
import os
import random
import secrets
import sqlite3
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from functools import wraps

import click
from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

MAX_AMOUNT_PAISE = 10_000_000 * 100      # Rs 1 crore per operation
FLAG_LIMIT_PAISE = 50_000 * 100          # flag anything >= Rs 50,000
MAX_FAILED_LOGINS = 5


class BankError(Exception):
    """A business-rule failure that is safe to show to the user."""


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        db = sqlite3.connect(current_app_db(), isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        g.db = db
    return g.db


def current_app_db():
    from flask import current_app
    return current_app.config["DATABASE"]


@contextmanager
def atomic(db):
    """All statements inside succeed together or not at all."""
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise


def to_paise(raw):
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"))
        if not amount.is_finite():          # rejects NaN and Infinity
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        raise BankError("Enter a valid amount, for example 250.00")
    paise = int(amount * 100)
    if paise <= 0 or paise > MAX_AMOUNT_PAISE:
        raise BankError("Amount must be above 0 and at most Rs 1,00,00,000.")
    return paise


def move_money(db, account_id, delta, kind, counterparty=None):
    """Add delta paise to an account and write the ledger row.

    The WHERE clause makes the balance check and the update a single atomic
    statement, so two simultaneous withdrawals can never overdraw.
    """
    cur = db.execute(
        "UPDATE accounts SET balance = balance + ? "
        "WHERE id = ? AND status = 'active' AND balance + ? >= 0",
        (delta, account_id, delta))
    if cur.rowcount != 1:
        raise BankError("Insufficient balance, or the account is frozen.")
    balance = db.execute("SELECT balance FROM accounts WHERE id = ?",
                         (account_id,)).fetchone()[0]
    flagged = int(abs(delta) >= FLAG_LIMIT_PAISE)
    db.execute(
        "INSERT INTO transactions (account_id, kind, amount, balance_after,"
        " counterparty, flagged) VALUES (?,?,?,?,?,?)",
        (account_id, kind, abs(delta), balance, counterparty, flagged))


def new_account_no(db):
    while True:
        number = "".join(random.choices("0123456789", k=10))
        if not db.execute("SELECT 1 FROM accounts WHERE account_no = ?",
                          (number,)).fetchone():
            return number


# ---------- app factory ----------
def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "bank.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)

    with sqlite3.connect(app.config["DATABASE"]) as init:
        with open(os.path.join(app.root_path, "schema.sql")) as f:
            init.executescript(f.read())

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    # ----- CSRF + current user -----
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.filters["rupees"] = lambda p: f"Rs {p / 100:,.2f}"

    @app.before_request
    def load_user_and_check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Invalid or missing CSRF token.")
        g.user = None
        if "user_id" in session:
            g.user = get_db().execute(
                "SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    def login_required(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if g.user is None:
                return redirect(url_for("login"))
            return view(*a, **kw)
        return wrapped

    def manager_required(view):
        @wraps(view)
        @login_required
        def wrapped(*a, **kw):
            if g.user["role"] != "manager":
                abort(403)
            return view(*a, **kw)
        return wrapped

    def my_account():
        return get_db().execute("SELECT * FROM accounts WHERE user_id = ?",
                                (g.user["id"],)).fetchone()

    # ----- auth -----
    @app.route("/")
    def index():
        return redirect(url_for("dashboard" if g.user else "login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            name = request.form.get("full_name", "").strip()
            password = request.form.get("password", "")
            if not (3 <= len(username) <= 30 and username.isalnum()):
                flash("Username must be 3-30 letters or digits.")
            elif not name:
                flash("Enter your full name.")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.")
            else:
                db = get_db()
                try:
                    with atomic(db):
                        cur = db.execute(
                            "INSERT INTO users (username, full_name, password_hash)"
                            " VALUES (?,?,?)",
                            (username, name, generate_password_hash(password)))
                        db.execute(
                            "INSERT INTO accounts (user_id, account_no) VALUES (?,?)",
                            (cur.lastrowid, new_account_no(db)))
                except sqlite3.IntegrityError:
                    flash("That username is already taken.")
                else:
                    flash("Account created. Please log in.")
                    return redirect(url_for("login"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            db = get_db()
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            user = db.execute("SELECT * FROM users WHERE username = ?",
                              (username,)).fetchone()
            if user and user["failed_attempts"] >= MAX_FAILED_LOGINS:
                flash("Account locked after too many attempts. Contact the manager.")
            elif user and check_password_hash(user["password_hash"], password):
                db.execute("UPDATE users SET failed_attempts = 0 WHERE id = ?",
                           (user["id"],))
                session.clear()
                session["user_id"] = user["id"]
                return redirect(url_for("dashboard"))
            else:
                if user:
                    db.execute("UPDATE users SET failed_attempts = failed_attempts + 1"
                               " WHERE id = ?", (user["id"],))
                flash("Wrong username or password.")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ----- customer -----
    @app.route("/dashboard")
    @login_required
    def dashboard():
        if g.user["role"] == "manager":
            return redirect(url_for("manager"))
        acc = my_account()
        txns = get_db().execute(
            "SELECT * FROM transactions WHERE account_id = ? ORDER BY id DESC LIMIT 10",
            (acc["id"],)).fetchall()
        return render_template("dashboard.html", acc=acc, txns=txns)

    @app.route("/statement")
    @login_required
    def statement():
        acc = my_account()
        txns = get_db().execute(
            "SELECT * FROM transactions WHERE account_id = ? ORDER BY id DESC LIMIT 200",
            (acc["id"],)).fetchall()
        return render_template("statement.html", acc=acc, txns=txns)

    def run_operation(fn):
        try:
            fn()
        except BankError as err:
            flash(str(err))
        return redirect(url_for("dashboard"))

    @app.route("/deposit", methods=["POST"])
    @login_required
    def deposit():
        def op():
            paise = to_paise(request.form.get("amount"))
            db = get_db()
            with atomic(db):
                move_money(db, my_account()["id"], paise, "deposit")
            flash("Deposit successful.")
        return run_operation(op)

    @app.route("/withdraw", methods=["POST"])
    @login_required
    def withdraw():
        def op():
            paise = to_paise(request.form.get("amount"))
            db = get_db()
            with atomic(db):
                move_money(db, my_account()["id"], -paise, "withdraw")
            flash("Withdrawal successful.")
        return run_operation(op)

    @app.route("/transfer", methods=["POST"])
    @login_required
    def transfer():
        def op():
            paise = to_paise(request.form.get("amount"))
            target_no = request.form.get("to_account", "").strip()
            db = get_db()
            me = my_account()
            target = db.execute("SELECT * FROM accounts WHERE account_no = ?",
                                (target_no,)).fetchone()
            if target is None:
                raise BankError("Recipient account not found.")
            if target["id"] == me["id"]:
                raise BankError("You cannot transfer to your own account.")
            with atomic(db):            # debit + credit succeed or fail together
                move_money(db, me["id"], -paise, "transfer_out", target["account_no"])
                move_money(db, target["id"], paise, "transfer_in", me["account_no"])
            flash("Transfer successful.")
        return run_operation(op)

    # ----- manager -----
    @app.route("/manager")
    @manager_required
    def manager():
        db = get_db()
        accounts = db.execute(
            "SELECT a.*, u.username, u.full_name, u.failed_attempts FROM accounts a"
            " JOIN users u ON u.id = a.user_id ORDER BY a.id").fetchall()
        flagged = db.execute(
            "SELECT t.*, a.account_no FROM transactions t JOIN accounts a"
            " ON a.id = t.account_id WHERE t.flagged = 1 ORDER BY t.id DESC LIMIT 50"
        ).fetchall()
        return render_template("manager.html", accounts=accounts, flagged=flagged)

    @app.route("/manager/toggle/<int:account_id>", methods=["POST"])
    @manager_required
    def toggle(account_id):
        db = get_db()
        acc = db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if acc is None:
            abort(404)
        new_status = "frozen" if acc["status"] == "active" else "active"
        db.execute("UPDATE accounts SET status = ? WHERE id = ?", (new_status, account_id))
        if new_status == "active":      # unfreezing also clears login lock
            db.execute("UPDATE users SET failed_attempts = 0 WHERE id = ?",
                       (acc["user_id"],))
        flash(f"Account {acc['account_no']} is now {new_status}.")
        return redirect(url_for("manager"))

    # ----- CLI -----
    @app.cli.command("create-manager")
    @click.argument("username")
    @click.password_option()
    def create_manager(username, password):
        """Create a bank manager: flask --app app create-manager admin"""
        get_db().execute(
            "INSERT INTO users (username, full_name, password_hash, role)"
            " VALUES (?,?,?, 'manager')",
            (username.lower(), "Branch Manager", generate_password_hash(password)))
        click.echo("Manager created.")

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
