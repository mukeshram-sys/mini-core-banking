import sqlite3
try:
    import pytest
except ImportError:
    pytest = None
from app import create_app


@(pytest.fixture if pytest else (lambda f: f))
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True,
                       "SECRET_KEY": "test"})


def post(client, url, **data):
    with client.session_transaction() as s:
        data["csrf"] = s.setdefault("csrf", "tok")
    return client.post(url, data=data, follow_redirects=True)


def signup(app, username):
    c = app.test_client()
    post(c, "/register", username=username, full_name=username.title(),
         password="password123")
    post(c, "/login", username=username, password="password123")
    return c


def row(app, sql, *args):
    con = sqlite3.connect(app.config["DATABASE"])
    try:
        return con.execute(sql, args).fetchone()
    finally:
        con.close()


def balance(app, username):
    return row(app, "SELECT a.balance FROM accounts a JOIN users u ON u.id=a.user_id"
                    " WHERE u.username=?", username)[0]


def acc_no(app, username):
    return row(app, "SELECT a.account_no FROM accounts a JOIN users u ON u.id=a.user_id"
                    " WHERE u.username=?", username)[0]


def test_deposit_and_withdraw(app):
    c = signup(app, "asha")
    post(c, "/deposit", amount="1000.50")
    assert balance(app, "asha") == 100050
    post(c, "/withdraw", amount="500")
    assert balance(app, "asha") == 50050


def test_cannot_overdraw(app):
    c = signup(app, "asha")
    post(c, "/deposit", amount="100")
    r = post(c, "/withdraw", amount="500")
    assert b"Insufficient balance" in r.data
    assert balance(app, "asha") == 10000


def test_invalid_amounts_rejected(app):
    c = signup(app, "asha")
    for bad in ["-5", "0", "abc", "NaN", "99999999999"]:
        post(c, "/deposit", amount=bad)
    assert balance(app, "asha") == 0


def test_transfer_moves_money(app):
    a, b = signup(app, "asha"), signup(app, "ravi")
    post(a, "/deposit", amount="1000")
    post(a, "/transfer", to_account=acc_no(app, "ravi"), amount="300")
    assert balance(app, "asha") == 70000
    assert balance(app, "ravi") == 30000


def test_transfer_is_atomic_when_receiver_frozen(app):
    a, _ = signup(app, "asha"), signup(app, "ravi")
    post(a, "/deposit", amount="1000")
    con = sqlite3.connect(app.config["DATABASE"])
    con.execute("UPDATE accounts SET status='frozen' WHERE account_no=?",
                (acc_no(app, "ravi"),))
    con.commit(); con.close()
    post(a, "/transfer", to_account=acc_no(app, "ravi"), amount="300")
    assert balance(app, "asha") == 100000      # debit was rolled back
    assert balance(app, "ravi") == 0


def test_large_transaction_is_flagged(app):
    c = signup(app, "asha")
    post(c, "/deposit", amount="60000")
    assert row(app, "SELECT flagged FROM transactions")[0] == 1


def test_csrf_required(app):
    c = signup(app, "asha")
    assert c.post("/deposit", data={"amount": "100"}).status_code == 400


def test_weak_password_rejected(app):
    c = app.test_client()
    post(c, "/register", username="asha", full_name="Asha", password="short")
    assert row(app, "SELECT COUNT(*) FROM users")[0] == 0


def test_account_locks_after_failed_logins(app):
    signup(app, "asha")
    c = app.test_client()
    for _ in range(5):
        post(c, "/login", username="asha", password="wrong")
    r = post(c, "/login", username="asha", password="password123")
    assert b"locked" in r.data


def test_customer_cannot_open_manager_page(app):
    c = signup(app, "asha")
    assert c.get("/manager").status_code == 403
