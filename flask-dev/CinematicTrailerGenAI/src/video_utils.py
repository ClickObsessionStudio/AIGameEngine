# flask-dev/CinematicTrailerGenAI/src/video_utils.py

import ffmpeg
import sys
from pathlib import Path
from typing import Tuple

def _get_video_dims(video_path: Path) -> Tuple[int, int]:
    """Gets the width and height of a video."""
    try:
        probe = ffmpeg.probe(str(video_path))
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            return int(video_stream['width']), int(video_stream['height'])
        raise ValueError("Could not find video stream in file.")
    except ffmpeg.Error as e:
        print(e.stderr, file=sys.stderr)
        raise

def resize_video_to_vertical(video_path: Path, mode: str, target_aspect_ratio: str = "9:16") -> Path:
    """Resizes a video to a vertical aspect ratio using ffmpeg-python."""
    if mode not in ("crop", "pad"):
        raise ValueError("Mode must be either 'crop' or 'pad'")
    
    # --- The output path will be created by ffmpeg ---
    out_path = video_path.with_name(f"{video_path.stem}_{mode}.mp4")
    
    # --- Get video dimensions ---
    w, h = _get_video_dims(video_path)
    
    # --- Build the ffmpeg command based on the mode ---
    if mode == "crop":
        print(f"⚙️ Cropping video to {target_aspect_ratio} with ffmpeg-python...")
        (
            ffmpeg
            .input(str(video_path))
            .filter('crop', f'ih*{target_aspect_ratio}:{h}')
            .output(str(out_path), acodec='copy')
            .run(overwrite_output=True)
        )
    else: # mode == "pad"
        print(f"⚙️ Padding video to {target_aspect_ratio} with ffmpeg-python...")
        (
            ffmpeg
            .input(str(video_path))
            .filter('scale', f'iw*min(1080/iw,1920/ih):-1')
            .filter('pad', '1080', '1920', '-1', '-1', 'black')
            .output(str(out_path), acodec='copy')
            .run(overwrite_output=True)
        )
        
    print(f"✅ {mode.capitalize()} video saved at: {out_path}")
    return out_path