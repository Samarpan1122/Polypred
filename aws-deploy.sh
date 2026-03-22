#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# PolyPred — AWS CLI deployment script
# Deploys backend (ECS Fargate) + frontend (S3 + CloudFront)
# Usage:  ./aws-deploy.sh [--region us-east-1] [--stage prod]
# ──────────────────────────────────────────────────────────
set -euo pipefail

# ─── Defaults ─────────────────────────────────────────────
PROJECT="polypred"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
STAGE="prod"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${PROJECT}-backend"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"
CLUSTER="${PROJECT}-cluster"
SERVICE="${PROJECT}-service"
TASK_FAMILY="${PROJECT}-task"
S3_BUCKET="${PROJECT}-models-${ACCOUNT_ID}"
S3_FRONTEND="${PROJECT}-frontend-${ACCOUNT_ID}"
VPC_CIDR="10.0.0.0/16"
SUBNET_CIDR_A="10.0.1.0/24"
SUBNET_CIDR_B="10.0.2.0/24"
CPU=1024
MEMORY=4096
LOG_GROUP="/ecs/${PROJECT}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2;;
    --stage)  STAGE="$2"; shift 2;;
    *)        echo "Unknown arg: $1"; exit 1;;
  esac
done

echo "═══════════════════════════════════════════════"
echo "  PolyPred AWS Deployment"
echo "  Region:  ${REGION}"
echo "  Account: ${ACCOUNT_ID}"
echo "  Stage:   ${STAGE}"
echo "═══════════════════════════════════════════════"

# ─── 1. ECR Repository ──────────────────────────────────
echo -e "\n[1/9] ECR Repository..."
aws ecr describe-repositories --repository-names "${ECR_REPO}" --region "${REGION}" 2>/dev/null || \
  aws ecr create-repository --repository-name "${ECR_REPO}" --region "${REGION}" \
    --image-scanning-configuration scanOnPush=true

# ─── 2. S3 Buckets ──────────────────────────────────────
echo -e "\n[2/9] S3 Buckets..."
for BUCKET in "${S3_BUCKET}" "${S3_FRONTEND}"; do
  aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null || \
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" \
      $([ "${REGION}" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=${REGION}" || echo "")
done

# Enable static website hosting on frontend bucket
aws s3 website "s3://${S3_FRONTEND}" --index-document index.html --error-document index.html
aws s3api put-bucket-policy --bucket "${S3_FRONTEND}" --policy "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{
    \"Sid\":\"PublicReadGetObject\",
    \"Effect\":\"Allow\",
    \"Principal\":\"*\",
    \"Action\":\"s3:GetObject\",
    \"Resource\":\"arn:aws:s3:::${S3_FRONTEND}/*\"
  }]
}"

# ─── 3. VPC + Subnets ──────────────────────────────────
echo -e "\n[3/9] VPC + Networking..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=${PROJECT}-vpc" --query 'Vpcs[0].VpcId' --output text 2>/dev/null)
if [ "${VPC_ID}" = "None" ] || [ -z "${VPC_ID}" ]; then
  VPC_ID=$(aws ec2 create-vpc --cidr-block "${VPC_CIDR}" --query 'Vpc.VpcId' --output text)
  aws ec2 create-tags --resources "${VPC_ID}" --tags "Key=Name,Value=${PROJECT}-vpc"
  aws ec2 modify-vpc-attribute --vpc-id "${VPC_ID}" --enable-dns-support '{"Value":true}'
  aws ec2 modify-vpc-attribute --vpc-id "${VPC_ID}" --enable-dns-hostnames '{"Value":true}'
fi
echo "  VPC: ${VPC_ID}"

# Internet Gateway
IGW_ID=$(aws ec2 describe-internet-gateways --filters "Name=tag:Name,Values=${PROJECT}-igw" --query 'InternetGateways[0].InternetGatewayId' --output text 2>/dev/null)
if [ "${IGW_ID}" = "None" ] || [ -z "${IGW_ID}" ]; then
  IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
  aws ec2 create-tags --resources "${IGW_ID}" --tags "Key=Name,Value=${PROJECT}-igw"
  aws ec2 attach-internet-gateway --internet-gateway-id "${IGW_ID}" --vpc-id "${VPC_ID}"
fi

# Subnets
AZ_A=$(aws ec2 describe-availability-zones --region "${REGION}" --query 'AvailabilityZones[0].ZoneName' --output text)
AZ_B=$(aws ec2 describe-availability-zones --region "${REGION}" --query 'AvailabilityZones[1].ZoneName' --output text)

