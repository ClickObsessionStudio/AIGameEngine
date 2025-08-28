# game_engine.py
from __future__ import annotations

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from data_class import PipelineOutput
from utils import ensure_game_payload
from instructions import SYSTEM_INSTRUCTIONS_ONE_CALL
from openai_client import get_client  # central client

# Load .env BEFORE reading env vars
load_dotenv()

def get_default_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5")


def build_user_message(user_prompt: str) -> str:
    return (
        "Create a complete, playable browser game from this idea. "
        "Choose the most fitting genre/mechanics based on the prompt. "
        "Keep it self-contained (inline CSS/JS) and accessible. "
        "Return STRICT JSON as per schema.\n\n"
        f"USER_IDEA:\n{user_prompt}"
    )


def generate_game(user_prompt: str, model: str | None = None) -> PipelineOutput:
    """
    Core pipeline: calls the model once and returns (title, summary, html).
    """
    client: OpenAI = get_client()
    model = model or get_default_model()

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTIONS_ONE_CALL},
            {"role": "user", "content": build_user_message(user_prompt)},
        ],
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content or ""
    data = json.loads(raw)
    title, summary, html = ensure_game_payload(data)
    return PipelineOutput(title=title, summary=summary, html=html)


if __name__ == "__main__":
    demo_prompt = "Small plane flying game, avoid the birds, collect stars, pixels, retro style"
    result = generate_game(demo_prompt)
    print("\n✅ Generated game!")
    print(f"Title  : {result.title}")
    print(f"Summary: {result.summary}")
    out_path = "index.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.html)
    print(f"Open   : {os.path.abspath(out_path)}\n")
