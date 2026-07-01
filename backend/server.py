"""Trade Journal Pro — standard-library HTTP server.

Serves a JSON REST API under /api/* and the static single-page frontend for
everything else. No third-party dependencies: run with `python run.py`.
"""
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import db, auth, metrics as M, coach, csv_import

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

MIME = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}

TRADE_FIELDS = [
    "symbol", "instrument", "direction", "quantity", "entry_price", "exit_price",
    "stop_price", "fees", "entry_time", "exit_time", "strategy", "setup",
    "market_condition", "timeframe", "session", "tags", "pre_notes", "post_notes",
    "emotion", "rating", "screenshot",
]


class Api(BaseHTTPRequestHandler):
    server_version = "TradeJournalPro/1.0"

    # ---- low level helpers -------------------------------------------------
    def log_message(self, fmt, *args):
        pass  # keep the console clean; flip on for debugging

    def _send(self, code, body=b"", ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, data, code=200):
        self._send(code, json.dumps(data, default=str).encode())

    def error(self, code, msg):
        self.json({"error": msg}, code)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return {}

    def current_user(self):
        hdr = self.headers.get("Authorization", "")
        token = hdr[7:] if hdr.startswith("Bearer ") else None
        if not token:
            return None
        uid = auth.verify_token(token)
        if not uid:
            return None
        conn = db.get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            return db.row_to_dict(row)
        finally:
            conn.close()

    # ---- routing -----------------------------------------------------------
    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def do_HEAD(self):
        self.route("GET")

    def route(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        self.query = urllib.parse.parse_qs(parsed.query)
        if path.startswith("/api/"):
            try:
                db.ensure_ready()  # idempotent: builds schema on serverless cold start
                self.api(method, path)
            except Exception as e:  # never leak a stack trace to the client
                self.error(500, f"Server error: {e}")
            return
        self.static(path)

    # ---- static file serving ----------------------------------------------
    def static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        rel = path.lstrip("/").replace("..", "")
        full = os.path.join(FRONTEND_DIR, rel)
        if not os.path.isfile(full):
            # SPA fallback -> index.html
            full = os.path.join(FRONTEND_DIR, "index.html")
        try:
            with open(full, "rb") as f:
                body = f.read()
        except OSError:
            self._send(404, b"Not found", "text/plain")
            return
        ext = os.path.splitext(full)[1]
        self._send(200, body, MIME.get(ext, "application/octet-stream"))

    # ---- API dispatch ------------------------------------------------------
    def api(self, method, path):
        routes = [
            ("POST", r"^/api/auth/register$", self.register),
            ("POST", r"^/api/auth/login$", self.login),
            ("GET", r"^/api/me$", self.me),
            ("POST", r"^/api/onboard$", self.onboard),
            ("GET", r"^/api/trades$", self.list_trades),
            ("POST", r"^/api/trades$", self.create_trade),
            ("POST", r"^/api/trades/import$", self.import_trades),
            ("PUT", r"^/api/trades/(\d+)$", self.update_trade),
            ("DELETE", r"^/api/trades/(\d+)$", self.delete_trade),
            ("GET", r"^/api/dashboard$", self.dashboard),
            ("GET", r"^/api/calendar$", self.calendar),
            ("GET", r"^/api/analytics$", self.analytics),
            ("GET", r"^/api/coach$", self.coach_view),
            ("GET", r"^/api/goals$", self.list_goals),
            ("POST", r"^/api/goals$", self.create_goal),
            ("PUT", r"^/api/goals/(\d+)$", self.update_goal),
            ("DELETE", r"^/api/goals/(\d+)$", self.delete_goal),
            ("GET", r"^/api/habits$", self.list_habits),
            ("POST", r"^/api/habits$", self.create_habit),
            ("POST", r"^/api/habits/(\d+)/toggle$", self.toggle_habit),
            ("DELETE", r"^/api/habits/(\d+)$", self.delete_habit),
        ]
        for m, pattern, handler in routes:
            if m != method:
                continue
            match = re.match(pattern, path)
            if match:
                return handler(*match.groups())
        self.error(404, "Unknown endpoint")

    # ---- auth --------------------------------------------------------------
    def register(self):
        data = self.read_json()
        email = (data.get("email") or "").strip().lower()
        name = (data.get("name") or "").strip()
        password = data.get("password") or ""
        if not email or "@" not in email or not name or len(password) < 6:
            return self.error(400, "Valid email, name and a 6+ char password are required.")
        conn = db.get_conn()
        try:
            if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                return self.error(409, "An account with that email already exists.")
            pw_hash, salt = auth.hash_password(password)
            uid = conn.insert(
                "INSERT INTO users (email, name, pw_hash, pw_salt) VALUES (?,?,?,?)",
                (email, name, pw_hash, salt),
            )
            conn.commit()
        finally:
            conn.close()
        self.json({"token": auth.make_token(uid), "user": {"id": uid, "email": email, "name": name, "onboarded": 0}})

    def login(self):
        data = self.read_json()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        conn = db.get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        finally:
            conn.close()
        if not row or not auth.verify_password(password, row["pw_hash"], row["pw_salt"]):
            return self.error(401, "Invalid email or password.")
        u = db.row_to_dict(row)
        self.json({"token": auth.make_token(u["id"]), "user": self._public_user(u)})

    def _public_user(self, u):
        return {k: u[k] for k in ("id", "email", "name", "trader_type", "experience",
                                  "account_size", "base_currency", "onboarded")}

    def me(self):
        u = self.current_user()
        if not u:
            return self.error(401, "Not authenticated")
        self.json({"user": self._public_user(u)})

    def onboard(self):
        u = self.current_user()
        if not u:
            return self.error(401, "Not authenticated")
        d = self.read_json()
        conn = db.get_conn()
        try:
            conn.execute(
                "UPDATE users SET trader_type=?, experience=?, account_size=?, base_currency=?, onboarded=1 WHERE id=?",
                (d.get("trader_type", ""), d.get("experience", ""), float(d.get("account_size") or 0),
                 d.get("base_currency", "USD"), u["id"]),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
        finally:
            conn.close()
        self.json({"user": self._public_user(db.row_to_dict(row))})

    # ---- trades ------------------------------------------------------------
    def _user_or_401(self):
        u = self.current_user()
        if not u:
            self.error(401, "Not authenticated")
            return None
        return u

    def _load_trades(self, uid):
        conn = db.get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE user_id=? ORDER BY entry_time DESC", (uid,)
            ).fetchall()
        finally:
            conn.close()
        return M.enrich_all(db.rows_to_list(rows))

    def list_trades(self):
        u = self._user_or_401()
        if not u:
            return
        trades = self._load_trades(u["id"])
        # optional filters
        q = self.query
        def qval(k):
            return q.get(k, [None])[0]
        for field in ("strategy", "setup", "market_condition", "session", "instrument", "symbol"):
            v = qval(field)
            if v:
                trades = [t for t in trades if (t.get(field) or "").lower() == v.lower()]
        status = qval("status")
        if status == "open":
            trades = [t for t in trades if t["is_open"]]
        elif status == "closed":
            trades = [t for t in trades if not t["is_open"]]
        self.json({"trades": trades})

    def _validate_trade(self, d):
        try:
            symbol = (d.get("symbol") or "").strip().upper()
            qty = float(d.get("quantity"))
            entry = float(d.get("entry_price"))
        except (TypeError, ValueError):
            return None, "symbol, quantity and entry_price are required and numeric."
        if not symbol or qty <= 0 or entry <= 0:
            return None, "symbol, quantity and entry_price must be positive."
        if not (d.get("entry_time") or "").strip():
            return None, "entry_time is required."
        return True, None

    def create_trade(self):
        u = self._user_or_401()
        if not u:
            return
        d = self.read_json()
        ok, err = self._validate_trade(d)
        if not ok:
            return self.error(400, err)
        d["symbol"] = d["symbol"].strip().upper()
        cols = ", ".join(TRADE_FIELDS)
        placeholders = ", ".join("?" for _ in TRADE_FIELDS)
        values = [self._coerce(f, d.get(f)) for f in TRADE_FIELDS]
        conn = db.get_conn()
        try:
            tid = conn.insert(
                f"INSERT INTO trades (user_id, {cols}) VALUES (?, {placeholders})",
                [u["id"], *values],
            )
            conn.commit()
            row = conn.execute("SELECT * FROM trades WHERE id=?", (tid,)).fetchone()
        finally:
            conn.close()
        self.json({"trade": M.enrich_trade(db.row_to_dict(row))}, 201)

    def _coerce(self, field, val):
        if field in ("quantity", "entry_price", "exit_price", "stop_price", "fees"):
            if val in ("", None):
                return None if field in ("exit_price", "stop_price") else 0
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
        if field == "rating":
            try:
                return int(val or 0)
            except (TypeError, ValueError):
                return 0
        return (val or "") if val is not None else ""

    def update_trade(self, tid):
        u = self._user_or_401()
        if not u:
            return
        d = self.read_json()
        conn = db.get_conn()
        try:
            row = conn.execute("SELECT * FROM trades WHERE id=? AND user_id=?", (tid, u["id"])).fetchone()
            if not row:
                return self.error(404, "Trade not found")
            updates = {f: self._coerce(f, d[f]) for f in TRADE_FIELDS if f in d}
            if updates:
                sets = ", ".join(f"{k}=?" for k in updates)
                conn.execute(f"UPDATE trades SET {sets} WHERE id=? AND user_id=?",
                             [*updates.values(), tid, u["id"]])
                conn.commit()
            row = conn.execute("SELECT * FROM trades WHERE id=?", (tid,)).fetchone()
        finally:
            conn.close()
        self.json({"trade": M.enrich_trade(db.row_to_dict(row))})

    def delete_trade(self, tid):
        u = self._user_or_401()
        if not u:
            return
        conn = db.get_conn()
        try:
            conn.execute("DELETE FROM trades WHERE id=? AND user_id=?", (tid, u["id"]))
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})

    def import_trades(self):
        u = self._user_or_401()
        if not u:
            return
        d = self.read_json()
        text = d.get("csv") or ""
        rows, warnings = csv_import.parse_csv(text)
        inserted = 0
        conn = db.get_conn()
        try:
            for rec in rows:
                values = [self._coerce(f, rec.get(f)) for f in TRADE_FIELDS]
                cols = ", ".join(TRADE_FIELDS)
                placeholders = ", ".join("?" for _ in TRADE_FIELDS)
                conn.execute(
                    f"INSERT INTO trades (user_id, {cols}) VALUES (?, {placeholders})",
                    [u["id"], *values],
                )
                inserted += 1
            conn.commit()
        finally:
            conn.close()
        self.json({"inserted": inserted, "warnings": warnings})

    # ---- analytics views ---------------------------------------------------
    def dashboard(self):
        u = self._user_or_401()
        if not u:
            return
        trades = self._load_trades(u["id"])
        start = u.get("account_size") or 0
        m = M.portfolio_metrics(trades, start)
        self.json({
            "metrics": m,
            "equity_curve": M.equity_curve(trades, start),
            "recent": trades[:8],
        })

    def calendar(self):
        u = self._user_or_401()
        if not u:
            return
        trades = self._load_trades(u["id"])
        self.json({"daily": M.daily_pnl(trades)})

    def analytics(self):
        u = self._user_or_401()
        if not u:
            return
        trades = self._load_trades(u["id"])
        self.json({
            "by_strategy": M.breakdown_by(trades, "strategy"),
            "by_setup": M.breakdown_by(trades, "setup"),
            "by_market_condition": M.breakdown_by(trades, "market_condition"),
            "by_session": M.breakdown_by(trades, "session"),
            "by_instrument": M.breakdown_by(trades, "instrument"),
            **M.weekday_session_breakdown(trades),
        })

    def coach_view(self):
        u = self._user_or_401()
        if not u:
            return
        trades = self._load_trades(u["id"])
        period = self.query.get("period", ["all"])[0]
        subset = self._filter_period(trades, period)
        m = M.portfolio_metrics(subset, u.get("account_size") or 0)
        label = {"week": "Last 7 days", "month": "Last 30 days", "all": "All time"}.get(period, "All time")
        report = coach.generate_report(subset, m, label)
        self.json({"report": report, "metrics": m})

    def _filter_period(self, trades, period):
        if period not in ("week", "month"):
            return trades
        from datetime import datetime, timedelta
        days = 7 if period == "week" else 30
        cutoff = datetime.now() - timedelta(days=days)
        out = []
        for t in trades:
            dt = M.parse_dt(t.get("entry_time"))
            if dt and dt >= cutoff:
                out.append(t)
        return out

    # ---- goals -------------------------------------------------------------
    def list_goals(self):
        u = self._user_or_401()
        if not u:
            return
        conn = db.get_conn()
        try:
            rows = conn.execute("SELECT * FROM goals WHERE user_id=? ORDER BY created_at DESC", (u["id"],)).fetchall()
        finally:
            conn.close()
        # auto-update progress for metric-linked goals
        trades = self._load_trades(u["id"])
        m = M.portfolio_metrics(trades, u.get("account_size") or 0)
        goals = db.rows_to_list(rows)
        metric_map = {"win_rate": m["win_rate"], "pnl": m["net_pnl"],
                      "profit_factor": m["profit_factor"] or 0, "expectancy": m["expectancy"]}
        for g in goals:
            if g["metric"] in metric_map:
                g["current"] = metric_map[g["metric"]]
        self.json({"goals": goals})

    def create_goal(self):
        u = self._user_or_401()
        if not u:
            return
        d = self.read_json()
        conn = db.get_conn()
        try:
            gid = conn.insert(
                "INSERT INTO goals (user_id, title, metric, target, deadline) VALUES (?,?,?,?,?)",
                (u["id"], d.get("title", "Untitled goal"), d.get("metric", "custom"),
                 float(d.get("target") or 0), d.get("deadline", "")),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
        finally:
            conn.close()
        self.json({"goal": db.row_to_dict(row)}, 201)

    def update_goal(self, gid):
        u = self._user_or_401()
        if not u:
            return
        d = self.read_json()
        allowed = ("title", "metric", "target", "current", "deadline", "status")
        updates = {k: d[k] for k in allowed if k in d}
        if not updates:
            return self.error(400, "Nothing to update")
        conn = db.get_conn()
        try:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE goals SET {sets} WHERE id=? AND user_id=?",
                         [*updates.values(), gid, u["id"]])
            conn.commit()
            row = conn.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
        finally:
            conn.close()
        self.json({"goal": db.row_to_dict(row)})

    def delete_goal(self, gid):
        u = self._user_or_401()
        if not u:
            return
        conn = db.get_conn()
        try:
            conn.execute("DELETE FROM goals WHERE id=? AND user_id=?", (gid, u["id"]))
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})

    # ---- habits ------------------------------------------------------------
    def list_habits(self):
        u = self._user_or_401()
        if not u:
            return
        conn = db.get_conn()
        try:
            rows = conn.execute("SELECT * FROM habits WHERE user_id=? ORDER BY created_at", (u["id"],)).fetchall()
        finally:
            conn.close()
        habits = db.rows_to_list(rows)
        for h in habits:
            h["log"] = json.loads(h["log"] or "{}")
            h["streak"] = self._streak(h["log"])
        self.json({"habits": habits})

    def _streak(self, log):
        from datetime import date, timedelta
        streak, day = 0, date.today()
        while log.get(day.isoformat()):
            streak += 1
            day -= timedelta(days=1)
        return streak

    def create_habit(self):
        u = self._user_or_401()
        if not u:
            return
        d = self.read_json()
        conn = db.get_conn()
        try:
            hid = conn.insert("INSERT INTO habits (user_id, name) VALUES (?,?)",
                              (u["id"], d.get("name", "New habit")))
            conn.commit()
            row = conn.execute("SELECT * FROM habits WHERE id=?", (hid,)).fetchone()
        finally:
            conn.close()
        h = db.row_to_dict(row)
        h["log"] = {}
        h["streak"] = 0
        self.json({"habit": h}, 201)

    def toggle_habit(self, hid):
        u = self._user_or_401()
        if not u:
            return
        d = self.read_json()
        day = d.get("date")
        from datetime import date as _date
        if not day:
            day = _date.today().isoformat()
        conn = db.get_conn()
        try:
            row = conn.execute("SELECT * FROM habits WHERE id=? AND user_id=?", (hid, u["id"])).fetchone()
            if not row:
                return self.error(404, "Habit not found")
            log = json.loads(row["log"] or "{}")
            log[day] = not log.get(day, False)
            conn.execute("UPDATE habits SET log=? WHERE id=?", (json.dumps(log), hid))
            conn.commit()
        finally:
            conn.close()
        self.json({"log": log, "streak": self._streak(log)})

    def delete_habit(self, hid):
        u = self._user_or_401()
        if not u:
            return
        conn = db.get_conn()
        try:
            conn.execute("DELETE FROM habits WHERE id=? AND user_id=?", (hid, u["id"]))
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})


def serve(host="127.0.0.1", port=8000):
    db.init_db()
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    httpd = ThreadingHTTPServer((host, port), Api)
    print(f"\n  Trade Journal Pro running at  http://{host}:{port}\n  Press Ctrl+C to stop.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
        httpd.shutdown()
