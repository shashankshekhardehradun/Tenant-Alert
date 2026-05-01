"""Storage helpers for raw landing files."""

from __future__ import annotations

from pathlib import Path

from google.cloud import storage


def upload_file_to_gcs(local_path: Path, bucket_name: str, blob_name: str) -> str:
    """Upload a local file to Cloud Storage and return its gs:// URI."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(local_path))
    return f"gs://{bucket_name}/{blob_name}"