SUBNET_A=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=${PROJECT}-subnet-a" --query 'Subnets[0].SubnetId' --output text 2>/dev/null)
if [ "${SUBNET_A}" = "None" ] || [ -z "${SUBNET_A}" ]; then
  SUBNET_A=$(aws ec2 create-subnet --vpc-id "${VPC_ID}" --cidr-block "${SUBNET_CIDR_A}" --availability-zone "${AZ_A}" --query 'Subnet.SubnetId' --output text)
  aws ec2 create-tags --resources "${SUBNET_A}" --tags "Key=Name,Value=${PROJECT}-subnet-a"
  aws ec2 modify-subnet-attribute --subnet-id "${SUBNET_A}" --map-public-ip-on-launch
fi

SUBNET_B=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=${PROJECT}-subnet-b" --query 'Subnets[0].SubnetId' --output text 2>/dev/null)
if [ "${SUBNET_B}" = "None" ] || [ -z "${SUBNET_B}" ]; then
  SUBNET_B=$(aws ec2 create-subnet --vpc-id "${VPC_ID}" --cidr-block "${SUBNET_CIDR_B}" --availability-zone "${AZ_B}" --query 'Subnet.SubnetId' --output text)
  aws ec2 create-tags --resources "${SUBNET_B}" --tags "Key=Name,Value=${PROJECT}-subnet-b"
  aws ec2 modify-subnet-attribute --subnet-id "${SUBNET_B}" --map-public-ip-on-launch
fi

# Route table
RTB_ID=$(aws ec2 describe-route-tables --filters "Name=tag:Name,Values=${PROJECT}-rtb" --query 'RouteTables[0].RouteTableId' --output text 2>/dev/null)
if [ "${RTB_ID}" = "None" ] || [ -z "${RTB_ID}" ]; then
  RTB_ID=$(aws ec2 create-route-table --vpc-id "${VPC_ID}" --query 'RouteTable.RouteTableId' --output text)
  aws ec2 create-tags --resources "${RTB_ID}" --tags "Key=Name,Value=${PROJECT}-rtb"
  aws ec2 create-route --route-table-id "${RTB_ID}" --destination-cidr-block 0.0.0.0/0 --gateway-id "${IGW_ID}"
  aws ec2 associate-route-table --route-table-id "${RTB_ID}" --subnet-id "${SUBNET_A}"
  aws ec2 associate-route-table --route-table-id "${RTB_ID}" --subnet-id "${SUBNET_B}"
fi

# Security group
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${PROJECT}-sg" "Name=vpc-id,Values=${VPC_ID}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
if [ "${SG_ID}" = "None" ] || [ -z "${SG_ID}" ]; then
  SG_ID=$(aws ec2 create-security-group --group-name "${PROJECT}-sg" --description "PolyPred ECS" --vpc-id "${VPC_ID}" --query 'GroupId' --output text)
  aws ec2 authorize-security-group-ingress --group-id "${SG_ID}" --protocol tcp --port 8000 --cidr 0.0.0.0/0
  aws ec2 authorize-security-group-ingress --group-id "${SG_ID}" --protocol tcp --port 443 --cidr 0.0.0.0/0
fi
echo "  SG: ${SG_ID}"

# ─── 4. IAM Role ───────────────────────────────────────
echo -e "\n[4/9] IAM Roles..."
TASK_ROLE="${PROJECT}-task-role"
EXEC_ROLE="${PROJECT}-exec-role"

for ROLE in "${TASK_ROLE}" "${EXEC_ROLE}"; do
  aws iam get-role --role-name "${ROLE}" 2>/dev/null || \
    aws iam create-role --role-name "${ROLE}" --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
    }'
done

aws iam attach-role-policy --role-name "${EXEC_ROLE}" --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true

# S3 access for task role
aws iam put-role-policy --role-name "${TASK_ROLE}" --policy-name s3-access --policy-document "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{
    \"Effect\":\"Allow\",
    \"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:ListBucket\"],
    \"Resource\":[\"arn:aws:s3:::${S3_BUCKET}\",\"arn:aws:s3:::${S3_BUCKET}/*\"]
  }]
}"

# ─── 5. CloudWatch Logs ────────────────────────────────
echo -e "\n[5/9] CloudWatch..."
aws logs create-log-group --log-group-name "${LOG_GROUP}" --region "${REGION}" 2>/dev/null || true

