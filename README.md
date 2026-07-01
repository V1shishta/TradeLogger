# 📈 Trade Journal Pro

**An AI-first trading journal and performance-analytics platform that turns your trade history into a personal trading coach.**

Most traders lose not because they lack strategies, but because they repeat the same behavioral mistakes — revenge trading, overtrading, cutting winners short, chasing FOMO entries. Trade Journal Pro logs every trade, computes the metrics that actually matter, and — crucially — **runs an explainable behavioral-analysis engine that names your recurring leaks and tells you exactly what to fix.**

> Built as an end-to-end product & engineering portfolio piece. Zero external dependencies — the entire backend runs on the Python standard library.

---

## ✨ Highlights

| | |
|---|---|
| ⚡ **10-second trade logging** | Fast entry form with strategy, setup, session, market condition, emotion & execution rating |
| 📥 **Broker CSV import** | Auto-detects columns from TD/thinkorswim, Interactive Brokers, Robinhood, Webull & generic exports |
| 📊 **Performance dashboard** | Net P&L, win rate, profit factor, expectancy, average R, max drawdown, streaks — with an interactive equity curve |
| 🧠 **AI Coach (explainable)** | Detects revenge trading, overtrading, cutting winners, FOMO/chasing, and position-sizing errors — each with the exact evidence that triggered it |
| 📅 **Trading calendar** | Daily P&L heatmap with monthly roll-ups |
| 🔬 **Strategy comparison** | Break performance down by strategy, setup, market condition, session, instrument & day of week |
| 🎯 **Goals & habits** | Metric-linked goals with auto-progress and a daily discipline habit tracker with streaks |
| 🔐 **Secure auth** | PBKDF2-hashed passwords and stateless HMAC-signed session tokens |

---

## 🚀 Quick start

**Requirements:** Python 3.10+ (no `pip install` needed).

```bash
# 1. Load the demo account with a realistic 140+ trade history
python run.py --seed --reset

# 2. Start the app
python run.py

# 3. Open http://127.0.0.1:8000  and click “Explore the demo account”
#    demo@tradejournal.pro  /  demo1234
```

Custom port: `python run.py --port 9000`

Or just start fresh and create your own account — the landing page walks you through a 20-second onboarding.

---

## ☁️ Deploy to Vercel (free)

