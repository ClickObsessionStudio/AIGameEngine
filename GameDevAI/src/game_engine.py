# game_engine.py
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from data_class import PipelineOutput
from utils import ensure_game_payload
from instructions import SYSTEM_INSTRUCTIONS_ONE_CALL

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


def build_user_message(user_prompt: str) -> str:
    return (
        "Create a complete, playable browser game from this idea. "
        "Choose the most fitting genre/mechanics based on the prompt. "
        "Keep it self-contained (inline CSS/JS) and accessible. "
        "Return STRICT JSON as per schema.\n\n"
        f"USER_IDEA:\n{user_prompt}"
    )


def generate_game(user_prompt: str, model: str = DEFAULT_MODEL) -> PipelineOutput:
    """
    Core pipeline: calls the model once and returns (title, summary, html).
    """
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Put it in your environment or a .env file.")

    client = OpenAI(api_key=api_key)

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
    # Optionally write the HTML for quick preview:
    out_path = "index.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.html)
    print(f"Open   : {os.path.abspath(out_path)}\n")
