# AI/flask-dev/TrailerUploader/YTShorts/upload_yt_shorts.py
"""
Minimal YouTube uploader (YouTube Data API v3)
...
"""

import argparse
import os
import sys
import json
from typing import List, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
# In a serverless environment, only /tmp is writable.
# We define paths at the top for clarity.
TOKEN_PATH = "/tmp/token.json" if os.getenv("VERCEL") else "token.json"
CLIENT_SECRETS_FILE = "client_secret.json"
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


def get_youtube_client():
    creds = None
    
    # --- Vercel/Environment Variable Authentication ---
    # This is the primary method for production environments.
    if os.getenv("VERCEL"):
        required_vars = [
            "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_TOKEN", 
            "YT_REFRESH_TOKEN", "YT_TOKEN_URI", "YT_SCOPES"
        ]
        # Ensure all required variables are present
        if all(os.getenv(var) for var in required_vars):
            try:
                creds = Credentials(
                    token=os.getenv("YT_TOKEN"),
                    refresh_token=os.getenv("YT_REFRESH_TOKEN"),
                    token_uri=os.getenv("YT_TOKEN_URI"),
                    client_id=os.getenv("YT_CLIENT_ID"),
                    client_secret=os.getenv("YT_CLIENT_SECRET"),
                    scopes=os.getenv("YT_SCOPES").split(',')
                )
                # Refresh the token if it's expired
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            except Exception as e:
                print(f"Error creating credentials from environment variables: {e}")
                sys.exit("FATAL: Failed to initialize YouTube credentials on Vercel.")
        else:
            sys.exit("FATAL: YouTube authentication environment variables are not set on Vercel.")
    
    # --- Local File-Based Authentication ---
    # This block runs only if not on Vercel.
    else:
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CLIENT_SECRETS_FILE):
                    sys.exit(
                        f"Missing {CLIENT_SECRETS_FILE}. This is required for the initial local authentication."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                creds = flow.run_local_server(port=0, prompt="consent")
            
            # Save the credentials for the next run
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())

    # If after all methods, credentials are not available, exit.
    if not creds:
        sys.exit("FATAL: Could not obtain YouTube credentials.")

    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)


def upload_video(
    youtube,
    file_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]],
    privacy_status: str = "private",
):
    body = {
        "snippet": {
            "title": title,
            "description": description,
        },
        "status": {"privacyStatus": privacy_status},
    }
    if tags:
        body["snippet"]["tags"] = tags

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print("Starting upload...")
    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
    except HttpError as e:
        print(f"HTTP Error: {e}")

    if response and "id" in response:
        video_id = response["id"]
        print("Upload complete ✅")
        print(f"Video ID: {video_id}")
        print(f"Watch URL: https://youtu.be/{video_id}")
        return video_id
    else:
        print("The upload failed.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Upload a video to YouTube (minimal).")
    parser.add_argument("video", help="Path to the video file (e.g., /path/to/video.mp4)")
    parser.add_argument("--title", help="Video title (default: filename)")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument(
        "--tags",
        default="",
        help='Comma-separated tags, e.g. "tag1,tag2"',
    )
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default="private",
        help="Privacy status (default: private)",
    )

    args = parser.parse_args()
    if not os.path.exists(args.video):
        sys.exit(f"File not found: {args.video}")

    title = args.title or os.path.splitext(os.path.basename(args.video))[0]
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    youtube = get_youtube_client()
    upload_video(
        youtube,
        file_path=args.video,
        title=title,
        description=args.description,
        tags=tags or None,
        privacy_status=args.privacy,
    )


if __name__ == "__main__":
    main()