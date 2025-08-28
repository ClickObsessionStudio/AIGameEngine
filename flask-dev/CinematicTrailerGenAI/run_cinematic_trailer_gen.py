# File: run_cinematic_trailer_gen.py

import os
import sys
import argparse
from pathlib import Path
from typing import Any

# Add the src directory to the system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from generate_cinematic_trailer import generate_cinematic_trailer
from video_utils import resize_video_to_vertical

def log(msg: str) -> None:
    print(f"[trailer_gen] {msg}", flush=True)

def extract_trailer_output(res: Any) -> Path:
    # ... (this function remains unchanged)
    if isinstance(res, (str, Path)):
        return Path(res)
    if isinstance(res, dict):
        p = res.get("video_path") or res.get("video") or res.get("path") or res.get("mp4_path") or res.get("output_path")
        if p:
            return Path(p)
    raise ValueError("Could not interpret CinematicTrailerGenAI output. Expect a video path (mp4).")

def run_trailer_step(
    game_summary: str,
    output_dir: str,
    video_model: str,
    video_duration: int,
    video_resolution: str,
    output_filename: str
) -> Path:
    # ... (this function remains unchanged)
    log("Starting cinematic trailer generation...")
    output_path = os.path.join(output_dir, output_filename)
    
    res = generate_cinematic_trailer(
        prompt=game_summary,
        model=video_model,
        duration=video_duration,
        resolution=video_resolution,
        output_path=output_path
    )
    
    video_path = extract_trailer_output(res)
    log(f"Trailer generated at: {video_path}")
    return video_path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate or edit a cinematic video trailer.")
    
    # --- MODIFICATION: Added an input group for clarity ---
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", type=str, help="The prompt to generate the video from.")
    group.add_argument("--input", type=str, help="Path to an existing video file to resize (skips generation).")

    # --- Generation-specific arguments ---
    parser.add_argument("--duration", type=int, default=10, help="Video duration in seconds (generation only).")
    parser.add_argument("--resolution", type=str, default="1080P", choices=["512P", "768P", "1080P"], help="Video resolution preset for the API (generation only).")
    parser.add_argument("--model", type=str, default="MiniMax-Hailuo-02", help="The video generation model to use (generation only).")
    parser.add_argument("--output_dir", type=str, default=os.path.join(os.getcwd(), "generated_media"), help="The directory to save the output video (generation only).")
    parser.add_argument("--output_filename", type=str, default="game_trailer.mp4", help="The name of the output video file (generation only).")
    
    # --- Resizing arguments (for both modes) ---
    parser.add_argument(
        "--resize_mode", 
        type=str, 
        choices=["none", "crop", "pad", "all"], 
        default="none", 
        help="Resize action. 'crop' cuts sides, 'pad' adds black bars, 'all' does both."
    )
    
    args = parser.parse_args()

    # --- MODIFICATION: Add validation for edit mode ---
    if args.input and not os.path.exists(args.input):
        sys.exit(f"Error: Input file not found: {args.input}")
    if args.input and args.resize_mode == 'none':
        parser.error('Error: --resize_mode must be "crop", "pad", or "all" when using --input.')

    try:
        base_video_path = None
        # --- MODIFICATION: Conditional logic for generate vs. edit mode ---
        if args.input:
            # --- EDIT MODE ---
            log(f"Loading existing video: {args.input}")
            base_video_path = Path(args.input)
        else:
            # --- GENERATE MODE ---
            base_video_path = run_trailer_step(
                game_summary=args.prompt,
                output_dir=args.output_dir,
                video_model=args.model,
                video_duration=args.duration,
                video_resolution=args.resolution,
                output_filename=args.output_filename
            )

        # --- RESIZING LOGIC (common to both modes) ---
        if args.resize_mode == "crop":
            resize_video_to_vertical(base_video_path, mode="crop")
        elif args.resize_mode == "pad":
            resize_video_to_vertical(base_video_path, mode="pad")
        elif args.resize_mode == "all":
            log("Resizing to both 'crop' and 'pad' versions...")
            resize_video_to_vertical(base_video_path, mode="crop")
            resize_video_to_vertical(base_video_path, mode="pad")

        if args.input:
            print(f"\n✅ Processing complete. Resized files saved in the same directory as the input video.")
        else:
            print(f"\n✅ Processing complete. See generated files in '{args.output_dir}'.")

    except Exception as e:
        print(f"\n⚠️ An error occurred: {e}")