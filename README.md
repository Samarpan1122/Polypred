# PolyPred

**Plug-and-play ML platform for copolymerisation reactivity-ratio (r₁, r₂) prediction from monomer SMILES pairs.**

22+ models covering deep learning (Siamese, VAE, LSTM, GAT) and traditional ML (RF, XGBoost, SVM, KNN, …) — all extracted from 12 research notebooks.

---

## Architecture

```
┌─────────────┐       ┌───────────────┐       ┌──────────┐
│  Next.js 14 │──────▶│  FastAPI (Py) │──────▶│  S3      │
│  (Vercel)   │  API  │  ECS Fargate  │ model │  Weights │
│  Tailwind   │◀──────│  PyTorch+RDKit│◀──────│          │
│  Recharts   │       │  sklearn      │       └──────────┘
└─────────────┘       └───────────────┘
```

## Models (22+)

| Category           | Models                                                                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Encoders**       | Standard AE, Denoising AE, VAE                                                                                                         |
| **Deep Learning**  | Siamese MIMO/MISO, Baseline MLP MIMO/MISO, Bi-LSTM Large/Optimized, GAT MIMO/MISO                                                      |
| **Traditional ML** | Decision Tree, Random Forest, Gradient Boosting, XGBoost, Extra Trees, AdaBoost, Linear Regression, Ridge, Lasso, ElasticNet, KNN, SVM |

## Quick Start (Local)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

### Docker Compose

```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

## API Endpoints

| Method | Path                     | Description                       |
| ------ | ------------------------ | --------------------------------- |
| `POST` | `/api/predict/single`    | Run one model                     |
| `POST` | `/api/predict/multi`     | Run multiple models               |
| `POST` | `/api/predict/all`       | Run all prediction models         |
| `POST` | `/api/predict/validate`  | Validate a SMILES string          |
| `POST` | `/api/compare/`          | Compare models with summary stats |
| `GET`  | `/api/models/`           | List all models with metadata     |
| `GET`  | `/api/models/categories` | List model categories             |
| `GET`  | `/health`                | Health check                      |

### Example Request

```bash
curl -X POST http://localhost:8000/api/predict/single \
  -H 'Content-Type: application/json' \
  -d '{"smiles_a": "C=Cc1ccccc1", "smiles_b": "C=C(C)C(=O)OC", "model": "random_forest"}'
```

## AWS Deployment

### Prerequisites

- AWS CLI configured
- Terraform ≥ 1.5
- Docker

### Steps

1. **Provision infrastructure**

   ```bash
   cd infrastructure/terraform
   terraform init && terraform apply
   ```

2. **Upload model weights to S3**

   ```bash
   ./backend/scripts/upload_models.sh /path/to/trained_models/
   ```

3. **Deploy backend**

   ```bash
   ./deploy.sh latest
   ```

4. **Deploy frontend** — push to Vercel or use the Docker image.

### AWS Resources Created

- **S3 bucket** — encrypted model weight storage
- **ECR repository** — Docker image registry
- **ECS Fargate** — containerised backend (1 vCPU, 4 GB RAM)
- **API Gateway** — HTTP API with CORS
- **VPC** — isolated network with public subnets
- **CloudWatch** — logs (30-day retention)
- **IAM roles** — least-privilege S3 + ECS access

## Feature Engineering Pipeline

| Feature Type        | Dimensions     | Used By                        |
| ------------------- | -------------- | ------------------------------ |
| Morgan FP (ECFP4)   | 2048           | Siamese, Baseline MLP, AE, VAE |
| AE Latent Pair      | 256            | Siamese MIMO/MISO              |
| Graph Node Features | 58 per atom    | GAT                            |
| Graph Edge Features | 13 per bond    | GAT                            |
| Global Features     | 7 per molecule | GAT                            |
| Flat Graph Features | 248 (pair)     | LSTM, Traditional ML           |
| RDKit Descriptors   | 210            | Descriptor analysis            |
| 3D Autocorrelation  | 80             | VAE-Siamese variant            |

## Project Structure

```
polypred-app/
├── frontend/            # Next.js 14 (App Router)
│   ├── src/app/         # Pages: dashboard, predict, compare, models
│   ├── src/components/  # MoleculeInput, ModelSelector, Charts, etc.
│   └── src/lib/         # API client, types, utils
├── backend/             # FastAPI
│   ├── app/main.py      # Entry point
│   ├── app/config.py    # Settings
│   ├── app/models/      # ML model definitions (PyTorch, sklearn)
│   ├── app/routers/     # API routes
│   ├── app/services/    # Model loading, S3, prediction
│   └── scripts/         # Utility scripts
├── infrastructure/      # Terraform + Docker
│   └── terraform/       # AWS IaC
├── docker-compose.yml
├── deploy.sh
└── README.md
```

## License

MIT
