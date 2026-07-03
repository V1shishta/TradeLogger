"""Demo data generator.

Creates a demo account with a realistic trade history that deliberately contains
a few behavioral leaks (revenge trades, a couple of overtrading days, inconsistent
sizing) so the AI Coach has something meaningful to surface. Deterministic via a
fixed random seed so the demo looks the same every time.
"""
import json
import random
from datetime import datetime, timedelta

from . import db, auth

DEMO_EMAIL = "demo@tradejournal.pro"
DEMO_PASSWORD = "demo1234"

# column order used for the batched trade insert (must match the dicts built
# in _generate_trades)
TRADE_COLS = [
    "symbol", "instrument", "direction", "quantity", "entry_price", "exit_price",
    "stop_price", "fees", "entry_time", "exit_time", "strategy", "setup",
    "market_condition", "timeframe", "session", "tags", "pre_notes", "post_notes",
    "emotion", "rating", "screenshot",
]

SYMBOLS = ["AAPL", "TSLA", "NVDA", "SPY", "AMD", "MSFT", "META", "QQQ", "COIN", "BTCUSD"]
STRATEGIES = ["Breakout", "Pullback", "VWAP Reversion", "Trend Follow", "Gap & Go", "Mean Reversion"]
SETUPS = ["Bull Flag", "ABCD", "Opening Range", "Double Bottom", "EMA Bounce", "Failed Breakdown"]
CONDITIONS = ["Trending", "Ranging", "Volatile"]
SESSIONS = ["Pre-market", "Open", "Midday", "Power Hour", "After-hours"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "Daily"]
EMOTIONS = ["calm", "confident", "fomo", "fear", "greed", "revenge", "calm", "confident"]


def run(reset=False):
    if reset:
        import os
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
    db.init_db()
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT id FROM users WHERE email=?", (DEMO_EMAIL,)).fetchone()
        if row:
            uid = row["id"]
            conn.execute("DELETE FROM trades WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM goals WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM habits WHERE user_id=?", (uid,))
        else:
            pw_hash, salt = auth.hash_password(DEMO_PASSWORD)
            uid = conn.insert(
                "INSERT INTO users (email, name, pw_hash, pw_salt, trader_type, experience, "
                "account_size, base_currency, onboarded) VALUES (?,?,?,?,?,?,?,?,1)",
                (DEMO_EMAIL, "Demo Trader", pw_hash, salt, "intraday", "intermediate", 25000, "INR"),
            )

        rng = random.Random(42)
        trades = _generate_trades(rng)
        # batch-insert so seeding stays fast on a remote Postgres (single round trip)
        cols = ", ".join(TRADE_COLS)
        ph = ", ".join("?" for _ in TRADE_COLS)
        conn.executemany(
            f"INSERT INTO trades (user_id, {cols}) VALUES (?, {ph})",
            [[uid, *[t[c] for c in TRADE_COLS]] for t in trades],
        )

        # goals
        conn.execute("INSERT INTO goals (user_id, title, metric, target) VALUES (?,?,?,?)",
                     (uid, "Reach 55% win rate", "win_rate", 55))
        conn.execute("INSERT INTO goals (user_id, title, metric, target) VALUES (?,?,?,?)",
                     (uid, "Grow account by $5,000", "pnl", 5000))
        conn.execute("INSERT INTO goals (user_id, title, metric, target) VALUES (?,?,?,?)",
                     (uid, "Hold profit factor above 1.5", "profit_factor", 1.5))

        # habits with some history
        today = datetime.now().date()
        for name in ["Followed my trading plan", "Journaled every trade", "Respected daily loss limit",
                     "No trading before the open"]:
            log = {}
            for i in range(20):
                d = (today - timedelta(days=i)).isoformat()
                log[d] = rng.random() > 0.25
            conn.execute("INSERT INTO habits (user_id, name, log) VALUES (?,?,?)",
                         (uid, name, json.dumps(log)))

        conn.commit()
    finally:
        conn.close()

    print(f"Seeded demo account.\n  email:    {DEMO_EMAIL}\n  password: {DEMO_PASSWORD}")


