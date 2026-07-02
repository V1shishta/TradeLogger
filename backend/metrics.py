"""Performance metrics and aggregations.

All calculations are derived purely from the user's logged trades so every
number shown in the UI is explainable and reproducible.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date
from statistics import mean, pstdev


# ---------------------------------------------------------------------------
# Per-trade enrichment
# ---------------------------------------------------------------------------

def parse_dt(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def enrich_trade(t: dict) -> dict:
    """Add computed fields (pnl, R multiple, return %, is_win, holding time)."""
    t = dict(t)
    qty = t.get("quantity") or 0
    entry = t.get("entry_price") or 0
    exit_ = t.get("exit_price")
    fees = t.get("fees") or 0
    # contract/point multiplier — 1 for equities/crypto, lot value for
    # futures & commodities (e.g. MCX GOLD = 100, CRUDEOIL = 100).
    mult = t.get("multiplier") or 1
    direction = (t.get("direction") or "long").lower()
    is_open = exit_ is None or exit_ == ""

    t["is_open"] = is_open
    if is_open:
        t["pnl"] = None
        t["return_pct"] = None
        t["r_multiple"] = None
        t["is_win"] = None
    else:
        exit_ = float(exit_)
        move = (exit_ - entry) if direction == "long" else (entry - exit_)
        gross = move * qty * mult
        pnl = gross - fees
        t["pnl"] = round(pnl, 2)
        cost_basis = abs(entry * qty * mult) or 1
        t["return_pct"] = round(pnl / cost_basis * 100, 2)
        t["is_win"] = pnl > 0
        stop = t.get("stop_price")
        if stop:
            risk_per_unit = abs(entry - float(stop))
            risk = risk_per_unit * abs(qty) * mult
            t["r_multiple"] = round(pnl / risk, 2) if risk else None
        else:
            t["r_multiple"] = None

    # holding time in hours
    et, xt = parse_dt(t.get("entry_time")), parse_dt(t.get("exit_time"))
    if et and xt:
        t["holding_hours"] = round((xt - et).total_seconds() / 3600, 2)
    else:
        t["holding_hours"] = None
    return t


def enrich_all(trades: list[dict]) -> list[dict]:
    return [enrich_trade(t) for t in trades]


# ---------------------------------------------------------------------------
# Portfolio-level metrics
# ---------------------------------------------------------------------------

def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0] if equity else 0
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = min(max_dd, v - peak)
    return round(max_dd, 2)


def portfolio_metrics(trades: list[dict], starting_equity: float = 0.0) -> dict:
    closed = [t for t in trades if not t["is_open"]]
    n = len(closed)
    if n == 0:
        return {
            "total_trades": 0, "closed_trades": 0, "open_trades": len(trades),
            "net_pnl": 0, "win_rate": 0, "wins": 0, "losses": 0,
            "avg_win": 0, "avg_loss": 0, "profit_factor": 0, "expectancy": 0,
            "avg_r": None, "max_drawdown": 0, "best_trade": 0, "worst_trade": 0,
            "avg_hold_hours": None, "largest_win_streak": 0, "largest_loss_streak": 0,
        }

    pnls = [t["pnl"] for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    win_rate = len(wins) / n * 100
    avg_win = mean(wins) if wins else 0
    avg_loss = mean(losses) if losses else 0
    expectancy = mean(pnls)  # average $ per trade
    profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0)

    rs = [t["r_multiple"] for t in closed if t.get("r_multiple") is not None]
    avg_r = round(mean(rs), 2) if rs else None

    # equity curve ordered by exit time
    ordered = sorted(closed, key=lambda t: t.get("exit_time") or t.get("entry_time") or "")
    equity, running = [], starting_equity
    for t in ordered:
        running += t["pnl"]
        equity.append(running)

    holds = [t["holding_hours"] for t in closed if t.get("holding_hours") is not None]

    # streaks
    best_streak = cur = 0
    worst_streak = curl = 0
    for t in ordered:
        if t["pnl"] > 0:
            cur += 1; curl = 0
        elif t["pnl"] < 0:
            curl += 1; cur = 0
        best_streak = max(best_streak, cur)
        worst_streak = max(worst_streak, curl)

    return {
        "total_trades": len(trades),
        "closed_trades": n,
        "open_trades": len(trades) - n,
        "net_pnl": round(sum(pnls), 2),
        "win_rate": round(win_rate, 1),
        "wins": len(wins),
        "losses": len(losses),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else None,
        "expectancy": round(expectancy, 2),
        "avg_r": avg_r,
        "max_drawdown": _max_drawdown(equity),
        "best_trade": round(max(pnls), 2),
        "worst_trade": round(min(pnls), 2),
        "avg_hold_hours": round(mean(holds), 2) if holds else None,
        "largest_win_streak": best_streak,
        "largest_loss_streak": worst_streak,
    }


def equity_curve(trades: list[dict], starting_equity: float = 0.0) -> list[dict]:
    closed = [t for t in trades if not t["is_open"]]
    ordered = sorted(closed, key=lambda t: t.get("exit_time") or t.get("entry_time") or "")
    out, running = [], starting_equity
    for t in ordered:
        running += t["pnl"]
        out.append({
            "date": (t.get("exit_time") or t.get("entry_time") or "")[:10],
            "equity": round(running, 2),
            "pnl": t["pnl"],
            "symbol": t["symbol"],
        })
    return out


def daily_pnl(trades: list[dict]) -> dict:
    """Map YYYY-MM-DD -> {pnl, trades} for the calendar heatmap."""
    agg = defaultdict(lambda: {"pnl": 0.0, "trades": 0})
    for t in trades:
        if t["is_open"]:
            continue
        d = (t.get("exit_time") or t.get("entry_time") or "")[:10]
        if not d:
            continue
        agg[d]["pnl"] += t["pnl"]
        agg[d]["trades"] += 1
    return {d: {"pnl": round(v["pnl"], 2), "trades": v["trades"]} for d, v in agg.items()}


def breakdown_by(trades: list[dict], field: str) -> list[dict]:
    """Group closed trades by a categorical field and compute per-group stats."""
    groups = defaultdict(list)
    for t in trades:
        if t["is_open"]:
            continue
        key = (t.get(field) or "Uncategorized") or "Uncategorized"
        groups[key].append(t)
    out = []
    for key, ts in groups.items():
        pnls = [t["pnl"] for t in ts]
        wins = [p for p in pnls if p > 0]
        out.append({
            "group": key,
            "trades": len(ts),
            "net_pnl": round(sum(pnls), 2),
            "win_rate": round(len(wins) / len(ts) * 100, 1),
            "avg_pnl": round(mean(pnls), 2),
            "expectancy": round(mean(pnls), 2),
        })
    out.sort(key=lambda x: x["net_pnl"], reverse=True)
    return out


def weekday_session_breakdown(trades: list[dict]) -> dict:
    by_weekday = defaultdict(list)
    for t in trades:
        if t["is_open"]:
            continue
        dt = parse_dt(t.get("entry_time"))
        if dt:
            by_weekday[dt.strftime("%A")].append(t["pnl"])
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = [{"group": d, "net_pnl": round(sum(by_weekday[d]), 2), "trades": len(by_weekday[d])}
               for d in order if by_weekday[d]]
    return {"weekday": weekday}
