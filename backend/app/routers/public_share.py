"""Public sharing workflow for datasets and models."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.config import settings
from app.services.dataset_service import DATA_DIR, list_datasets, resolve_dataset_owner
from app.services.model_loader import available_models

router = APIRouter(prefix="/api/public-share", tags=["public-share"])

REQUESTS_DIR = DATA_DIR / "public_share_requests"
REQUESTS_DIR.mkdir(parents=True, exist_ok=True)


def _utcnow() -> str:
    return datetime.utcnow().isoformat()


def _request_path(request_id: str) -> Path:
    return REQUESTS_DIR / f"{request_id}.json"


def _load_request(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_request(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def _is_admin(email: str | None) -> bool:
    return (email or "").strip().lower() in settings.ADMIN_EMAILS


def _require_admin(email: str | None) -> str:
    admin_email = (email or "").strip().lower()
    if not _is_admin(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")
    return admin_email


def _list_request_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(REQUESTS_DIR.glob("*.json")):
        try:
            records.append(_load_request(path))
        except Exception:
            continue
    records.sort(key=lambda item: item.get("submitted_at") or "", reverse=True)
    return records


def _apply_dataset_visibility(record: dict[str, Any]) -> None:
    if record.get("asset_type") != "dataset":
        return

    dataset_id = record.get("asset_id")
    owner_id = record.get("owner_id") or resolve_dataset_owner(dataset_id)
    if not dataset_id or not owner_id:
        return

    meta_path = DATA_DIR / "users" / owner_id / dataset_id / "meta.json"
    if not meta_path.exists():
        return

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(
        {
            "is_public": True,
            "public_share_status": "approved",
            "public_share_approved_at": record.get("reviewed_at"),
            "public_share_request_id": record.get("request_id"),
        }
    )
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def _review_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": record.get("request_id"),
        "asset_type": record.get("asset_type"),
        "asset_id": record.get("asset_id"),
        "asset_name": record.get("asset_name"),
        "owner_id": record.get("owner_id"),
        "owner_email": record.get("owner_email"),
        "requester_name": record.get("requester_name"),
        "institutional_email": record.get("institutional_email"),
        "affiliation": record.get("affiliation"),
        "country": record.get("country"),
        "research_title": record.get("research_title"),
        "research_area": record.get("research_area"),
        "status": record.get("status"),
        "submitted_at": record.get("submitted_at"),
        "reviewed_at": record.get("reviewed_at"),
        "reviewed_by": record.get("reviewed_by"),
        "review_notes": record.get("review_notes", ""),
    }


def _public_catalog_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": record.get("request_id"),
        "asset_type": record.get("asset_type"),
        "asset_id": record.get("asset_id"),
        "asset_name": record.get("asset_name"),
        "owner_id": record.get("owner_id"),
        "requester_name": record.get("requester_name"),
        "affiliation": record.get("affiliation"),
        "country": record.get("country"),
        "research_title": record.get("research_title"),
        "research_area": record.get("research_area"),
        "research_summary": record.get("research_summary"),
        "intended_use": record.get("intended_use"),
        "citation_text": record.get("citation_text", ""),
        "profile_url": record.get("profile_url", ""),
        "submitted_at": record.get("submitted_at"),
        "approved_at": record.get("reviewed_at"),
    }


class PublicShareRequest(BaseModel):
    asset_type: Literal["dataset", "model"]
    asset_id: str = Field(..., min_length=1, max_length=128)
    asset_name: str = Field(..., min_length=1, max_length=255)
    owner_id: str = Field(default="", max_length=255)
    owner_email: str = Field(default="", max_length=255)

    requester_name: str = Field(..., min_length=2, max_length=255)
    institutional_email: EmailStr
    affiliation: str = Field(..., min_length=2, max_length=255)
    department: str = Field(default="", max_length=255)
    position_title: str = Field(default="", max_length=255)
    university_id: str = Field(default="", max_length=128)
    orcid: str = Field(default="", max_length=64)
    country: str = Field(..., min_length=2, max_length=128)
    profile_url: str = Field(default="", max_length=512)

    research_title: str = Field(..., min_length=5, max_length=300)
    research_area: str = Field(..., min_length=3, max_length=200)
    research_summary: str = Field(..., min_length=20, max_length=3000)
    intended_use: str = Field(..., min_length=20, max_length=2000)
    funding_source: str = Field(default="", max_length=300)

    is_external_research_data: bool = False
    external_data_source: str = Field(default="", max_length=512)
    external_data_license: str = Field(default="", max_length=255)
    citation_text: str = Field(default="", max_length=1000)

    ethics_approval_required: bool = False
    ethics_approval_reference: str = Field(default="", max_length=255)

    confirms_data_rights: bool
    confirms_no_pii: bool
    confirms_terms: bool

    additional_notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_conditional_fields(self):
        if self.is_external_research_data:
            if not self.external_data_source.strip():
                raise ValueError("external_data_source is required when external data is used")
            if not self.external_data_license.strip():
                raise ValueError("external_data_license is required when external data is used")
        if self.ethics_approval_required and not self.ethics_approval_reference.strip():
            raise ValueError("ethics_approval_reference is required when ethics approval is required")
        if not (self.confirms_data_rights and self.confirms_no_pii and self.confirms_terms):
            raise ValueError("all required confirmations must be accepted")
        return self


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    review_notes: str = Field(default="", max_length=2000)


@router.post("/requests")
def create_public_share_request(payload: PublicShareRequest):
    request_id = str(uuid.uuid4())[:12]
    now = _utcnow()
    existing = next(
        (
            item
            for item in _list_request_records()
            if item.get("asset_type") == payload.asset_type
            and item.get("asset_id") == payload.asset_id
            and item.get("status") in {"pending_review", "approved"}
        ),
        None,
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This {payload.asset_type} already has an active public-sharing request.",
        )

    owner_id = payload.owner_id.strip().lower() or resolve_dataset_owner(payload.asset_id) or ""
    record = {
        "request_id": request_id,
        "status": "pending_review",
        "submitted_at": now,
        "reviewed_at": None,
        "reviewed_by": None,
        "review_notes": "",
        **payload.model_dump(),
        "owner_id": owner_id,
    }

    _save_request(_request_path(request_id), record)

    return {
        "ok": True,
        "request_id": request_id,
        "status": "pending_review",
        "message": "Public sharing request submitted for admin review.",
    }


@router.get("/requests/{request_id}")
def get_public_share_request(request_id: str):
    path = _request_path(request_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Request not found")
    return _load_request(path)


@router.get("/catalog")
def get_public_catalog():
    approved = [
        _public_catalog_item(record)
        for record in _list_request_records()
        if record.get("status") == "approved"
    ]
    datasets = [item for item in approved if item["asset_type"] == "dataset"]
    models = [item for item in approved if item["asset_type"] == "model"]
    return {
        "ok": True,
        "datasets": datasets,
        "models": models,
        "summary": {
            "datasets": len(datasets),
            "models": len(models),
            "total": len(approved),
        },
    }


@router.get("/admin/requests")
def list_admin_requests(
    admin_email: str = Query(..., min_length=3),
    status: Literal["all", "pending_review", "approved", "rejected"] = Query("all"),
):
    _require_admin(admin_email)
    records = _list_request_records()
    if status != "all":
        records = [record for record in records if record.get("status") == status]
    return {
        "ok": True,
        "requests": records,
        "summary": {
            "total": len(records),
            "pending_review": sum(1 for item in records if item.get("status") == "pending_review"),
            "approved": sum(1 for item in records if item.get("status") == "approved"),
            "rejected": sum(1 for item in records if item.get("status") == "rejected"),
        },
    }


@router.get("/admin/overview")
def get_admin_overview(admin_email: str = Query(..., min_length=3)):
    _require_admin(admin_email)
    records = _list_request_records()
    user_dirs = DATA_DIR / "users"
    dataset_owner_dirs = [
        item for item in user_dirs.iterdir()
        if item.is_dir()
    ] if user_dirs.exists() else []
    dataset_count = sum(len(list_datasets(owner_id=owner_dir.name)) for owner_dir in dataset_owner_dirs)
    unique_requesters = {
        record.get("institutional_email", "").strip().lower()
        for record in records
        if record.get("institutional_email")
    }
    approved = [record for record in records if record.get("status") == "approved"]
    approved_dataset_count = sum(1 for record in approved if record.get("asset_type") == "dataset")
    approved_model_count = sum(1 for record in approved if record.get("asset_type") == "model")

    return {
        "ok": True,
        "admin_emails": settings.ADMIN_EMAILS,
        "stats": {
            "users": max(len(dataset_owner_dirs), len(unique_requesters)),
            "datasets": dataset_count,
            "models": len(available_models()),
            "share_requests": len(records),
            "pending_requests": sum(1 for record in records if record.get("status") == "pending_review"),
            "approved_requests": len(approved),
            "rejected_requests": sum(1 for record in records if record.get("status") == "rejected"),
            "public_datasets": approved_dataset_count,
            "public_models": approved_model_count,
        },
        "recent_requests": [_review_summary(record) for record in records[:8]],
    }


@router.post("/admin/requests/{request_id}/review")
def review_public_share_request(
    request_id: str,
    payload: ReviewRequest,
    admin_email: str = Query(..., min_length=3),
):
    reviewer = _require_admin(admin_email)
    path = _request_path(request_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Request not found")

    record = _load_request(path)
    if record.get("status") != "pending_review":
        raise HTTPException(status_code=409, detail="Request has already been reviewed")

    record.update(
        {
            "status": payload.decision,
            "review_notes": payload.review_notes.strip(),
            "reviewed_by": reviewer,
            "reviewed_at": _utcnow(),
        }
    )
    _save_request(path, record)

    if payload.decision == "approved":
        _apply_dataset_visibility(record)

    return {
        "ok": True,
        "request": record,
    }
