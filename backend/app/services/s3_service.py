"""S3 service — download / upload model artefacts."""

import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("s3", region_name=settings.AWS_REGION)
    return _client


def download_file(s3_key: str, local_path: str | Path) -> Path:
    """Download *s3_key* from the configured bucket → local_path."""
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists():
        return local_path  # cache hit
    _get_client().download_file(settings.S3_BUCKET, s3_key, str(local_path))
    return local_path


def upload_file(local_path: str | Path, s3_key: str) -> str:
    _get_client().upload_file(str(local_path), settings.S3_BUCKET, s3_key)
    return f"s3://{settings.S3_BUCKET}/{s3_key}"


def file_exists(s3_key: str) -> bool:
    try:
        _get_client().head_object(Bucket=settings.S3_BUCKET, Key=s3_key)
        return True
    except ClientError:
        return False


def list_models() -> list[str]:
    """List all model weight files under the configured prefix."""
    resp = _get_client().list_objects_v2(
        Bucket=settings.S3_BUCKET, Prefix=settings.S3_MODEL_PREFIX
    )
    return [obj["Key"] for obj in resp.get("Contents", [])]
