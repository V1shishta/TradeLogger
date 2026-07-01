"""Flexible CSV importer for broker exports.

Broker exports differ wildly, so instead of hard-coding one schema we normalize
headers and match them against a synonym map. This covers the common shapes from
TD Ameritrade / thinkorswim, Interactive Brokers, Robinhood, Webull, and generic
spreadsheet exports, and degrades gracefully on unknown columns.
"""
import csv
import io

# canonical field -> possible header names (lowercased, spaces/underscores stripped)
SYNONYMS = {
    "symbol":      ["symbol", "ticker", "instrument", "underlying", "contract"],
    "instrument":  ["assettype", "type", "securitytype", "instrumenttype"],
    "direction":   ["direction", "side", "action", "buysell", "longshort"],
    "quantity":    ["quantity", "qty", "shares", "size", "contracts", "amount", "units"],
    "entry_price": ["entryprice", "buyprice", "openprice", "avgentry", "price", "fillprice", "entry"],
    "exit_price":  ["exitprice", "sellprice", "closeprice", "avgexit", "exit"],
    "stop_price":  ["stop", "stopprice", "stoploss"],
    "fees":        ["fees", "commission", "commissions", "fee", "cost"],
    "entry_time":  ["entrytime", "opendate", "datetime", "date", "opentime", "tradedate", "boughtdate"],
    "exit_time":   ["exittime", "closedate", "closetime", "solddate"],
    "strategy":    ["strategy", "playbook"],
    "setup":       ["setup", "pattern"],
    "market_condition": ["marketcondition", "market", "condition"],
    "timeframe":   ["timeframe", "interval", "tf"],
    "session":     ["session"],
    "tags":        ["tags", "labels"],
    "pre_notes":   ["prenotes", "planno", "plan", "thesis"],
    "post_notes":  ["postnotes", "notes", "comment", "comments", "review"],
    "emotion":     ["emotion", "mood", "psychology"],
}

NUMERIC = {"quantity", "entry_price", "exit_price", "stop_price", "fees"}


def _norm(h):
    return "".join(c for c in h.lower() if c.isalnum())


def _build_mapping(headers):
    norm_headers = {_norm(h): h for h in headers}
    mapping = {}
    for field, names in SYNONYMS.items():
        for name in names:
            if name in norm_headers:
                mapping[field] = norm_headers[name]
                break
    return mapping


def _clean_number(v):
    if v is None:
        return None
    s = str(v).strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    if s in ("", "-", "--", "n/a", "na"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _norm_direction(v):
    s = (v or "").strip().lower()
    if s in ("buy", "long", "bot", "b", "buy to open"):
        return "long"
    if s in ("sell", "short", "sld", "s", "sell to open", "sell short"):
        return "short"
    return "long"


def parse_csv(text):
    """Return (rows, warnings). Each row is a partial trade dict ready to insert."""
    warnings = []
    # sniff delimiter
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return [], ["Could not read any header row."]

    mapping = _build_mapping(reader.fieldnames)
    if "symbol" not in mapping:
        warnings.append("No recognizable 'symbol' column found — check the file format.")
    required_present = {"symbol", "quantity", "entry_price"} <= set(mapping)
    if not required_present:
        warnings.append("Import needs at least symbol, quantity and entry price columns.")

    rows = []
    for i, raw in enumerate(reader, start=2):
        rec = {}
        for field, col in mapping.items():
            val = raw.get(col, "")
            if field in NUMERIC:
                rec[field] = _clean_number(val)
            elif field == "direction":
                rec[field] = _norm_direction(val)
            else:
                rec[field] = (val or "").strip()
        if not rec.get("symbol") or rec.get("quantity") in (None, 0) or rec.get("entry_price") is None:
            continue
        rec.setdefault("direction", "long")
        rec.setdefault("instrument", "equity")
        rec["quantity"] = abs(rec["quantity"])
        rows.append(rec)

    if not rows and not warnings:
        warnings.append("No valid trade rows were found.")
    return rows, warnings
