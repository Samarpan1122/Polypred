"""S3 service - scoped upload/download utilities for user data and artefacts."""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("s3", region_name=settings.AWS_REGION)
    return _client


def _safe_owner(owner_id: str | int | None) -> str:
    raw = str(owner_id or "anonymous").strip().lower()
    safe = re.sub(r"[^a-z0-9._-]", "-", raw)
    safe = re.sub(r"-+", "-", safe).strip("-.")
    return safe or "anonymous"


def _encryption_args() -> dict[str, Any]:
    # Enforce AWS S3-managed encryption (SSE-S3) for all uploads.
    return {"ServerSideEncryption": "AES256"}


def _user_prefix(owner_id: str | int | None) -> str:
    return f"users/{_safe_owner(owner_id)}/"


def _user_prefixes(owner_id: str | int | None) -> dict[str, str]:
    owner = _safe_owner(owner_id)
    return {
        "datasets": f"users/{owner}/datasets/",
        "models": f"users/{owner}/models/",
        "results": f"users/{owner}/results/",
        "requests": f"users/{owner}/requests/",
    }


def ensure_user_prefixes(owner_id: str | int | None) -> dict[str, str]:
    prefixes = _user_prefixes(owner_id)
    client = _get_client()
    for prefix in prefixes.values():
        client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=prefix,
            Body=b"",
            **_encryption_args(),
        )
    return prefixes


def get_encryption_posture() -> dict[str, Any]:
    args = _encryption_args()
    return {
        "mode": args.get("ServerSideEncryption", "AES256"),
        "bucket_key_enabled": False,
    }


def download_file(s3_key: str, local_path: str | Path) -> Path:
    """Download *s3_key* from the configured bucket → local_path."""
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists():
        return local_path  # cache hit
    _get_client().download_file(settings.S3_BUCKET, s3_key, str(local_path))
    return local_path


def upload_bytes(data: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
    _get_client().put_object(
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        Body=data,
        ContentType=content_type,
        **_encryption_args(),
    )
    return s3_key


def upload_json(payload: dict[str, Any], s3_key: str) -> str:
    return upload_bytes(
        json.dumps(payload, default=str, indent=2).encode("utf-8"),
        s3_key,
        content_type="application/json",
    )


def upload_user_file(local_path: str | Path, user_id: int, filename: str) -> str:
    """Upload a user file under the user's scoped dataset prefix."""
    owner = _safe_owner(user_id)
    s3_key = f"users/{owner}/datasets/{filename}"
    _get_client().upload_file(
        str(local_path), 
        settings.S3_BUCKET, 
        s3_key,
        ExtraArgs=_encryption_args(),
    )
    return s3_key


def upload_user_model(local_path: str | Path, user_id: int, model_name: str) -> str:
    """Upload a trained model artefact under the user's scoped model prefix."""
    owner = _safe_owner(user_id)
    s3_key = f"users/{owner}/models/{model_name}"
    _get_client().upload_file(
        str(local_path), 
        settings.S3_BUCKET, 
        s3_key,
        ExtraArgs=_encryption_args(),
    )
    return s3_key


def list_user_files(
    owner_id: str | int | None,
    section: str = "all",
    max_keys: int = 500,
) -> list[dict[str, Any]]:
    prefixes = _user_prefixes(owner_id)
    allowed_sections = {"datasets", "models", "results", "requests"}
    targets = [section] if section in allowed_sections else ["datasets", "models", "results", "requests"]
    client = _get_client()
    budget = max(1, min(int(max_keys), 1000))

    files: list[dict[str, Any]] = []
    for target in targets:
        if len(files) >= budget:
            break
        prefix = prefixes[target]
        token = None
        while True:
            remaining = budget - len(files)
            if remaining <= 0:
                break
            kwargs: dict[str, Any] = {
                "Bucket": settings.S3_BUCKET,
                "Prefix": prefix,
                "MaxKeys": min(remaining, 1000),
            }
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)

            for obj in resp.get("Contents", []):
                key = obj.get("Key", "")
                if key.endswith("/"):
                    continue
                last_modified = obj.get("LastModified")
                last_modified_iso = (
                    last_modified.isoformat() if isinstance(last_modified, datetime) else None
                )
                files.append(
                    {
                        "key": key,
                        "name": key.split("/")[-1],
                        "section": target,
                        "size": obj.get("Size", 0),
                        "etag": str(obj.get("ETag", "")).strip('"'),
                        "last_modified": last_modified_iso,
                        "storage_class": obj.get("StorageClass", "STANDARD"),
                        "encryption": "AES256",
                    }
                )
                if len(files) >= budget:
                    break

            if len(files) >= budget or not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")

    files.sort(key=lambda item: item.get("last_modified") or "", reverse=True)
    return files[:budget]


def create_user_download_url(owner_id: str | int | None, s3_key: str, expires_in: int | None = None) -> str:
    owner_prefix = _user_prefix(owner_id)
    if not s3_key.startswith(owner_prefix):
        raise ValueError("Requested key does not belong to this user")

    ttl = expires_in if expires_in is not None else settings.STORAGE_PRESIGN_TTL_SECONDS
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
        ExpiresIn=max(30, min(int(ttl), 3600)),
    )


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


def delete_prefix(prefix: str) -> int:
    """Delete all objects under a prefix. Returns deleted object count."""
    client = _get_client()
    deleted = 0
    token = None
    while True:
        kwargs: dict[str, Any] = {
            "Bucket": settings.S3_BUCKET,
            "Prefix": prefix,
        }
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        keys = [{"Key": obj["Key"]} for obj in resp.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket=settings.S3_BUCKET, Delete={"Objects": keys})
            deleted += len(keys)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return deleted
