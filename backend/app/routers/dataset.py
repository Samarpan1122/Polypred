"""Endpoints for dataset upload, listing, preview, stats, splitting."""

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
import numpy as np
from app.services.dataset_service import (
    save_dataset, sync_dataset_to_s3, get_dataset, list_datasets, delete_dataset,
    get_dataset_stats, load_dataframe, split_dataset,
)
from app.models.schemas import SplitConfig, SplitMethod

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload")
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(None),
    owner_id: str = Form("anonymous"),
):
    contents = await file.read()
    ds_name = name or file.filename or "dataset"
    info = save_dataset(ds_name, contents, owner_id=owner_id, sync_to_s3=False)
    background_tasks.add_task(sync_dataset_to_s3, info["id"], owner_id)
    return info


@router.get("/")
async def list_all(owner_id: str = Query("anonymous")):
    return list_datasets(owner_id=owner_id)


@router.get("/{dataset_id}")
async def get_one(dataset_id: str, owner_id: str = Query("anonymous")):
    info = get_dataset(dataset_id, owner_id=owner_id)
    if not info:
        return JSONResponse({"error": "Not found"}, 404)
    return info


@router.get("/{dataset_id}/preview")
async def preview(dataset_id: str, rows: int = Query(20, ge=1, le=500), owner_id: str = Query("anonymous")):
    df = load_dataframe(dataset_id, owner_id=owner_id)
    return {
        "columns": df.columns.tolist(),
        "dtypes": {c: str(d) for c, d in df.dtypes.items()},
        "rows": df.head(rows).replace({np.nan: None}).to_dict(orient="records"),
        "shape": list(df.shape),
    }


@router.get("/{dataset_id}/stats")
async def stats(dataset_id: str, owner_id: str = Query("anonymous")):
    return get_dataset_stats(dataset_id, owner_id=owner_id)


@router.post("/{dataset_id}/split")
async def do_split(dataset_id: str, config: SplitConfig, owner_id: str = Query("anonymous")):
    return split_dataset(dataset_id, config, owner_id=owner_id)


@router.delete("/{dataset_id}")
async def remove(dataset_id: str, owner_id: str = Query("anonymous")):
    if delete_dataset(dataset_id, owner_id=owner_id):
        return {"ok": True}
    return JSONResponse({"error": "Not found"}, 404)
