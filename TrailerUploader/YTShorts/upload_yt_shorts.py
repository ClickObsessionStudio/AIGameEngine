#!/usr/bin/env python3
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
CLIENT_SECRETS_FILE = "client_secret.json"
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


def get_youtube_client():
    creds = None
    
    # --- Vercel/Environment Variable Authentication ---
    # This block will run if the app is on Vercel or if token.json is missing
    if os.getenv("VERCEL") or not os.path.exists("token.json"):
        # Check for all required environment variables
        required_vars = [
            "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_TOKEN", 
            "YT_REFRESH_TOKEN", "YT_TOKEN_URI", "YT_SCOPES"
        ]
        if all(os.getenv(var) for var in required_vars):
            creds = Credentials(
                token=os.getenv("YT_TOKEN"),
                refresh_token=os.getenv("YT_REFRESH_TOKEN"),
                token_uri=os.getenv("YT_TOKEN_URI"),
                client_id=os.getenv("YT_CLIENT_ID"),
                client_secret=os.getenv("YT_CLIENT_SECRET"),
                scopes=os.getenv("YT_SCOPES").split(',') # Scopes are comma-separated in env var
            )
        else:
            # If running on Vercel without env vars, it's a fatal error
            if os.getenv("VERCEL"):
                sys.exit("FATAL: YouTube authentication environment variables are not set on Vercel.")
            # Fallback to local file-based flow if not on Vercel
            pass 
    
    # --- Local File-Based Authentication ---
    # This block runs if the environment variable method didn't create credentials
    if not creds:
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    # --- Token Refresh/Creation Logic ---
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # This part is for local development first-time setup
            if not os.path.exists(CLIENT_SECRETS_FILE):
                sys.exit(
                    f"Missing {CLIENT_SECRETS_FILE}. This is required for the initial local authentication."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
        
        # Save the credentials for the next run (only in local development)
        if not os.getenv("VERCEL"):
            with open("token.json", "w") as token:
                token.write(creds.to_json())

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