import re
from typing import Dict, Any, Tuple

def ensure_game_payload(data: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Validate one-shot JSON payload from the model and extract fields.
    """
    missing = [k for k in ("title", "summary", "html") if k not in data]
    if missing:
        raise ValueError(f"Model JSON missing fields: {missing}")
    title = str(data["title"]).strip() or "Untitled Game"
    summary = str(data["summary"]).strip()
    html = str(data["html"]).strip()

    low = html.lower()
    if "<html" not in low or "</html>" not in low or "<script" not in low:
        raise ValueError("HTML must be a complete document and include a <script> block.")
    # Basic sanity checks to avoid external dependencies
    if re.search(r"https?://|@import|<link[^>]+rel=['\"]stylesheet", low):
        raise ValueError("External resources detected; HTML must be fully self-contained.")
    return title, summary, html
