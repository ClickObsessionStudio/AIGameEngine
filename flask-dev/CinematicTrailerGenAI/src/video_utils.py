# src/video_utils.py
from pathlib import Path
from typing import Tuple

# v2 import (preferred). Fallback to v1 if needed.
try:
    from moviepy import VideoFileClip, CompositeVideoClip, ColorClip
    MOVIEPY_V2 = True
except Exception:  # MoviePy v1.x
    from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip
    MOVIEPY_V2 = False

def _parse_ratio(r: str) -> float:
    try:
        a, b = map(int, r.split(":"))
        return a / b
    except Exception as e:
        raise ValueError(f"Invalid aspect ratio {r!r}. Use e.g. '9:16'.") from e

def _even(x: int) -> int:
    return x if x % 2 == 0 else x + 1

def _get_video_dims(p: Path) -> Tuple[int, int]:
    with VideoFileClip(str(p)) as clip:
        return int(clip.w), int(clip.h)

def resize_video_to_vertical(video_path: Path, mode: str, target_aspect_ratio: str = "9:16") -> Path:
    if mode not in ("crop", "pad"):
        raise ValueError("Mode must be either 'crop' or 'pad'")
    return _crop_video(video_path, target_aspect_ratio) if mode == "crop" else _pad_video(video_path, target_aspect_ratio)

def _crop_video(video_path: Path, target_aspect_ratio: str) -> Path:
    print(f"⚙️ Cropping video to {target_aspect_ratio} with MoviePy...")
    ar = _parse_ratio(target_aspect_ratio)
    out = video_path.with_name(f"{video_path.stem}_cropped.mp4")

    with VideoFileClip(str(video_path)) as clip:
        w, h = clip.w, clip.h
        cur_ar = w / h
        if cur_ar > ar:
            # too wide → crop width
            target_w = _even(int(h * ar))
            x1 = (w - target_w) // 2
            x2 = x1 + target_w
            clip2 = clip.cropped(x1=x1, y1=0, x2=x2, y2=h) if MOVIEPY_V2 else clip.crop(x1=x1, y1=0, x2=x2, y2=h)
        else:
            # too tall → crop height
            target_h = _even(int(w / ar))
            y1 = (h - target_h) // 2
            y2 = y1 + target_h
            clip2 = clip.cropped(x1=0, y1=y1, x2=w, y2=y2) if MOVIEPY_V2 else clip.crop(x1=0, y1=y1, x2=w, y2=y2)

        clip2.write_videofile(str(out), codec="libx264", audio_codec="aac", preset="medium", threads=0)
    print(f"✅ Cropped video saved at: {out}")
    return out

def _pad_video(video_path: Path, target_aspect_ratio: str) -> Path:
    print(f"⚙️ Padding video to {target_aspect_ratio} with MoviePy...")
    ar = _parse_ratio(target_aspect_ratio)
    out = video_path.with_name(f"{video_path.stem}_padded.mp4")

    with VideoFileClip(str(video_path)) as clip:
        w, h = clip.w, clip.h
        cur_ar = w / h
        if cur_ar > ar:
            # need more height (letterbox)
            target_w, target_h = w, _even(int(w / ar))
        else:
            # need more width (pillarbox)
            target_w, target_h = _even(int(h * ar)), h

        # center the original on a black canvas of target size
        clip_centered = clip.with_position("center") if MOVIEPY_V2 else clip.set_position("center")
        bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).with_duration(clip.duration) if MOVIEPY_V2 \
             else ColorClip(size=(target_w, target_h), color=(0, 0, 0)).set_duration(clip.duration)
        comp = CompositeVideoClip([bg, clip_centered], size=(target_w, target_h))
        comp.write_videofile(str(out), codec="libx264", audio_codec="aac", preset="medium", threads=0)

    print(f"✅ Padded video saved at: {out}")
    return out