# ─── 6. Build & Push Docker Image ──────────────────────
echo -e "\n[6/9] Building & pushing Docker image..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

docker build -t "${ECR_REPO}:latest" ./backend
docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
echo "  Image pushed to ${ECR_URI}:latest"

# ─── 7. ECS Cluster + Task Definition ──────────────────
echo -e "\n[7/9] ECS Cluster & Task..."
aws ecs describe-clusters --clusters "${CLUSTER}" --query 'clusters[0].status' --output text 2>/dev/null | grep -q ACTIVE || \
  aws ecs create-cluster --cluster-name "${CLUSTER}" --capacity-providers FARGATE --default-capacity-provider-strategy '[{"capacityProvider":"FARGATE","weight":1}]'

TASK_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${TASK_ROLE}"
EXEC_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EXEC_ROLE}"

aws ecs register-task-definition \
  --family "${TASK_FAMILY}" \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu "${CPU}" --memory "${MEMORY}" \
  --task-role-arn "${TASK_ROLE_ARN}" \
  --execution-role-arn "${EXEC_ROLE_ARN}" \
  --container-definitions "[{
    \"name\":\"${PROJECT}-backend\",
    \"image\":\"${ECR_URI}:latest\",
    \"portMappings\":[{\"containerPort\":8000,\"protocol\":\"tcp\"}],
    \"environment\":[
      {\"name\":\"S3_BUCKET\",\"value\":\"${S3_BUCKET}\"},
      {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"${REGION}\"}
    ],
    \"logConfiguration\":{
      \"logDriver\":\"awslogs\",
      \"options\":{
        \"awslogs-group\":\"${LOG_GROUP}\",
        \"awslogs-region\":\"${REGION}\",
        \"awslogs-stream-prefix\":\"ecs\"
      }
    },
    \"essential\":true
  }]"

# ─── 8. ECS Service ────────────────────────────────────
echo -e "\n[8/9] ECS Service..."
EXISTING_SVC=$(aws ecs describe-services --cluster "${CLUSTER}" --services "${SERVICE}" --query 'services[0].status' --output text 2>/dev/null)
if [ "${EXISTING_SVC}" = "ACTIVE" ]; then
  echo "  Updating service..."
  aws ecs update-service --cluster "${CLUSTER}" --service "${SERVICE}" --force-new-deployment --desired-count 1
else
  echo "  Creating service..."
  aws ecs create-service \
    --cluster "${CLUSTER}" \
    --service-name "${SERVICE}" \
    --task-definition "${TASK_FAMILY}" \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_A},${SUBNET_B}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}"
fi

# ─── 9. Build & Deploy Frontend ────────────────────────
echo -e "\n[9/9] Building & deploying frontend..."

# Get the public IP of the ECS task for API URL
echo "  Waiting for ECS task to start..."
sleep 10
TASK_ARN=$(aws ecs list-tasks --cluster "${CLUSTER}" --service-name "${SERVICE}" --query 'taskArns[0]' --output text 2>/dev/null)
if [ "${TASK_ARN}" != "None" ] && [ -n "${TASK_ARN}" ]; then
  ENI_ID=$(aws ecs describe-tasks --cluster "${CLUSTER}" --tasks "${TASK_ARN}" --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text 2>/dev/null)
  if [ "${ENI_ID}" != "None" ] && [ -n "${ENI_ID}" ]; then
    PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids "${ENI_ID}" --query 'NetworkInterfaces[0].Association.PublicIp' --output text 2>/dev/null)
    API_URL="http://${PUBLIC_IP}:8000"
  fi
fi
API_URL="${API_URL:-http://localhost:8000}"

cd frontend
NEXT_PUBLIC_API_URL="${API_URL}" npm run build
aws s3 sync out/ "s3://${S3_FRONTEND}/" --delete
cd ..

# ─── Done ──────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Deployment Complete!"
echo "═══════════════════════════════════════════════════"
echo "  Backend API:   ${API_URL}"
echo "  Frontend:      http://${S3_FRONTEND}.s3-website-${REGION}.amazonaws.com"
echo "  ECR Image:     ${ECR_URI}:latest"
echo "  S3 Models:     s3://${S3_BUCKET}/"
echo "  Cluster:       ${CLUSTER}"
echo "  Log Group:     ${LOG_GROUP}"
echo "═══════════════════════════════════════════════════"
