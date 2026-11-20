# Questions to prepare (answers are in app.py)

1. **Why store money as integers?** Float rounding errors; paise as integers are exact.
2. **Two people withdraw at the same instant. What stops an overdraw?** The conditional
   `UPDATE ... WHERE balance + ? >= 0` is atomic, and the schema has `CHECK (balance >= 0)`.
3. **What if the credit fails after the debit in a transfer?** Both run inside one
   `BEGIN IMMEDIATE` transaction, so the debit is rolled back. See `test_transfer_is_atomic_when_receiver_frozen`.
4. **How do you stop SQL injection?** Every query uses `?` placeholders, never string formatting.
5. **How are passwords stored?** Salted hashes via Werkzeug (`generate_password_hash`), never plain text.
6. **What is CSRF and how did you stop it?** A forged request from another site. Every POST needs a random session token.
7. **ACID, in your own project's words.** Atomicity: transfer. Consistency: CHECK constraints.
   Isolation: IMMEDIATE transactions. Durability: SQLite commits to disk.
8. **What would you change for a real bank?** PostgreSQL, HTTPS, OTP or 2FA, audit logging,
   rate limiting, encryption at rest, and a double-entry ledger.
9. **Why SQLite?** Zero setup for a demo; the SQL is standard, so moving to PostgreSQL or MySQL is straightforward.