The app runs locally on **SQLite** with zero dependencies, and automatically switches to **Postgres** in production when a database URL is present in the environment — same codebase, no config toggles. On Vercel it runs as a serverless Python function (the request handler is already a `BaseHTTPRequestHandler`, which Vercel's Python runtime calls directly), with the SPA served from the CDN.

**Steps (all in the Vercel dashboard — no CLI needed):**

1. **Import the repo** → [vercel.com/new](https://vercel.com/new) → *Add New… → Project* → import `V1shishta/TradeLogger`. Framework preset: **Other**. Deploy.
2. **Add a database** → project **Storage** tab → *Create Database → Postgres* → connect it to the project. This injects `POSTGRES_URL` (and friends) as environment variables automatically.
3. **Redeploy** (Deployments → ⋯ → Redeploy) so the function picks up the new env vars.
4. **Open the URL.** On the first request the app creates its schema and seeds the demo account automatically — log in with `demo@tradejournal.pro` / `demo1234`.

**Relevant files:** [`vercel.json`](vercel.json) (routing), [`api/index.py`](api/index.py) (serverless entry), [`requirements.txt`](requirements.txt) (`psycopg`), and the dual-backend logic in [`backend/db.py`](backend/db.py).

**Env vars**

| Var | Purpose |
|---|---|
| `POSTGRES_URL` / `POSTGRES_URL_NON_POOLING` / `DATABASE_URL` | Provided by Vercel Postgres; presence switches the app to Postgres |
| `AUTO_SEED` | `1` (default) auto-seeds the demo account on an empty DB; set `0` to skip |
| `TJP_SECRET` | Fixed token-signing secret — **set this in production** so sessions survive redeploys |

> Note: Vercel's filesystem is ephemeral, so SQLite is not viable there — the managed Postgres above is what makes the deployment persistent and free.

---

## 🏗️ Architecture

```
trade-journal-pro/
├── run.py                  # local entry point / CLI (serve · --seed · --reset)
├── api/index.py            # Vercel serverless entry (re-exports the request handler)
├── vercel.json             # Vercel routing (static SPA + /api function)
├── requirements.txt        # psycopg — only needed for the Postgres deployment
├── backend/                # standard-library only (psycopg used only in prod)
│   ├── server.py           #   HTTP server, routing, static serving, REST API
│   ├── db.py               #   dual SQLite/Postgres layer + schema + helpers
│   ├── auth.py             #   PBKDF2 hashing + HMAC-signed tokens
│   ├── metrics.py          #   P&L, win rate, expectancy, R, drawdown, equity curve, breakdowns
│   ├── coach.py            #   explainable behavioral-analysis engine + report generator
│   ├── csv_import.py       #   broker-agnostic CSV parser
│   └── seed.py             #   deterministic demo-data generator
├── frontend/               # vanilla SPA — no build step
│   ├── index.html
│   ├── css/styles.css      #   dark design system, fully responsive
│   └── js/                 #   api.js · ui.js · charts.js · app.js
├── sample_data/            # sample_trades.csv for the import demo
└── docs/CASE_STUDY.md      # full product case study
```

**Design decisions**

- **Stdlib-only backend.** No framework, no dependency install, runs anywhere Python does — ideal for a portfolio reviewer who wants to run it in one command. `http.server` + `sqlite3` + `hashlib`/`hmac` cover everything.
- **Explainable "AI" over a black box.** The coach is a transparent, deterministic rules engine. Every insight ships with the concrete numbers that triggered it, satisfying the product requirement that recommendations be auditable and grounded in the user's own data. The same signal features (inter-trade timing, size deltas after losses, hold-time asymmetry, clustering) form a clean upgrade path to an ML model later.
- **No build step on the frontend.** A single-page vanilla-JS app keeps the repo instantly runnable; Chart.js loads from CDN and degrades gracefully offline.

---

## 🔌 API reference

All endpoints are JSON under `/api`. Authenticated routes expect `Authorization: Bearer <token>`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/auth/register` | Create account → returns token |
| `POST` | `/api/auth/login` | Log in → returns token |
| `GET`  | `/api/me` | Current user profile |
| `POST` | `/api/onboard` | Save trader type, experience, account size |
| `GET`  | `/api/trades` | List trades (filters: `status`, `strategy`, `symbol`, …) |
| `POST` | `/api/trades` | Create a trade |
| `PUT`  | `/api/trades/{id}` | Update a trade |
| `DELETE` | `/api/trades/{id}` | Delete a trade |
| `POST` | `/api/trades/import` | Import a CSV body |
| `GET`  | `/api/dashboard` | Metrics + equity curve + recent trades |
| `GET`  | `/api/calendar` | Daily P&L map |
| `GET`  | `/api/analytics` | Breakdowns by strategy/setup/condition/session/instrument/weekday |
| `GET`  | `/api/coach?period=week\|month\|all` | Behavioral insights + coaching report |
| `GET/POST/PUT/DELETE` | `/api/goals` | Goal CRUD (metric-linked auto-progress) |
| `GET/POST/DELETE` | `/api/habits`, `POST /api/habits/{id}/toggle` | Habit tracker |

---

## 🧮 How the metrics are computed

Every figure is derived directly from your logged trades so nothing is a black box:

- **P&L** — `(exit − entry) × qty − fees` for longs (inverted for shorts)
- **R-multiple** — `net P&L ÷ (|entry − stop| × qty)` when a stop is recorded
- **Expectancy** — average P&L per closed trade
- **Profit factor** — gross profit ÷ gross loss
- **Max drawdown** — largest peak-to-trough dip on the cumulative equity curve

See [`docs/CASE_STUDY.md`](docs/CASE_STUDY.md) for the full product story: user research, personas, prioritization, wireframes, architecture, KPIs, and roadmap.

---

## 🔒 Security & privacy notes

- Passwords are never stored in plaintext (PBKDF2-HMAC-SHA256, per-user salt, 240k rounds).
- Session tokens are HMAC-signed and expire; there is no server-side session store to leak.
- All trade data stays in a local SQLite file — nothing is sent to any third party.
- For a production deployment: set a fixed `TJP_SECRET` env var, run behind HTTPS, and move to a hardened WSGI/ASGI server.

## 🗺️ Roadmap (post-MVP)

Broker & TradingView API sync · ML-scored behavioral models · MAE/MFE trade replay · shareable public track records · mobile app · multi-account portfolios. Details in the case study.

---

*Built with Python's standard library and vanilla JavaScript. No frameworks were harmed in the making of this journal.*
