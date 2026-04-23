from pathlib import Path
import json


def load_candidate_symbols(context):
    """Return a list of futures symbols to scan."""
    latest_scan_path = context["latest_scan_path"]
    manual_symbols = context.get("manual_symbols", [])

    data = json.loads(Path(latest_scan_path).read_text(encoding="utf-8"))
    opportunities = data.get("opportunities", [])

    symbols = []
    seen = set()
    for item in opportunities:
        symbol = str(item.get("symbol") or "").strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)

    # Fallback to the manually configured list if the latest scan file is empty.
    return symbols or manual_symbols
