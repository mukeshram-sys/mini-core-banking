# GitHub setup, step by step

## 1. One-time setup on your computer
1. Install Git from https://git-scm.com and Python 3.10+ from https://python.org
2. Tell Git who you are:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
3. Create a free account at https://github.com. Use a professional username,
   because recruiters will see it.

## 2. Create the repository on GitHub
1. Click **New repository**.
2. Name it `mini-core-banking`, set it to **Public**.
3. Do NOT tick "Add a README" or ".gitignore" (the project already has them).
4. Click **Create repository**.

## 3. Push the project
Open a terminal inside the project folder:
```bash
git init
git add .
git commit -m "Initial commit: mini core banking system"
git branch -M main
git remote add origin https://github.com/<your-username>/mini-core-banking.git
git push -u origin main
```
GitHub asks you to sign in. If it asks for a password, use a **Personal Access Token**
(Settings > Developer settings > Personal access tokens), not your account password.

## 4. Build a visible commit history
Recruiters read your history. After the first push, work in small steps:
```bash
git checkout -b feature/fraud-detection
# ...make changes...
git add .
git commit -m "Add isolation forest fraud scoring"
git push -u origin feature/fraud-detection
```
Then open a **Pull Request** on GitHub and merge it. Use messages like
`Add statement page` or `Fix NaN amount validation`, not `update` or `final`.

## 5. Make the repo look professional
- Edit the repo's **About** box: one-line description and topics (`flask`, `banking`, `python`, `sqlite`).
- Add screenshots to the README (create a `docs/screenshots` folder).
- Keep the green **tests** badge: the workflow in `.github/workflows` runs on every push.
- Pin the repo on your profile (Profile > Customize your pins).
- Never commit passwords, `.env` files or the database. `.gitignore` already blocks them.

## 6. Optional: free deployment
Deploy on https://render.com: connect the GitHub repo, set the build command to
`pip install -r requirements.txt gunicorn`, the start command to
`gunicorn "app:create_app()"`, and add a `SECRET_KEY` environment variable.
Note: SQLite data is wiped on free hosting restarts, so use PostgreSQL for a permanent demo.
