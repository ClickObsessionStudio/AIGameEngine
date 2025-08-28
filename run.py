# File: AI/main.py

import os
import sys

# Adjust the path to correctly import from the 'src' directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'CinematicTrailerGenAI', 'src')))

# Now import the function
from generate_cinematic_trailer import generate_cinematic_trailer

def main():
    # Define all possible options here
    user_prompt = "Eating ramen in an anime style in a classic restaurant, highly detailed, cinematic lighting, 8k"
    video_model = "MiniMax-Hailuo-02"
    video_duration = 10
    video_resolution = "512P"
    
    # Define the output path, including the directory
    video_output_path = os.path.join(os.path.dirname(__file__), "generated_media", "robot_detective.mp4")

    print("Starting video generation from main.py...")
    try:
        video_path = generate_cinematic_trailer(
            prompt=user_prompt,
            model=video_model,
            duration=video_duration,
            resolution=video_resolution,
            output_path=video_output_path
        )
        print(f"🎬 Video generation complete! Video saved at: {video_path}")
    except RuntimeError as e:
        print(f"⚠️ An error occurred during video generation: {e}")

if __name__ == "__main__":
    main()