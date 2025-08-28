from __future__ import annotations

import os
from flask import Flask, render_template, request, send_from_directory, jsonify
from dotenv import load_dotenv

from game_engine import generate_game, get_default_model  # updated helper
from openai_client import get_client                      # single client
from storage import SITE_DIR, ensure_site, list_games, save_game_files, extract_title_from_html
ensure_site()

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


# Static proxy (optional: thumbs etc.)
@app.get("/site/<path:subpath>")
def site_static(subpath: str):
    return send_from_directory(SITE_DIR, subpath)


if __name__ == "__main__":
    # Use 5000 (default) unless you specifically want a different port.
    app.run(host="127.0.0.1", port=5000, debug=True)
