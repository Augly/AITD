from pathlib import Path
import json


def load_candidate_symbols(context):
    """Return a list of futures symbols to scan."""
    manual_symbols = context["manual_symbols"]

    # Example: read a local JSON file and return payload["symbols"]
    # payload_path = Path(context["project_root"]) / "data" / "my_symbols.json"
    # payload = json.loads(payload_path.read_text(encoding="utf-8"))
    # return payload.get("symbols", [])

    return manual_symbols
