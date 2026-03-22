#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────
#  PolyPred — Deploy Backend to AWS ECS Fargate
# ──────────────────────────────────────────────────────────
#  Usage:  ./deploy.sh [--tag <image_tag>]
# ──────────────────────────────────────────────────────────

TAG="${1:-latest}"
REGION="us-east-1"
PROJECT="polypred"

echo "▶ Deploying PolyPred backend (tag: $TAG)"

# 1. Get ECR repo URL
ECR_REPO=$(aws ecr describe-repositories \
  --repository-names "${PROJECT}-backend" \
  --region "$REGION" \
  --query 'repositories[0].repositoryUri' \
  --output text 2>/dev/null || echo "")

if [ -z "$ECR_REPO" ]; then
  echo "⚠ ECR repository not found. Run 'terraform apply' first."
  exit 1
fi

echo "  ECR: $ECR_REPO"

# 2. Login to ECR
echo "▶ Logging into ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REPO"

# 3. Build & push
echo "▶ Building Docker image..."
docker build -t "${PROJECT}-backend:${TAG}" ./backend

echo "▶ Tagging & pushing..."
docker tag "${PROJECT}-backend:${TAG}" "${ECR_REPO}:${TAG}"
docker push "${ECR_REPO}:${TAG}"

# 4. Force new deployment
echo "▶ Updating ECS service..."
aws ecs update-service \
  --cluster "${PROJECT}-cluster" \
  --service "${PROJECT}-backend" \
  --force-new-deployment \
  --region "$REGION" \
  --no-cli-pager

echo "✓ Deployment triggered. Watch progress:"
echo "  aws ecs describe-services --cluster ${PROJECT}-cluster --services ${PROJECT}-backend --region $REGION"
