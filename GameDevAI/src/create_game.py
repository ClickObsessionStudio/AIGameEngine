from __future__ import annotations
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

from game_engine import generate_game, DEFAULT_MODEL

# Load environment variables from .env file
load_dotenv()

# --- Supabase Initialization ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials not found in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "games"

# -------------------- Public API --------------------

__all__ = ["publish_game_to_supabase", "PublishResult"]

@dataclass(frozen=True)
class PublishResult:
    slug: str
    title: str
    summary: str
    game_url: str
    thumbnail_url: str

def publish_game_to_supabase(
    prompt: str,
    model: Optional[str] = None,
) -> PublishResult:
    """
    Generates a game and publishes its assets and metadata to Supabase.
    """
    # 1) Generate game content from OpenAI
    model = model or DEFAULT_MODEL
    game_data = generate_game(prompt, model=model)

    # 2) Create a unique slug
    base = game_data.title.strip() or prompt
    slug = _slugify(base)

    # 3) Upload game files to Supabase Storage
    # Upload HTML file
    html_path_on_storage = f"{slug}/index.html"
    supabase.storage.from_(BUCKET_NAME).upload(
        path=html_path_on_storage,
        file=game_data.html.encode("utf-8"),
        file_options={"content-type": "text/html", "upsert": "true"}
    )

    # Generate and upload SVG thumbnail
    svg_content = _create_thumb_svg(title=game_data.title, slug=slug)
    svg_path_on_storage = f"{slug}/thumb.svg"
    supabase.storage.from_(BUCKET_NAME).upload(
        path=svg_path_on_storage,
        file=svg_content.encode("utf-8"),
        file_options={"content-type": "image/svg+xml", "upsert": "true"}
    )

    # 4) Get public URLs for the uploaded files
    game_url = supabase.storage.from_(BUCKET_NAME).get_public_url(html_path_on_storage)
    thumbnail_url = supabase.storage.from_(BUCKET_NAME).get_public_url(svg_path_on_storage)

    # 5) Upsert game metadata into the Supabase 'games' table
    game_entry = {
        "slug": slug,
        "title": game_data.title,
        "summary": game_data.summary,
        "game_url": game_url,
        "thumbnail_url": thumbnail_url,
        "added_at": datetime.utcnow().isoformat() + "Z",
    }

    # 'upsert' will insert a new row or update it if a row with the same 'slug' already exists.
    # The `on_conflict` parameter is crucial for this behavior.
    supabase.table("games").upsert(game_entry, on_conflict="slug").execute()

    # 6) Return the result object
    return PublishResult(
        slug=slug,
        title=game_data.title,
        summary=game_data.summary,
        game_url=game_url,
        thumbnail_url=thumbnail_url,
    )

# -------------------- Internals (mostly unchanged, some removed) --------------------

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "untitled"

def _create_thumb_svg(*, title: str, slug: str) -> str:
    # This function now returns the SVG string directly instead of writing to a file
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <defs>
    <linearGradient id="g" x1="0" x2="1">
      <stop offset="0" stop-color="#0b2a5a"/>
      <stop offset="1" stop-color="#0f7ea5"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <g font-family="Arial,Helvetica,sans-serif" fill="#e8f0fa">
    <text x="60" y="330" font-size="64" font-weight="700">{title[:40]}</text>
    <text x="60" y="570" font-size="28" fill="#b9cee6">Play Game ▶</text>
  </g>
</svg>"""

# -------------------- CLI (for testing) --------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate & publish a game to Supabase.")
    parser.add_argument("--prompt", required=True, help="User prompt / idea for the game")
    args = parser.parse_args()

    print(f"Generating game for prompt: '{args.prompt}'...")
    result = publish_game_to_supabase(prompt=args.prompt)
    print("\n✅ Game published successfully to Supabase!")
    print(f"   Title: {result.title}")
    print(f"   Summary: {result.summary}")
    print(f"   Play here: {result.game_url}")