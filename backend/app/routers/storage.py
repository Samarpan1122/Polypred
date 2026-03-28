"""Storage health and setup endpoints for S3-backed user artifacts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.services import s3_service
from app.services.dataset_service import list_datasets

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
    owner_slug = s3_service._safe_owner(owner_id)
    files = []
    warnings: list[str] = []

    # Always surface uploaded datasets instantly from local metadata.
    if section in ("all", "datasets"):
        try:
            local_sets = list_datasets(owner_id=owner_id)
            for ds in local_sets:
                ds_name = ds.get("filename") or ds.get("name") or f"dataset_{ds.get('id', '')}.csv"
                files.append(
                    {
                        "asset_id": ds.get("id"),
                        "asset_type": "dataset",
                        "key": ds.get("s3_key") or f"users/{owner_slug}/datasets/{ds.get('id')}/{ds_name}",
                        "name": ds_name,
                        "section": "datasets",
                        "size": 0,
                        "etag": "",
                        "last_modified": ds.get("uploaded_at"),
                        "storage_class": "S3" if ds.get("s3_synced") else "LOCAL",
                        "encryption": "AES256",
                        "downloadable": bool(ds.get("s3_synced") and ds.get("s3_key")),
                        "is_public": bool(ds.get("is_public", False)),
                        "public_share_status": ds.get("public_share_status", "private"),
                    }
                )
        except Exception as exc:
            warnings.append(f"local datasets unavailable: {exc}")

    # Query S3 only for sections that require remote listing.
    s3_targets: list[str]
    if section == "all":
        s3_targets = ["models", "results", "requests"]
    elif section == "datasets":
        s3_targets = []
    else:
        s3_targets = [section]

    remaining = max(0, max_keys - len(files))
    for target in s3_targets:
        if remaining <= 0:
            break
        try:
            part = s3_service.list_user_files(owner_id=owner_id, section=target, max_keys=remaining)
            for item in part:
                item["downloadable"] = True
                item["asset_id"] = item.get("key")
                item["asset_type"] = "model" if item.get("section") == "models" else item.get("section")
                item["is_public"] = bool(item.get("is_public", False))
                item["public_share_status"] = item.get("public_share_status", "private")
            files.extend(part)
            remaining = max(0, max_keys - len(files))
        except Exception as exc:
            warnings.append(f"s3 {target} unavailable: {exc}")

    files.sort(key=lambda item: item.get("last_modified") or "", reverse=True)
    files = files[:max_keys]

    return {
        "ok": True,
        "owner": owner_id,
        "section": section,
        "count": len(files),
        "encryption": s3_service.get_encryption_posture(),
        "files": files,
        "warnings": warnings,
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
