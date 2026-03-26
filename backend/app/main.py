"""PolyPred - FastAPI backend entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import predict, models, compare, dataset, features, training, reaction, auth_v2, public_share, storage

app = FastAPI(
    title="PolyPred API",
    description=(
        "Full ML experimentation platform for copolymerisation reactivity-ratio prediction. "
        "Upload datasets · featurize · train 27+ models · HP tuning · visualise everything."
    ),
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers - original
app.include_router(predict.router)
app.include_router(models.router)
app.include_router(compare.router)
# Routers - local security
from app.api.endpoints import auth, data_portal
app.include_router(auth.router)
app.include_router(data_portal.router)
app.include_router(auth_v2.router)

# Routers - new platform
app.include_router(dataset.router)
app.include_router(features.router)
app.include_router(training.router)
app.include_router(reaction.router)
app.include_router(public_share.router)
app.include_router(storage.router)


@app.get("/")
async def root():
    return {"message": "PolyPred API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ──────────────────────────────────────────────────────────────────────
#  AWS Lambda handler (via Mangum)
# ──────────────────────────────────────────────────────────────────────
try:
    from mangum import Mangum
    handler = Mangum(app)
except ImportError:
    handler = None
