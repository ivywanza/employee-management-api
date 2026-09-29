import os
import uuid
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

ONBOARDING_BUCKET = "onboarding-documents"
HUB_BUCKET = "hub-documents"


def upload_file(bucket: str, folder: str, filename: str, content: bytes, content_type: str) -> str:
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    key = f"{folder}/{uuid.uuid4()}.{ext}"
    supabase.storage.from_(bucket).upload(key, content, {"content-type": content_type})
    return key


def get_signed_url(bucket: str, key: str, expires_in: int = 300) -> str:
    result = supabase.storage.from_(bucket).create_signed_url(key, expires_in)
    return result.get("signedURL") or result.get("signed_url")