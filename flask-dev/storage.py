# storage.py
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict

def _default_site_dir() -> Path:
    # On Vercel (serverless), only /tmp is writable. Use local folder otherwise.
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_VERSION"):
        return Path(os.getenv("SITE_DIR", "/tmp/site"))
    # local dev: keep repo folder `site/`
    return Path(__file__).parent / "site"

SITE_DIR: Path = _default_site_dir()
GAMES_DIR = SITE_DIR / "games"
CATALOG = SITE_DIR / "catalog.json"


def ensure_site() -> None:
    """
    Make directories only if we are allowed to write.
    On Vercel, SITE_DIR defaults to /tmp/site (writable, but ephemeral).
    """
    try:
        SITE_DIR.mkdir(parents=True, exist_ok=True)
        GAMES_DIR.mkdir(parents=True, exist_ok=True)
        if not CATALOG.exists():
            CATALOG.write_text("[]\n", encoding="utf-8")
    except Exception:
        # Read-only or other issue: don't crash on import
        pass


def load_catalog() -> List[Dict]:
    try:
        if CATALOG.exists():
            return json.loads(CATALOG.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_catalog(items: List[Dict]) -> None:
    try:
        SITE_DIR.mkdir(parents=True, exist_ok=True)
        CATALOG.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # On Vercel this will be ephemeral, and might fail if FS is read-only
        pass


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "untitled"


def extract_title_from_html(html: str) -> str | None:
    m = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def save_game_files(*, title: str, summary: str, html: str) -> Dict:
    """
    Best-effort persistence:
    - Local: writes to repo ./site/ (durable on your machine)
    - Vercel: writes to /tmp/site (ephemeral but won’t crash)
    """
    items = load_catalog()
    slug = slugify(title)
    now_iso = datetime.utcnow().isoformat() + "Z"

    entry = {
        "slug": slug,
        "title": title,
        "summary": summary,
        "added_at": now_iso,
        "thumbnail": f"/site/games/{slug}/thumb.svg",  # optional
        "path": f"/games/{slug}/",
        "play_count": 0,
    }

    try:
        game_dir = GAMES_DIR / slug
        game_dir.mkdir(parents=True, exist_ok=True)
        (game_dir / "index.html").write_text(html, encoding="utf-8")
        # upsert catalog
        items = [x for x in items if x.get("slug") != slug]
        items.append(entry)
        items.sort(key=lambda x: x.get("added_at", ""), reverse=True)
        save_catalog(items)
    except Exception:
        # swallow on Vercel read-only failures; still return entry so UI can route
        pass

    return entry


def list_games() -> List[Dict]:
    return load_catalog()
