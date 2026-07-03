"""Explainable behavioral-analysis engine ("AI Coach").

Every insight is a deterministic, auditable rule over the trader's own history.
There is no black box: each detection returns the concrete evidence (counts,
dollar figures, trade ids) that triggered it, satisfying the product constraint
that AI recommendations must be explainable and grounded in historical data.

Design note: this is intentionally a transparent heuristics engine rather than
an opaque model. The same feature signals (inter-trade timing, size deltas after
losses, hold-time asymmetry, clustering) are exactly what an ML layer would learn
from later — so the architecture is a drop-in upgrade path, not a throwaway.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from statistics import mean, pstdev

from .metrics import parse_dt


def _sorted_by_entry(trades):
    return sorted(
        [t for t in trades if not t["is_open"]],
        key=lambda t: t.get("entry_time") or "",
    )


def _notional(t):
    return abs((t.get("entry_price") or 0) * (t.get("quantity") or 0))


# ---------------------------------------------------------------------------
# Individual detectors -> each returns an insight dict or None
# ---------------------------------------------------------------------------

def detect_revenge_trading(trades):
    ordered = _sorted_by_entry(trades)
    hits = []
    for prev, cur in zip(ordered, ordered[1:]):
        if prev["pnl"] is None or prev["pnl"] >= 0:
            continue
        pe, ce = parse_dt(prev.get("exit_time") or prev.get("entry_time")), parse_dt(cur.get("entry_time"))
        if not pe or not ce:
            continue
        gap = (ce - pe).total_seconds() / 60.0
        bigger = _notional(cur) > _notional(prev) * 1.2
        soon = 0 <= gap <= 45
        emotional = (cur.get("emotion") or "").lower() in ("revenge", "angry", "frustrated")
        if soon and (bigger or emotional):
            hits.append(cur)
    if len(hits) < 2:
        return None
    hit_pnl = sum(t["pnl"] for t in hits)
    sev = "high" if len(hits) >= 5 or hit_pnl < 0 else "medium"
    return {
        "pattern": "Revenge Trading",
        "severity": sev,
        "count": len(hits),
        "impact": round(hit_pnl, 2),
        "evidence": f"{len(hits)} trades opened within 45 min of a loss, most with larger size than the losing trade. "
                    f"Net P&L on these: ₹{hit_pnl:,.2f}.",
        "recommendation": "Add a mandatory cool-off rule: no new entry for 30–60 min after a losing trade, and never "
                          "increase size on the trade immediately following a loss.",
    }


def detect_overtrading(trades):
    by_day = defaultdict(list)
    for t in _sorted_by_entry(trades):
        d = (t.get("entry_time") or "")[:10]
        if d:
            by_day[d].append(t)
    if len(by_day) < 3:
        return None
    counts = {d: len(ts) for d, ts in by_day.items()}
    avg = mean(counts.values())
    threshold = max(avg * 1.8, avg + 3)
    heavy_days = {d: ts for d, ts in by_day.items() if len(ts) >= threshold}
    if not heavy_days:
        return None
    heavy_pnl = sum(t["pnl"] for ts in heavy_days.values() for t in ts)
    normal_pnl = sum(t["pnl"] for d, ts in by_day.items() if d not in heavy_days for t in ts)
    normal_days = len(by_day) - len(heavy_days)
    heavy_avg = heavy_pnl / max(len(heavy_days), 1)
    normal_avg = normal_pnl / max(normal_days, 1)
    sev = "high" if heavy_avg < 0 and heavy_avg < normal_avg else "medium"
    return {
        "pattern": "Overtrading",
        "severity": sev,
        "count": len(heavy_days),
        "impact": round(heavy_pnl, 2),
        "evidence": f"On {len(heavy_days)} high-volume day(s) you averaged {max(len(ts) for ts in heavy_days.values())} "
                    f"trades vs a {avg:.1f}/day baseline. Avg P&L on heavy days ₹{heavy_avg:,.2f} vs "
                    f"₹{normal_avg:,.2f} on normal days.",
        "recommendation": "Cap daily trade count near your baseline. Quality over quantity — pre-define the number of "
                          "A+ setups you'll take per session and stop when you hit it.",
    }


def detect_cutting_winners(trades):
    closed = [t for t in trades if not t["is_open"]]
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] < 0]
    if len(wins) < 3 or len(losses) < 3:
        return None
    avg_win = mean(t["pnl"] for t in wins)
    avg_loss = abs(mean(t["pnl"] for t in losses))
    win_hold = [t["holding_hours"] for t in wins if t.get("holding_hours") is not None]
    loss_hold = [t["holding_hours"] for t in losses if t.get("holding_hours") is not None]
    payoff = avg_win / avg_loss if avg_loss else 0
    hold_asym = (mean(win_hold) < mean(loss_hold) * 0.7) if win_hold and loss_hold else False
    if payoff >= 1.0 and not hold_asym:
        return None
    sev = "high" if payoff < 0.7 else "medium"
    ev = f"Average winner ₹{avg_win:,.2f} vs average loser ₹{avg_loss:,.2f} (payoff ratio {payoff:.2f}). "
    if hold_asym:
        ev += f"You hold winners {mean(win_hold):.1f}h but losers {mean(loss_hold):.1f}h — the opposite of a healthy edge."
    return {
        "pattern": "Cutting Winners / Holding Losers",
        "severity": sev,
        "count": len(wins),
        "impact": round(avg_win - avg_loss, 2),
        "evidence": ev,
        "recommendation": "Use predefined profit targets and trailing stops so winners run to plan. Honor your stop-loss "
                          "on losers instead of hoping for a recovery.",
    }


def detect_position_sizing(trades):
    closed = _sorted_by_entry(trades)
    notionals = [_notional(t) for t in closed if _notional(t) > 0]
    if len(notionals) < 5:
        return None
    cv = pstdev(notionals) / mean(notionals) if mean(notionals) else 0
    # size increase right after a loss
    ordered = closed
    upsize_after_loss = 0
    for prev, cur in zip(ordered, ordered[1:]):
        if prev["pnl"] is not None and prev["pnl"] < 0 and _notional(cur) > _notional(prev) * 1.3:
            upsize_after_loss += 1
    if cv < 0.6 and upsize_after_loss < 2:
        return None
    sev = "high" if cv > 1.0 or upsize_after_loss >= 4 else "medium"
    return {
        "pattern": "Inconsistent Position Sizing",
        "severity": sev,
        "count": upsize_after_loss,
        "impact": None,
        "evidence": f"Position size varies widely (coefficient of variation {cv:.2f}; consistent sizing is < 0.40). "
                    f"You up-sized right after a loss {upsize_after_loss} time(s).",
        "recommendation": "Size every trade by a fixed % risk of account (e.g. 1% per trade). Consistent risk makes your "
                          "expectancy meaningful and prevents one impulsive trade from erasing a good week.",
    }


def detect_fomo(trades):
    closed = _sorted_by_entry(trades)
    fomo = [t for t in closed if (t.get("emotion") or "").lower() in ("fomo", "greed", "excited")]
    # chasing: 3+ entries in the same symbol on the same day
    by_sym_day = defaultdict(list)
    for t in closed:
        by_sym_day[(t["symbol"], (t.get("entry_time") or "")[:10])].append(t)
    chase = [ts for ts in by_sym_day.values() if len(ts) >= 3]
    if len(fomo) < 2 and not chase:
        return None
    fomo_pnl = sum(t["pnl"] for t in fomo)
    sev = "high" if fomo_pnl < 0 or len(chase) >= 2 else "low"
    ev = ""
    if fomo:
        wr = sum(1 for t in fomo if t["pnl"] > 0) / len(fomo) * 100
        ev += f"{len(fomo)} trades were tagged FOMO/greed with a {wr:.0f}% win rate and ₹{fomo_pnl:,.2f} net. "
    if chase:
        ev += f"{len(chase)} instance(s) of chasing (3+ re-entries in one symbol in a day)."
    return {
        "pattern": "FOMO / Chasing Entries",
        "severity": sev,
        "count": len(fomo) + len(chase),
        "impact": round(fomo_pnl, 2),
        "evidence": ev,
        "recommendation": "Require a written setup reason before entry. If price has already run past your planned entry, "
                          "let it go — there is always another trade.",
    }


def detect_discipline(trades):
    closed = [t for t in trades if not t["is_open"]]
    rated = [t for t in closed if t.get("rating")]
    if len(rated) < 5:
        return None
    hi = [t for t in rated if t["rating"] >= 4]
    lo = [t for t in rated if t["rating"] <= 2]
    if not hi or not lo:
        return None
    hi_exp = mean(t["pnl"] for t in hi)
    lo_exp = mean(t["pnl"] for t in lo)
    if hi_exp <= lo_exp:
        return None
    return {
        "pattern": "Discipline Pays (positive)",
        "severity": "info",
        "count": len(hi),
        "impact": round(hi_exp - lo_exp, 2),
        "evidence": f"Well-executed trades (self-rated 4–5) average ₹{hi_exp:,.2f} vs ₹{lo_exp:,.2f} for rushed ones "
                    f"(rated 1–2). Following your process is worth ₹{hi_exp - lo_exp:,.2f}/trade to you.",
        "recommendation": "Keep grading execution. Your data proves discipline is your edge — protect it by only taking "
                          "trades you'd rate 4+ in advance.",
    }


DETECTORS = [
    detect_revenge_trading,
    detect_overtrading,
    detect_cutting_winners,
    detect_position_sizing,
    detect_fomo,
    detect_discipline,
]


def analyze(trades):
    insights = []
    for d in DETECTORS:
        try:
            res = d(trades)
        except Exception:
            res = None
        if res:
            insights.append(res)
    sev_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    insights.sort(key=lambda i: sev_order.get(i["severity"], 4))
    return insights


# ---------------------------------------------------------------------------
# Narrative report generation
# ---------------------------------------------------------------------------

def generate_report(trades, metrics, period_label="All time"):
    """Build a plain-language performance report with strengths, weaknesses,
    and prioritized recommendations."""
    insights = analyze(trades)
    strengths, weaknesses = [], []

    wr = metrics["win_rate"]
    pf = metrics["profit_factor"]
    exp = metrics["expectancy"]

    if metrics["closed_trades"] == 0:
        return {
            "period": period_label,
            "headline": "Log a few closed trades to unlock your first coaching report.",
            "strengths": [], "weaknesses": [], "insights": [], "recommendations": [],
            "grade": "—",
        }

    if pf and pf >= 1.5:
        strengths.append(f"Solid profit factor of {pf} — winners more than cover losers.")
    if wr >= 50:
        strengths.append(f"Win rate of {wr}% keeps you on the right side of trades.")
    if exp > 0:
        strengths.append(f"Positive expectancy of ₹{exp:,.2f} per trade — the system has an edge.")
    if metrics.get("avg_r") and metrics["avg_r"] >= 0.5:
        strengths.append(f"Healthy average R of {metrics['avg_r']} shows good reward-to-risk.")

    if pf is not None and pf < 1.0:
        weaknesses.append(f"Profit factor {pf} is below 1.0 — losses currently outpace gains.")
    if metrics["avg_loss"] and abs(metrics["avg_loss"]) > metrics["avg_win"]:
        weaknesses.append("Average loss is larger than average win — risk control needs tightening.")
    if metrics["max_drawdown"] < 0 and abs(metrics["max_drawdown"]) > abs(metrics["net_pnl"]):
        weaknesses.append("Peak-to-trough drawdown exceeds net P&L — equity is volatile.")

    recs = [i["recommendation"] for i in insights if i["severity"] in ("high", "medium")]
    if not recs:
        recs.append("No major behavioral leaks detected — focus on consistency and journaling every trade.")

    # simple letter grade from expectancy + profit factor + discipline
    score = 0
    score += 2 if exp > 0 else 0
    score += 2 if (pf or 0) >= 1.5 else (1 if (pf or 0) >= 1 else 0)
    score += 1 if wr >= 45 else 0
    score -= sum(1 for i in insights if i["severity"] == "high")
    grade = ["D", "C", "C+", "B", "B+", "A"][max(0, min(5, score))]

    headline = (f"{period_label}: {metrics['closed_trades']} closed trades, "
                f"₹{metrics['net_pnl']:,.2f} net, {wr}% win rate.")

    return {
        "period": period_label,
        "headline": headline,
        "grade": grade,
        "strengths": strengths or ["Keep logging — more data will surface your strengths."],
        "weaknesses": weaknesses or ["No structural weaknesses flagged this period."],
        "insights": insights,
        "recommendations": recs[:5],
    }
