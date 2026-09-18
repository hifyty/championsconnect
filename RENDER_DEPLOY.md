# 🚀 Deploying Champions Connect to Render (with free Postgres)

This app is ready to deploy — it already has a `Procfile` (`web: gunicorn app:app`)
and runs on Postgres automatically once `DATABASE_URL` is set. Do these in order.

---

## Step 1 — Create a free Postgres database (Neon)

Render's own free Postgres tier expires and deletes your data after ~30-44
days, which isn't safe for real giving/member data. [Neon](https://neon.com)'s
free tier has no expiration, so use that instead.

1. Go to [neon.com](https://neon.com) and sign up (you do this — not me).
2. Create a new project (any name, e.g. `champions-connect`).
3. On the project dashboard, copy the **connection string** — it looks like:
   `postgres://user:password@ep-xxxx.region.aws.neon.tech/dbname?sslmode=require`
4. Keep this tab open — you'll paste it into Render in Step 3.

---

## Step 2 — Push this code to GitHub

If you haven't already:
```bash
cd championsconnect_clone
git push origin main
```

---

## Step 3 — Create the Render web service

1. Go to [render.com](https://render.com) and sign up / log in (again, you do
   this step).
2. **New +** → **Web Service** → connect your `championsconnect` GitHub repo.
3. Render should auto-detect the `Procfile`. If asked:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app` (from the Procfile)
4. Under **Environment**, add these variables:
   | Key | Value |
   |---|---|
   | `SECRET_KEY` | generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
   | `DATABASE_URL` | the Neon connection string from Step 1 |
   | `STRIPE_SECRET_KEY` | (once you have a Stripe account — optional for now) |
   | `STRIPE_WEBHOOK_SECRET` | (see Step 5 below — optional for now) |
5. Click **Create Web Service**. First deploy takes a few minutes.

---

## Step 4 — Smoke test

Once deployed, visit your Render URL and check, in order:
1. `/login` loads and you can log in with `admin@championschoir.ca` / `admin123`
   **— change this password immediately after confirming login works.**
2. The dashboard loads with no errors.
3. Add a test member or donation, then check it actually shows up (confirms
   Postgres is really being written to, not just read).
4. If something looks wrong, check Render's **Logs** tab for the actual error
   — that's the fastest way to spot a leftover SQLite-only query.

This Postgres path was thoroughly tested against SQLite and reviewed
carefully for Postgres compatibility, but **could not be execution-tested
against a real Postgres server** in the environment this was built in — this
smoke test is that missing verification step.

---

## Step 5 — Point Stripe's webhook at your live URL (once you have Stripe keys)

1. In the Stripe dashboard: **Developers → Webhooks → Add endpoint**
2. URL: `https://your-app.onrender.com/give/webhook`
3. Events to send: `checkout.session.completed`, `invoice.paid`
4. Copy the **Signing secret** shown after creating it → set as
   `STRIPE_WEBHOOK_SECRET` in Render's environment, then redeploy.

---

## Notes

- Render's free web service spins down after inactivity, so the first
  request after a quiet period will be slow (~30-60s cold start). That's
  normal, not a bug.
- Neon's free tier scales compute to zero after 5 minutes idle and wakes up
  automatically on the next query — same idea, may add a brief delay.
- Local development still works exactly as before with no setup: just don't
  set `DATABASE_URL` locally and it uses `church.db` (SQLite) automatically.
