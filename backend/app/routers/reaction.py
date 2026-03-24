"""Reaction Validator router - /api/reaction endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from rdkit import Chem

from app.services.training_service import RESULTS_DIR

router = APIRouter(prefix="/api/reaction", tags=["reaction"])


# ──────────────────────────────────────────────────────────
#  Schemas
# ──────────────────────────────────────────────────────────
class ReactionValidateRequest(BaseModel):
    smiles_a: str = Field(..., description="SMILES for monomer A")
    smiles_b: str = Field(..., description="SMILES for monomer B")


class SmilesValidation(BaseModel):
    smiles: str
    valid: bool
    error: str | None = None


class ReactionValidateResponse(BaseModel):
    smiles_a: SmilesValidation
    smiles_b: SmilesValidation
    both_valid: bool


class RankedModel(BaseModel):
    model_name: str
    model_type: str
    r2_r1: float | None = None
    r2_r2: float | None = None
    avg_r2: float | None = None
    mse_r1: float | None = None
    mse_r2: float | None = None
    job_id: str | None = None


# ──────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────
def is_valid_smiles(smi: str) -> tuple[bool, str | None]:
    """Validate a SMILES string using RDKit (syntax + chemistry)."""
    # 1) parse without sanitization: catches pure syntax problems
    m = Chem.MolFromSmiles(smi, sanitize=False)
    if m is None:
        return False, "Invalid SMILES syntax - could not be parsed"

    # 2) run sanitization: catches valence/aromaticity/chemistry issues
    try:
        Chem.SanitizeMol(m)
    except Exception as e:
        return False, f"Chemistry error: {str(e)}"

    return True, None


# ──────────────────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────────────────
@router.post("/validate", response_model=ReactionValidateResponse)
async def validate_reaction(req: ReactionValidateRequest):
    """Validate two SMILES strings for a reaction pair."""
    valid_a, err_a = is_valid_smiles(req.smiles_a.strip())
    valid_b, err_b = is_valid_smiles(req.smiles_b.strip())

    return ReactionValidateResponse(
        smiles_a=SmilesValidation(smiles=req.smiles_a, valid=valid_a, error=err_a),
        smiles_b=SmilesValidation(smiles=req.smiles_b, valid=valid_b, error=err_b),
        both_valid=valid_a and valid_b,
    )


@router.get("/top-models", response_model=list[RankedModel])
async def top_models():
    """Scan completed training jobs and rank models by average R² score."""
    all_models: list[RankedModel] = []

    if not RESULTS_DIR.exists():
        return []

    for job_dir in RESULTS_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        results_file = job_dir / "results.json"
        if not results_file.exists():
            continue

        try:
            data = json.loads(results_file.read_text())
            job_id = data.get("job_id", job_dir.name)

            for model_result in data.get("results", []):
                r2_r1 = model_result.get("r2_r1")
                r2_r2 = model_result.get("r2_r2")

                # Skip models with no R² scores (e.g. autoencoders)
                if r2_r1 is None and r2_r2 is None:
                    continue

                # Compute average R²
                scores = [s for s in [r2_r1, r2_r2] if s is not None]
                avg_r2 = sum(scores) / len(scores) if scores else None

                all_models.append(RankedModel(
                    model_name=model_result.get("model_name", "unknown"),
                    model_type=model_result.get("model_type", "unknown"),
                    r2_r1=r2_r1,
                    r2_r2=r2_r2,
                    avg_r2=round(avg_r2, 4) if avg_r2 is not None else None,
                    mse_r1=model_result.get("mse_r1"),
                    mse_r2=model_result.get("mse_r2"),
                    job_id=job_id,
                ))
        except (json.JSONDecodeError, KeyError):
            continue

    # Sort by average R² descending (best first)
    all_models.sort(key=lambda m: m.avg_r2 if m.avg_r2 is not None else -999, reverse=True)

    return all_models
