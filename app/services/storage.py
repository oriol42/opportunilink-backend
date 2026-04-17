# app/services/storage.py
# Handles all file uploads/deletes with Supabase Storage.
# Supabase Storage works like S3 — files are organized in "buckets".
# Our bucket: "documents" — one folder per user (user_id/filename)

import httpx
from app.config import settings

BUCKET = "documents"
STORAGE_URL = f"{settings.supabase_url}/storage/v1"

HEADERS = {
    "Authorization": f"Bearer {settings.supabase_key}",
    "apikey": settings.supabase_key,
}


async def upload_file(
    file_bytes: bytes,
    file_path: str,       # e.g. "user_uuid/cv_2026.pdf"
    content_type: str,    # e.g. "application/pdf"
) -> str:
    """
    Uploads a file to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    url = f"{STORAGE_URL}/object/{BUCKET}/{file_path}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            content=file_bytes,
            headers={
                **HEADERS,
                "Content-Type": content_type,
            },
        )

    if response.status_code not in (200, 201):
        raise Exception(f"Storage upload failed: {response.text}")

    # Return the public URL to store in DB
    public_url = f"{STORAGE_URL}/object/public/{BUCKET}/{file_path}"
    return public_url


async def delete_file(file_path: str) -> bool:
    """
    Deletes a file from Supabase Storage.
    Returns True if successful.
    """
    url = f"{STORAGE_URL}/object/{BUCKET}/{file_path}"

    async with httpx.AsyncClient() as client:
        response = await client.delete(url, headers=HEADERS)

    return response.status_code in (200, 204)
