# publish_game.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from game_engine import generate_game, DEFAULT_MODEL


# -------------------- Public API --------------------

__all__ = ["publish_game", "PublishResult"]


@dataclass(frozen=True)
class PublishResult:
    slug: str
    title: str
    summary: str
    game_path: Path
    catalog_path: Path


def publish_game(
    prompt: str,
    site_dir: Path | str = "../Website",
    model: Optional[str] = None,
) -> str:
    """
    Generate a game from `prompt`, publish it into a GitHub Pages site directory,
    update the catalog, and return the game's summary as plain text.

    Args:
        prompt: Free-form user idea.
        site_dir: Path to the site root containing: index.html, assets/, games/, catalog.json.
        model: OpenAI model name (defaults to DEFAULT_MODEL from game_engine.py).

    Returns:
        The generated game's summary (string).
    """
    site_dir = Path(site_dir).resolve()
    _validate_site(site_dir)

    # 1) Generate game
    model = model or DEFAULT_MODEL
    result = generate_game(prompt, model=model)

    # 2) Slug
    base = result.title.strip() or prompt
    slug = _slugify(base)

    # 3) Write files
    game_dir = site_dir / "games" / slug
    _ensure_dirs(game_dir)
    (game_dir / "index.html").write_text(result.html, encoding="utf-8")
    _write_thumb_svg(game_dir / "thumb.svg", title=result.title, slug=slug)

    # 4) Update catalog
    catalog_path = site_dir / "catalog.json"
    items = _load_catalog(catalog_path)
    items = _upsert_catalog_entry(
        items,
        slug=slug,
        title=result.title,
        summary=result.summary,
    )
    _save_catalog(catalog_path, items)

    # Optional: return richer data in case you need it later
    _ = PublishResult(
        slug=slug,
        title=result.title,
        summary=result.summary,
        game_path=game_dir / "index.html",
        catalog_path=catalog_path,
    )

    # 5) Return just the summary (per your requirement)
    return result.summary


# -------------------- Internals --------------------

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "untitled"


def _ensure_dirs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _validate_site(site_dir: Path) -> None:
    if not site_dir.exists():
        raise FileNotFoundError(f"Site dir not found: {site_dir}")
    required = ["index.html", "assets", "games", "catalog.json"]
    missing = [name for name in required if not (site_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Site dir missing required items: {', '.join(missing)}. "
            "Initialize your Website repo per the setup guide."
        )


def _load_catalog(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_catalog(path: Path, items: List[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _upsert_catalog_entry(
    items: List[dict],
    *,
    slug: str,
    title: str,
    summary: str,
) -> List[dict]:
    now_iso = datetime.utcnow().isoformat() + "Z"
    entry = {
        "slug": slug,
        "title": title,
        "summary": summary,
        "added_at": now_iso,
        "thumbnail": f"games/{slug}/thumb.svg",
        "path": f"games/{slug}/",
        "play_count": 0,
    }
    filtered = [x for x in items if x.get("slug") != slug]
    filtered.append(entry)
    filtered.sort(key=lambda x: x.get("added_at", ""), reverse=True)
    return filtered


def _write_thumb_svg(dest: Path, *, title: str, slug: str) -> None:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <defs>
    <linearGradient id="g" x1="0" x2="1">
      <stop offset="0" stop-color="#0b2a5a"/>
      <stop offset="1" stop-color="#0f7ea5"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <g font-family="Arial,Helvetica,sans-serif" fill="#e8f0fa">
    <text x="60" y="330" font-size="64" font-weight="700">{title[:40]}</text>
    <text x="60" y="570" font-size="28" fill="#b9cee6">Play ▶ /games/{slug}/</text>
  </g>
</svg>"""
    dest.write_text(svg, encoding="utf-8")


# -------------------- CLI --------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate & publish a game to a GitHub Pages site and print the summary."
    )
    parser.add_argument("--prompt", required=True, help="User prompt / idea for the game")
    parser.add_argument("--site-dir", default="../Website", help="Path to Website repo root")
    parser.add_argument("--model", default=None, help="OpenAI model name (defaults to game_engine.DEFAULT_MODEL)")
    args = parser.parse_args()

    summary = publish_game(prompt=args.prompt, site_dir=args.site_dir, model=args.model)
    print("\n=== GAME SUMMARY ===\n")
    print(summary)
    print("\n(Commit & push your Website repo to publish.)\n")
