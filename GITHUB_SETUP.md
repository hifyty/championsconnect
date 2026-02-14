# 🐙 Champions Connect — GitHub Setup Guide

Since you already have a GitHub account, this takes about 5 minutes.

---

## Step 1 — Install Git on Mac

Open Terminal (Cmd+Space → "Terminal") and run:
```bash
git --version
```
If not installed, Mac will prompt you. Click **Install** and wait.

Then configure your identity (use your GitHub email):
```bash
git config --global user.name "Your Name"
git config --global user.email "your@github-email.com"
```

---

## Step 2 — Create the Repository on GitHub

1. Go to: https://github.com/new
2. Fill in:
   - **Repository name:** `champions-connect`
   - **Description:** `Champions Connect — Church Management System`
   - **Visibility:** ⬅️ Private (protects member data)
3. Leave all checkboxes unchecked
4. Click **Create repository**
5. Keep the page open — you need the URL in Step 4

---

## Step 3 — Create a GitHub Access Token

GitHub requires a token instead of your account password in Terminal.

1. Go to: https://github.com/settings/tokens/new
2. Name it: `champions-connect`
3. Expiration: `No expiration`
4. Check: ✅ **repo** (full repository access)
5. Click **Generate token**
6. **Copy the token now** — GitHub shows it only once!
   Looks like: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx`
7. Paste it into Notes or a password manager

---

## Step 4 — Push Your Code

In Terminal, go into your project folder:
```bash
cd ~/Downloads/church_app_full
```

Run these commands one at a time:
```bash
git init
git add .
git commit -m "🎉 Launch Champions Connect"
git remote add origin https://github.com/YOUR_USERNAME/champions-connect.git
git branch -M main
git push -u origin main
```

When prompted:
- **Username:** your GitHub username
- **Password:** paste the token from Step 3

Refresh your GitHub page — your code will be there! ✅

---

## Pushing Updates (Every Time You Change the App)

```bash
git add .
git commit -m "describe what changed"
git push
```

Good commit messages:
```
✨ Add new prayer verse
👥 Update member profile
📧 Configure Gmail SMTP
🐛 Fix roster date filter
💰 Record March tithes
```

---

## What's Never Uploaded to GitHub

Your `.gitignore` protects:
- `church.db` — all your member & financial data stays local only
- `.env` — any secret keys
- `__pycache__/` — Python temp files

Member data never leaves your machine.
