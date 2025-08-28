# api/index.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from create_game import publish_game_to_supabase, _slugify
from supabase_client import public_url

app = FastAPI()

class GenerateReq(BaseModel):
    prompt: str
    model: str | None = None

@app.post("/api/generate")
def generate(req: GenerateReq):
    try:
        res = publish_game_to_supabase(prompt=req.prompt, model=req.model)
        # Construct public URLs (bucket is public)
        folder = f"games/{res.slug}/"
        html_public = public_url(f"games/{folder}index.html")
        thumb_public = public_url(f"games/{folder}thumb.svg")
        return {
            "slug": res.slug,
            "title": res.title,
            "summary": res.summary,
            "index_url": html_public,
            "thumb_url": thumb_public,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
