# File: AI/CinematicTrailerGenAI/src/generate_cinematic_trailer.py

import os
import time
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
# This assumes your .env file is in the AI directory, two levels up
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

# --- Global Configurations (loaded from .env) ---
API_KEY = os.getenv("HAILUO_API_KEY")
GROUP_ID = os.getenv("HAILUO_GROUP_ID")

def create_video_task(prompt: str, model: str, duration: int, resolution: str):
    """Submits the video generation task and returns the task ID."""
    if not API_KEY or not GROUP_ID:
        print("🛑 Error: API_KEY and GROUP_ID must be set in your .env file.")
        return None

    print("🚀 Step 1: Submitting video generation task...")
    
    url = "https://api.minimax.io/v1/video_generation"
    
    payload = json.dumps({
      "prompt": prompt,
      "model": model,
      "duration": duration,
      "resolution": resolution
    })
    
    headers = {
      'Authorization': f'Bearer {API_KEY}',
      'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        response_data = response.json()
        
        if response_data.get("base_resp", {}).get("status_code") != 0:
            error_msg = response_data.get("base_resp", {}).get("status_msg", "Unknown error")
            print(f"❌ API Error: {error_msg}")
            return None

        task_id = response_data['task_id']
        print(f"✅ Task submitted successfully! Task ID: {task_id}")
        return task_id
    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP Request failed: {e}")
        return None

def poll_task_status(task_id: str) -> str:
    """Checks the task status until it's complete and returns the file ID."""
    print("\n⏳ Step 2: Polling for task status (checking every 10 seconds)...")
    
    url = f"https://api.minimax.io/v1/query/video_generation?task_id={task_id}"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    while True:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            
            status = response_data.get('status')
            print(f"   Current status: {status}...")

            if status == 'Success':
                print("✅ Generation successful!")
                return response_data.get('file_id')
            elif status == 'Fail':
                print("❌ Generation failed.")
                return None
            elif status not in ['Queueing', 'Preparing', 'Processing']:
                 print(f"❓ Unknown status received: {status}")
                 return None

            time.sleep(10)
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTP Request failed during polling: {e}")
            return None

def download_video(file_id: str, output_path: str) -> str:
    """Retrieves the download URL, saves the video file, and returns the saved path."""
    print("\n📥 Step 3: Downloading video...")
    
    url = f"https://api.minimax.io/v1/files/retrieve?GroupId={GROUP_ID}&file_id={file_id}"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response_data = response.json()

        download_url = response_data.get('file', {}).get('download_url')
        if not download_url:
            print("❌ Could not find download URL in the response.")
            return None

        print(f"   Download URL received. Fetching video data...")
        video_data = requests.get(download_url).content
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(video_data)
        
        print(f"🎉 Video saved successfully as '{output_path}'!")
        return output_path

    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to download video: {e}")
        return None

def generate_cinematic_trailer(
    prompt: str,
    model: str = "MiniMax-Hailuo-02",
    duration: int = 6,
    resolution: str = "1080P",
    output_path: str = "generated_video.mp4"
) -> str:
    """
    Public function to generate a video from a prompt using the Minimax Hailuo-02 model.
    """
    if not API_KEY or not GROUP_ID:
        raise RuntimeError("API_KEY and GROUP_ID must be set in the environment (.env).")

    task_id = create_video_task(prompt=prompt, model=model, duration=duration, resolution=resolution)
    if not task_id:
        raise RuntimeError("Failed to create video generation task.")
    
    file_id = poll_task_status(task_id)
    if not file_id:
        raise RuntimeError("Video generation failed or did not return a file_id.")
    
    saved_path = download_video(file_id, output_path=output_path)
    if not saved_path:
        raise RuntimeError("Failed to download generated video.")
        
    return saved_path


if __name__ == '__main__':
    # Define default values for standalone run
    DEFAULT_PROMPT = "Eating ramen in an anime style in a classic restaurant, highly detailed, cinematic lighting, 8k"
    DEFAULT_MODEL = "MiniMax-Hailuo-02"
    DEFAULT_DURATION = 6
    DEFAULT_RESOLUTION = "720"
    DEFAULT_OUTPUT_PATH = "output/ramen.mp4"
    
    # Run the function with default values
    print("Running as a standalone script...")
    try:
        path = generate_cinematic_trailer(
            prompt=DEFAULT_PROMPT,
            model=DEFAULT_MODEL,
            duration=DEFAULT_DURATION,
            resolution=DEFAULT_RESOLUTION,
            output_path=DEFAULT_OUTPUT_PATH
        )
        print(f"\n✅ Video generation complete! Video saved at: {path}")
    except RuntimeError as e:
        print(f"\n⚠️ An error occurred: {e}")