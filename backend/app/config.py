"""PolyPred Backend Configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "PolyPred API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Plug-and-play ML models for copolymerization reactivity ratio prediction"

    # AWS Cognito
    COGNITO_USER_POOL_ID: str = os.getenv("COGNITO_USER_POOL_ID", "us-east-1_example")
    COGNITO_CLIENT_ID: str = os.getenv("COGNITO_CLIENT_ID", "exampleclientid")
    COGNITO_CLIENT_SECRET: str = os.getenv("COGNITO_CLIENT_SECRET", "")

    # AWS
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "polypred-models")
    S3_MODEL_PREFIX: str = os.getenv("S3_MODEL_PREFIX", "models/")

    # Model paths (local cache)
    MODEL_CACHE_DIR: Path = Path(os.getenv("MODEL_CACHE_DIR", "/tmp/polypred_models"))

    # Benchmark models directory (pre-trained weights from Specific_Models_Final)
    BENCHMARK_MODELS_DIR: Path = Path(os.getenv(
        "BENCHMARK_MODELS_DIR",
        str(Path(__file__).resolve().parent.parent.parent / "Specific_Models_Final")
    ))

    # CORS
    ALLOWED_ORIGINS: list = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,https://polypred.vercel.app,*"
    ).split(",")

    _device = os.getenv("DEVICE", "cpu")
    if _device == "cuda":
        import torch
        if not torch.cuda.is_available():
            _device = "cpu"
    DEVICE: str = _device

    # Morgan fingerprint defaults
    FP_RADIUS: int = 2
    FP_NBITS: int = 2048

    # Molecular graph feature dimensions (from notebooks)
    NODE_FEATURE_DIM: int = 58
    EDGE_FEATURE_DIM: int = 13
    GLOBAL_FEATURE_DIM: int = 7
    LATENT_DIM: int = 64

    # Auth & Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret-key-change-me")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/polypred")
    
    # Encryption (AWS S3 managed encryption)
    STORAGE_PRESIGN_TTL_SECONDS: int = int(os.getenv("STORAGE_PRESIGN_TTL_SECONDS", "300"))

    # All available model types
    MODEL_TYPES: list = [
        # Benchmark models (pre-trained weights in Specific_Models_Final/)
        "siamese_lstm",
        "siamese_regression",
        "siamese_bayesian",
        "lstm_bayesian",
        "lstm_siamese_bayesian",
        "standalone_lstm",
        "ensemble_methods",
        "decision_tree",
        "random_forest",
        "autoencoder",
    ]


settings = Settings()
settings.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
