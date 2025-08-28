#!/usr/bin/env python3
"""
Pipeline Orchestrator for AIGameEngine

Flow:
    main.py --prompt "...game idea..."
        -> GameDevAI/generate-game.py          (returns game_summary[, public_game_url])
        -> CinematicTrailerGenAI/src/generate_cinematic_trailer.py (returns mp4 path)
        -> TrailerUploader/upload.py          (uploads to platforms; uses mp4 + public_game_url)

This script is defensive: it loads modules from file paths with dashes, tries common
function names, maps argument synonyms, and logs everything.

Usage examples:
  python main.py --prompt "Cozy farming rogue-lite on a floating island"
  python main.py --prompt "Cyberpunk cat detective" --platforms yt ig tt
  python main.py --prompt-file prompt.txt
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# ---------- Paths ----------

REPO_ROOT = Path(__file__).resolve().parent

GAME_GEN_PATH = REPO_ROOT / "GameDevAI" / "generate-game.py"
# Updated path to the new script location and name
TRAILER_GEN_PATH = REPO_ROOT / "CinematicTrailerGenAI" / "src" / "generate_cinematic_trailer.py"
UPLOADER_PATH = REPO_ROOT / "TrailerUploader" / "upload.py"

# ---------- Logging ----------

def log(msg: str) -> None:
    print(f"[main] {msg}", flush=True)

def die(msg: str, code: int = 1) -> None:
    log(f"ERROR: {msg}")
    sys.exit(code)

# ---------- Module loading ----------

def load_module_from_file(py_path: Path, module_name: str):
    if not py_path.exists():
        die(f"Cannot find {py_path}")
    spec = importlib.util.spec_from_file_location(module_name, str(py_path))
    if spec is None or spec.loader is None:
        die(f"Failed to create import spec for {py_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module

def pick_callable(module, candidates: Iterable[str]) -> Tuple[str, Callable[..., Any]]:
    for name in candidates:
        func = getattr(module, name, None)
        if callable(func):
            return name, func
    # If the module itself is callable (rare), use that
    if callable(module):
        return "<module>", module  # type: ignore
    cands = ", ".join(candidates)
    die(f"None of the expected callables found in {module.__name__}. "
        f"Tried: {cands}")
    raise RuntimeError("Unreachable")

# ---------- Argument mapping ----------

# For resilient invocation we map "our" names to many possible parameter names.
SYNONYMS: Dict[str, List[str]] = {
    "prompt": ["prompt", "game_prompt", "idea", "concept", "text", "input_text"],
    "summary": ["summary", "game_summary", "description", "synopsis"],
    "video_path": ["video_path", "video", "filepath", "file", "path", "mp4_path", "output_path"],
    "game_url": ["public_game_url", "game_url", "url", "link", "public_url"],
    "platforms": ["platforms", "targets", "destinations", "channels"],
}

def _first_match(keys: Iterable[str], *candidates: str) -> Optional[str]:
    ks = set(keys)
    for name in candidates:
        if name in ks:
            return name
    return None

def call_best_effort(func: Callable[..., Any], **kwargs) -> Any:
    """
    Call a function with best-effort keyword mapping.
    We inspect the signature and pass only params the function accepts,
    remapping via SYNONYMS. If it takes **kwargs, we pass all mapped.
    """
    sig = inspect.signature(func)
    params = sig.parameters
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

    # Build a mapping from our canonical keys to the callee's parameter names
    mapped: Dict[str, Any] = {}
    for canon_key, value in kwargs.items():
        # if caller didn't provide this value, skip
        if value is None:
            continue

        # direct hit
        if canon_key in params:
            mapped[canon_key] = value
            continue

        # try synonyms
        syns = SYNONYMS.get(canon_key, [])
        target = _first_match(params.keys(), *syns)
        if target:
            mapped[target] = value
            continue

        # if callee has **kwargs, keep original key
        if has_var_kw:
            mapped[canon_key] = value

    # Drop any unknowns if no **kwargs
    if not has_var_kw:
        mapped = {k: v for k, v in mapped.items() if k in params}

    # Finally, try to call. If it fails due to missing required positional-only params,
    # re-raise with a helpful message.
    try:
        return func(**mapped)
    except TypeError as e:
        raise TypeError(
            f"Failed calling {getattr(func, '__name__', str(func))} with kwargs {mapped}. "
            f"Signature: {sig}. Original error: {e}"
        )

# ---------- Result normalization ----------

def extract_game_outputs(res: Any) -> Tuple[str, Optional[str]]:
    """
    Normalize outputs from GameDevAI step.
    We expect (summary, url) OR dict with 'summary'/'game_summary' and optional url,
    OR a plain summary string.
    """
    # (summary, url)
    if isinstance(res, (list, tuple)):
        if len(res) == 0:
            die("Game generator returned an empty tuple/list")
        summary = str(res[0])
        url = str(res[1]) if len(res) > 1 and res[1] is not None else None
        return summary, url

    # dict-like
    if isinstance(res, dict):
        summary = res.get("summary") or res.get("game_summary") or res.get("description") or res.get("synopsis")
        url = res.get("public_game_url") or res.get("game_url") or res.get("url") or res.get("link") or None
        if summary is None:
            die("Game generator returned a dict but no summary-like field was found")
        return str(summary), (str(url) if url else None)

    # plain string
    if isinstance(res, str):
        return res, None

    # unknown type -> try JSON-ish repr and hope it has 'summary'
    try:
        text = json.dumps(res)  # type: ignore
        log(f"Game generator returned unexpected type; JSONified: {text[:120]}...")
    except Exception:
        pass
    die("Could not interpret GameDevAI output. Please ensure it returns a summary (and optionally a public game URL).")
    return "", None  # unreachable

def extract_trailer_output(res: Any) -> Path:
    """
    Normalize output from trailer generator.
    Expect path-like string or dict with video_path.
    """
    if isinstance(res, (str, Path)):
        p = Path(res)
        if not p.exists():
            log(f"WARNING: Trailer path doesn't exist yet: {p} (continuing anyway)")
        return p

    if isinstance(res, dict):
        p = res.get("video_path") or res.get("video") or res.get("path") or res.get("mp4_path") or res.get("output_path")
        if p:
            return Path(p)
    die("Could not interpret CinematicTrailerGenAI output. Expect a video path (mp4).")
    return Path()  # unreachable

# ---------- Steps ----------
# Now that generate_cinematic_trailer.py is a module, we can import it directly.
sys.path.append(str(REPO_ROOT / 'CinematicTrailerGenAI' / 'src'))
from generate_cinematic_trailer import generate_cinematic_trailer

def run_gamedev_step(prompt: str) -> Tuple[str, Optional[str]]:
    log("Loading GameDevAI...")
    mod = load_module_from_file(GAME_GEN_PATH, "generate_game_mod")
    name, fn = pick_callable(mod, ["generate_game", "generate", "main", "run"])
    log(f"Calling GameDevAI.{name}()")
    res = call_best_effort(fn, prompt=prompt)
    summary, url = extract_game_outputs(res)
    log(f"Game summary acquired ({len(summary)} chars). Public URL: {url or 'N/A'}")
    return summary, url

# This function is now simplified to directly call the new generate_cinematic_trailer function.
def run_trailer_step(game_summary: str) -> Path:
    log("Calling CinematicTrailerGenAI...")
    
    # Configure the parameters for the new video generation function
    # You can customize these as needed, perhaps based on the game summary
    # or other CLI arguments.
    video_model = "MiniMax-Hailuo-02"
    video_duration = 10
    video_resolution = "720P"
    video_output_path = REPO_ROOT / "generated_media" / "game_trailer.mp4"
    
    res = generate_cinematic_trailer(
        prompt=game_summary,
        model=video_model,
        duration=video_duration,
        resolution=video_resolution,
        output_path=str(video_output_path)
    )
    
    video_path = extract_trailer_output(res)
    log(f"Trailer generated at: {video_path}")
    return video_path

def run_uploader_step(video_path: Path, game_url: Optional[str], platforms: List[str]) -> Any:
    log("Loading TrailerUploader...")
    mod = load_module_from_file(UPLOADER_PATH, "uploader_mod")
    name, fn = pick_callable(mod, ["upload", "upload_trailer", "main", "run", "orchestrate"])
    log(f"Calling TrailerUploader.{name}() for platforms={platforms}")
    return call_best_effort(fn, video_path=str(video_path), game_url=game_url, platforms=platforms)

# ---------- CLI ----------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGameEngine pipeline runner")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt", type=str, help="Game prompt text")
    g.add_argument("--prompt-file", type=str, help="Path to a text file containing the game prompt")

    parser.add_argument(
        "--platforms",
        nargs="*",
        default=["yt", "ig", "tt"],  # YouTube Shorts, Instagram Reels, TikTok
        help="Platforms to upload to. Any of: yt ig tt. Default: yt ig tt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run generation steps but skip the uploader"
    )
    return parser.parse_args(argv)

def normalize_platforms(raw: Iterable[str]) -> List[str]:
    norm = []
    valid = {"yt", "ig", "tt"}
    for p in raw:
        p = p.lower().strip()
        if p in valid and p not in norm:
            norm.append(p)
    if not norm:
        norm = ["yt", "ig", "tt"]
    return norm

# ---------- Main ----------

def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    # Read prompt
    if args.prompt is not None:
        prompt = args.prompt.strip()
    else:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            die(f"Prompt file not found: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8").strip()

    if not prompt:
        die("Empty prompt provided")

    platforms = normalize_platforms(args.platforms)
    log(f"Starting pipeline. Platforms: {platforms}")

    # 1) GameDevAI
    game_summary, public_url = run_gamedev_step(prompt)

    # 2) CinematicTrailerGenAI
    video_path = run_trailer_step(game_summary)

    # 3) TrailerUploader
    if args.dry_run:
        log("Dry-run enabled; skipping uploader step.")
    else:
        upload_res = run_uploader_step(video_path, public_url, platforms)
        if upload_res is not None:
            try:
                pretty = json.dumps(upload_res, indent=2, ensure_ascii=False)
                log(f"Uploader result:\n{pretty}")
            except Exception:
                log(f"Uploader result: {upload_res}")

    log("Pipeline complete.")

if __name__ == "__main__":
    main()