def seed_if_empty():
    """Seed the demo account only when the database has no users yet.

    Called on serverless cold start (see db.ensure_ready) so a freshly
    provisioned Postgres comes up with a ready-to-explore demo account."""
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        count = db.row_to_dict(row)["n"]
    finally:
        conn.close()
    if count and int(count) > 0:
        return
    run(reset=False)


def _generate_trades(rng):
    trades = []
    start = datetime.now() - timedelta(days=58)
    day = start
    while day < datetime.now():
        if day.weekday() >= 5:  # skip weekends for equities
            day += timedelta(days=1)
            continue
        # most days a few trades; ~1 in 6 days is an overtrading binge
        n = rng.choice([1, 2, 2, 3, 3, 4]) if rng.random() > 0.16 else rng.choice([8, 9, 10, 11])
        binge = n >= 8
        last_loss = None
        t_cursor = day.replace(hour=9, minute=35, second=0, microsecond=0)
        for _ in range(n):
            sym = rng.choice(SYMBOLS)
            direction = rng.choice(["long", "long", "short"])
            entry = round(rng.uniform(20, 480), 2)
            # base win probability; binges and revenge trades are worse
            p_win = 0.58
            emotion = rng.choice(EMOTIONS)
            base_qty = rng.choice([50, 100, 100, 150, 200])
            # revenge: right after a loss, bigger size + worse odds
            if last_loss is not None and rng.random() < 0.38:
                base_qty = int(base_qty * rng.uniform(1.4, 2.1))
                emotion = "revenge"
                p_win = 0.40
                t_cursor = last_loss + timedelta(minutes=rng.randint(3, 25))
            if binge:
                p_win -= 0.05
            win = rng.random() < p_win
            risk = round(entry * rng.uniform(0.01, 0.03), 2)
            stop = round(entry - risk, 2) if direction == "long" else round(entry + risk, 2)
            # exit relative to entry — winners cut a touch short vs losers (a subtle leak)
            if win:
                move = risk * rng.uniform(0.9, 2.1)
                hold_min = rng.randint(6, 90)      # winners held shorter
            else:
                move = -risk * rng.uniform(0.8, 1.9)
                hold_min = rng.randint(30, 240)    # losers held (hoped) longer
            exit_price = round(entry + move if direction == "long" else entry - move, 2)
            qty = base_qty
            entry_time = t_cursor
            exit_time = entry_time + timedelta(minutes=hold_min)
            fees = round(rng.uniform(0.5, 4), 2)
            pnl = (exit_price - entry) * qty if direction == "long" else (entry - exit_price) * qty

            trades.append({
                "symbol": sym,
                "instrument": "crypto" if sym.endswith("USD") else "equity",
                "direction": direction,
                "quantity": qty,
                "entry_price": entry,
                "exit_price": exit_price,
                "stop_price": stop,
                "fees": fees,
                "entry_time": entry_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "exit_time": exit_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "strategy": rng.choice(STRATEGIES),
                "setup": rng.choice(SETUPS),
                "market_condition": rng.choice(CONDITIONS),
                "timeframe": rng.choice(TIMEFRAMES),
                "session": rng.choice(SESSIONS),
                "tags": "",
                "pre_notes": "Waited for confirmation." if not binge else "Saw it moving, jumped in.",
                "post_notes": "Executed to plan." if win and emotion == "calm" else
                              ("Chased — should have skipped." if emotion in ("fomo", "revenge") else "Stopped out."),
                "emotion": emotion,
                "rating": rng.choice([4, 5, 4, 3]) if emotion in ("calm", "confident") else rng.choice([1, 2, 2, 3]),
                "screenshot": "",
            })
            last_loss = exit_time if pnl < 0 else None
            t_cursor = exit_time + timedelta(minutes=rng.randint(10, 90))
        day += timedelta(days=1)
    return trades


if __name__ == "__main__":
    run()
