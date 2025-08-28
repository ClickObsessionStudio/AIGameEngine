# migrate_local_games.py
import json
from pathlib import Path
from supabase_client import get_supabase

def migrate(site_dir="../Website", bucket="games"):
    site = Path(site_dir).resolve()
    supa = get_supabase()
    storage = supa.storage.from_(bucket)

    # Optional: if you have catalog.json already
    catalog = site / "catalog.json"
    meta = json.loads(catalog.read_text("utf-8")) if catalog.exists() else []

    for game_dir in (site / "games").iterdir():
        if not game_dir.is_dir(): continue
        slug = game_dir.name
        idx = game_dir / "index.html"
        thumb = game_dir / "thumb.svg"
        if not idx.exists(): continue

        storage.upload(f"games/{slug}/index.html", idx.read_bytes(), {"content-type":"text/html","upsert":True})
        if thumb.exists():
            storage.upload(f"games/{slug}/thumb.svg", thumb.read_bytes(), {"content-type":"image/svg+xml","upsert":True})

        # find metadata if available
        entry = next((x for x in meta if x.get("slug")==slug), None) or {
            "title": slug.replace("-", " ").title(),
            "summary": "(migrated game)"
        }

        supa.table("games").upsert({
            "slug": slug,
            "title": entry["title"],
            "summary": entry.get("summary",""),
            "thumbnail_path": f"{bucket}/games/{slug}/thumb.svg",
            "folder_path": f"{bucket}/games/{slug}/"
        }, on_conflict="slug").execute()

if __name__ == "__main__":
    migrate()
