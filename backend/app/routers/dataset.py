"""Endpoints for dataset upload, listing, preview, stats, splitting."""

from fastapi import APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from app.services.dataset_service import (
    save_dataset, get_dataset, list_datasets, delete_dataset,
    get_dataset_stats, load_dataframe, split_dataset,
)
from app.models.schemas import SplitConfig, SplitMethod

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
):
    contents = await file.read()
    ds_name = name or file.filename or "dataset"
    info = save_dataset(ds_name, contents)
    return info


@router.get("/")
async def list_all():
    return list_datasets()


@router.get("/{dataset_id}")
async def get_one(dataset_id: str):
    info = get_dataset(dataset_id)
    if not info:
        return JSONResponse({"error": "Not found"}, 404)
    return info


@router.get("/{dataset_id}/preview")
async def preview(dataset_id: str, rows: int = Query(20, ge=1, le=500)):
    df = load_dataframe(dataset_id)
    return {
        "columns": df.columns.tolist(),
        "dtypes": {c: str(d) for c, d in df.dtypes.items()},
        "rows": df.head(rows).to_dict(orient="records"),
        "shape": list(df.shape),
    }


@router.get("/{dataset_id}/stats")
async def stats(dataset_id: str):
    return get_dataset_stats(dataset_id)


@router.post("/{dataset_id}/split")
async def do_split(dataset_id: str, config: SplitConfig):
    return split_dataset(dataset_id, config)


@router.delete("/{dataset_id}")
async def remove(dataset_id: str):
    if delete_dataset(dataset_id):
        return {"ok": True}
    return JSONResponse({"error": "Not found"}, 404)
