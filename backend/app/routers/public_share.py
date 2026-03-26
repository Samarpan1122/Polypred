"""Public sharing request endpoints for datasets and models."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.services.dataset_service import DATA_DIR

router = APIRouter(prefix="/api/public-share", tags=["public-share"])

REQUESTS_DIR = DATA_DIR / "public_share_requests"
REQUESTS_DIR.mkdir(parents=True, exist_ok=True)


class PublicShareRequest(BaseModel):
    asset_type: Literal["dataset", "model"]
    asset_id: str = Field(..., min_length=1, max_length=128)
    asset_name: str = Field(..., min_length=1, max_length=255)

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


@router.post("/requests")
def create_public_share_request(payload: PublicShareRequest):
    request_id = str(uuid.uuid4())[:12]
    now = datetime.utcnow().isoformat()

    record = {
        "request_id": request_id,
        "status": "pending_review",
        "submitted_at": now,
        **payload.model_dump(),
    }

    out_path = REQUESTS_DIR / f"{request_id}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "request_id": request_id,
        "status": "pending_review",
        "message": "Public sharing request submitted. Our team will review and contact you.",
    }


@router.get("/requests/{request_id}")
def get_public_share_request(request_id: str):
    p = REQUESTS_DIR / f"{request_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Request not found")
    return json.loads(p.read_text(encoding="utf-8"))
