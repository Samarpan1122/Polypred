"""Storage health and setup endpoints for S3-backed user artifacts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.services import s3_service

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.get("/health")
def storage_health():
    client = s3_service._get_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
        return {
            "ok": True,
            "bucket": settings.S3_BUCKET,
            "region": settings.AWS_REGION,
            "encryption": s3_service.get_encryption_posture(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "bucket": settings.S3_BUCKET,
            "region": settings.AWS_REGION,
            "error": str(exc),
            "encryption": s3_service.get_encryption_posture(),
        }


@router.post("/prepare")
def prepare_user_storage(owner_id: str = Query("anonymous")):
    prefixes = s3_service.ensure_user_prefixes(owner_id)
    return {"ok": True, "owner": owner_id, "prefixes": prefixes}


@router.get("/user-files")
def list_user_files(
    owner_id: str = Query(..., min_length=1),
    section: str = Query("all", pattern="^(all|datasets|models|results|requests)$"),
    max_keys: int = Query(200, ge=1, le=1000),
):
    files = s3_service.list_user_files(owner_id=owner_id, section=section, max_keys=max_keys)
    return {
        "ok": True,
        "owner": owner_id,
        "section": section,
        "count": len(files),
        "encryption": s3_service.get_encryption_posture(),
        "files": files,
    }


@router.get("/download-url")
def get_user_download_url(
    owner_id: str = Query(..., min_length=1),
    key: str = Query(..., min_length=5),
    expires_in: int = Query(300, ge=30, le=3600),
):
    try:
        url = s3_service.create_user_download_url(owner_id=owner_id, s3_key=key, expires_in=expires_in)
        return {"ok": True, "key": key, "expires_in": expires_in, "url": url}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create download URL: {exc}") from exc
