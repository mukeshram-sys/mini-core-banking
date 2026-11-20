CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    full_name       TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','manager')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Money is stored in paise (integer) to avoid floating point errors.
CREATE TABLE IF NOT EXISTS accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL UNIQUE REFERENCES users(id),
    account_no TEXT NOT NULL UNIQUE,
    balance    INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    status     TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','frozen'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    kind          TEXT NOT NULL CHECK (kind IN ('deposit','withdraw','transfer_in','transfer_out')),
    amount        INTEGER NOT NULL CHECK (amount > 0),
    balance_after INTEGER NOT NULL,
    counterparty  TEXT,
    flagged       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account_id, id DESC);
