# supabase_client.py
import os
from supabase import create_client, Client

def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # server-side only
    return create_client(url, key)

def public_url(path: str) -> str:
    # For public buckets you can derive the URL directly:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    return f"{base}/storage/v1/object/public/{path.lstrip('/')}"
