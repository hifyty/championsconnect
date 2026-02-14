# 📧 Gmail Setup for Mass Email — Step by Step

Champions Connect uses Gmail's SMTP server to send emails to your congregation.
Follow these steps exactly — it takes about 5 minutes.

---

## Part 1 — Enable 2-Factor Authentication on Gmail

Gmail requires 2FA before you can create an App Password.

1. Go to: https://myaccount.google.com/security
2. Under "How you sign in to Google", click **2-Step Verification**
3. Follow the prompts to turn it on (use your phone number or authenticator app)
4. Once enabled, continue to Part 2

---

## Part 2 — Create a Gmail App Password

> ⚠️ You CANNOT use your regular Gmail password — Google blocks this.
> You must create a special 16-character "App Password" instead.

1. Go to: https://myaccount.google.com/apppasswords
   *(You must be signed into the Gmail account you want to send from)*

2. Under "App name", type: `Champions Connect`

3. Click **Create**

4. Google will show you a 16-character password like: `abcd efgh ijkl mnop`
   **Copy this immediately** — Google will only show it once!

5. Save it somewhere safe (Notes app, password manager, etc.)

---

## Part 3 — Enter Settings in Champions Connect

1. Start your app: `python3 app.py`
2. Open: http://localhost:5000
3. Log in as admin
4. Click **Mass Email** in the sidebar
5. Click the **Configure** button under Email Settings
6. Fill in:
   - **Sender Name:** Champions Connect (or your church name)
   - **SMTP Host:** `smtp.gmail.com` (already set)
   - **Port:** `587` (already set)
   - **Email:** your full Gmail address (e.g. `championschoir@gmail.com`)
   - **App Password:** paste the 16-character password from Part 2
7. Click **Save Settings**

You should see "✅ Configured" appear.

---

## Part 4 — Send a Test Email

1. Go to Mass Email page
2. Set recipients to **Active members on mailing list**
3. Subject: `Test — Champions Connect Email`
4. Body: `This is a test email from our new church management system!`
5. Click **Send Email Blast**
6. Check that the emails arrive in inboxes ✅

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Authentication failed" | Double-check you used the App Password, not your Gmail password |
| "Less secure app" error | App Passwords bypass this — make sure 2FA is enabled |
| Emails go to spam | Ask recipients to mark as "Not Spam" once; it improves over time |
| "Connection refused" | Check your internet connection; port 587 must be open |
| App Password page not showing | Make sure 2FA is fully enabled first |

---

## Recommended Gmail Setup

Create a **dedicated church Gmail account** rather than using a personal one:
- Go to gmail.com and create `championschoir.edmonton@gmail.com` (or similar)
- This keeps church emails separate from personal ones
- Looks more professional to recipients
- Easier to share access with other admins

---

## What the Emails Look Like

Recipients will see a branded HTML email with:
- Champions Connect header in navy and gold
- Your subject and message body
- "Champions Choir Edmonton" footer
- Sent from your configured Gmail address

Members can reply directly to your Gmail if needed.
