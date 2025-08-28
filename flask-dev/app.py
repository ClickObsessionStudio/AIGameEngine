# flask-dev/app.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from flask import Flask, render_template, request, send_from_directory, jsonify
from dotenv import load_dotenv

# --- Add paths to other modules ---
# The folders are now inside the same directory as app.py
APP_ROOT = Path(__file__).resolve().parent
sys.path.append(str(APP_ROOT / "CinematicTrailerGenAI" / "src"))
sys.path.append(str(APP_ROOT / "TrailerUploader" / "YTShorts"))
# --- End of path additions ---


from game_engine import generate_game, get_default_model
from openai_client import get_client
from storage import SITE_DIR, ensure_site, list_games, save_game_files, extract_title_from_html
from flask import send_file

# trailers - Now these imports will work
from generate_cinematic_trailer import generate_cinematic_trailer
from video_utils import resize_video_to_vertical

# youtube - This import will work after renaming the file
from upload_yt_shorts import upload_video, get_youtube_client

from googleapiclient.errors import HttpError
import traceback


ensure_site()

MEDIA_DIR = (SITE_DIR / "media") if not os.getenv("VERCEL") else Path("/tmp/site/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv()
client = get_client()

app = Flask(__name__)


# ---------- Pages ----------
@app.get("/")
def library():
    games = list_games()
    return render_template("library.html", games=games)


@app.get("/create")
def create_page():
    return render_template("create.html")


@app.get("/games/<slug>/")
def play_game(slug: str):
    game_dir = SITE_DIR / "games" / slug
    if not game_dir.exists():
        return ("Game not found", 404)
    return send_from_directory(game_dir, "index.html")


# ---------- APIs ----------
@app.post("/api/generate/full")
def api_generate_full():
    """
    One-shot generation (NO saving).
    Returns {title, summary, html}. You can refine later.
    """
    data = request.get_json(force=True) or {}
    prompt: str = (data.get("prompt") or "").strip()
    model = (data.get("model") or get_default_model())
    if not prompt:
        return ("Missing prompt", 400)

    result = generate_game(prompt, model=model)
    return jsonify({
        "ok": True,
        "title": result.title,
        "summary": result.summary,
        "html": result.html,
    })


@app.post("/api/generate/edit")
def api_generate_edit():
    """
    Refinement endpoint: take current HTML + user instructions,
    return an UPDATED full HTML document (no saving).
    """
    data = request.get_json(force=True) or {}
    current_html: str = (data.get("html") or "").strip()
    instruction: str = (data.get("prompt") or "").strip()
    if not current_html or not instruction:
        return ("Missing html or prompt", 400)

    SYSTEM = (
        "You are a senior front-end engineer. "
        "You will receive an existing FULL, self-contained HTML game. "
        "Apply the user's instructions and RETURN ONLY a full, valid HTML document "
        "(<html>...</html>) with inline CSS + vanilla JS; no external resources; "
        "no markdown, no JSON, no commentary."
    )
    USER = (
        "USER_INSTRUCTIONS:\n"
        f"{instruction}\n\n"
        "CURRENT_GAME_HTML:\n"
        f"{current_html[:20000]}"
    )

    # use the shared client
    resp = client.chat.completions.create(
        model=get_default_model(),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
    )
    new_html = (resp.choices[0].message.content or "").strip()
    return jsonify({"ok": True, "html": new_html})


@app.post("/api/generate/save")
def api_save_generated():
    """
    Persist the final HTML into the local library and return metadata.
    """
    data = request.get_json(force=True) or {}
    html: str = (data.get("html") or "").strip()
    if not html:
        return ("Missing html", 400)

    title = extract_title_from_html(html) or "Untitled Game"
    summary = "A fun game."
    saved = save_game_files(title=title, summary=summary, html=html)

    return jsonify({
        "ok": True,
        "slug": saved["slug"],
        "title": saved["title"],
        "summary": saved["summary"],
        "path": f"/games/{saved['slug']}/"
    })


#---------- Media APIs ----------
@app.post("/api/trailer/generate")
def api_trailer_generate():
    """
    Generate a cinematic trailer from the user's current prompt/summary,
    then create a vertical 'pad' version for Shorts.
    Stores MP4s under MEDIA_DIR and returns the padded video URL.
    """
    if os.getenv("VERCEL"):
        return jsonify({"ok": False, "error": "Trailer generation is disabled on Vercel. Run locally."}), 501
    
    data = request.get_json(force=True) or {}
    summary = (data.get("summary") or data.get("prompt") or "").strip()
    title = (data.get("title") or "game-trailer").strip()[:60]
    if not summary:
        return ("Missing summary/prompt", 400)

    base_name = f"{title.lower().replace(' ', '-')}-trailer"
    gen_name = f"{base_name}.mp4"
    pad_name = f"{base_name}-pad.mp4"

    gen_path = MEDIA_DIR / gen_name
    pad_path = MEDIA_DIR / pad_name

    try:
        # 1) Generate (landscape or mixed)
        _ = generate_cinematic_trailer(
            prompt=summary,
            model=data.get("model") or "MiniMax-Hailuo-02",
            duration=int(data.get("duration") or 6),
            resolution=data.get("resolution") or "768P",
            output_path=str(gen_path)
        )

        # 2) Resize to vertical with padding (Shorts friendly)
        maybe_new = resize_video_to_vertical(gen_path, mode="pad")
        if maybe_new:
            try:
                from pathlib import Path as _P
                pad_path = _P(maybe_new)
            except Exception:
                pass
        
        if not pad_path.exists():
            guessed = MEDIA_DIR / f"{gen_path.stem}_pad.mp4"
            if guessed.exists():
                guessed.replace(pad_path)
            else:
                if gen_path.exists():
                    import shutil
                    shutil.copy2(gen_path, pad_path)

    except Exception as e:
        return jsonify({"ok": False, "error": f"generate_or_pad_failed: {e}"}), 500

    return jsonify({
        "ok": True,
        "filename": pad_path.name,
        "video_url": f"/media/{pad_path.name}"
    })


@app.post("/api/trailer/upload")
def api_trailer_upload():
    if os.getenv("VERCEL"):
        return jsonify({"ok": False, "error": "YouTube upload is disabled on Vercel. Run locally."}), 501
    
    data = request.get_json(force=True) or {}
    filename = (data.get("filename") or "").strip()
    title = (data.get("title") or "Game Trailer").strip()
    description = (data.get("description") or "").strip()
    privacy = (data.get("privacy") or "public").strip()

    if not filename:
        return ("Missing filename", 400)

    video_path = MEDIA_DIR / filename
    if not video_path.exists():
        return (f"File not found: {video_path}", 404)

    try:
        yt = get_youtube_client()
        video_id = upload_video(
            yt,
            file_path=str(video_path),
            title=title[:95],
            description=description[:4900],
            tags=["#shorts", "game", "trailer"],
            privacy_status=privacy
        )
        return jsonify({"ok": True, "video_id": video_id, "watch_url": f"https://youtu.be/{video_id}"})
    except HttpError as he:
        try:
            err_msg = he.content.decode("utf-8") if hasattr(he, "content") else str(he)
        except Exception:
            err_msg = str(he)
        return jsonify({"ok": False, "error": "YouTube API error", "details": err_msg}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}", "trace": traceback.format_exc(limit=2)}), 500



@app.get("/media/<path:filename>")
def media(filename: str):
    """
    Serve generated media (local/dev). On Vercel this will only work during a warm run.
    """
    path = MEDIA_DIR / filename
    if not path.exists():
        return ("Not found", 404)
    return send_file(path, mimetype="video/mp4", as_attachment=False)

# Static proxy (optional: thumbs etc.)
@app.get("/site/<path:subpath>")
def site_static(subpath: str):
    return send_from_directory(SITE_DIR, subpath)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)