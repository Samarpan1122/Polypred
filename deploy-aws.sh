#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  PolyPred - Full AWS Deployment (remote build on CodeBuild)
#  Backend:  CodeBuild → ECR → ECS Fargate + ALB
#  Frontend: Static export → S3 + CloudFront CDN
#
#  Prerequisites:
#    - AWS CLI v2 configured (aws configure)
#    - Node.js 20+ / npm
#
#  Usage:
#    chmod +x deploy-aws.sh
#    ./deploy-aws.sh
#    ./deploy-aws.sh --region us-west-2
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────
PROJECT="polypred"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
STAGE="prod"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2;;
    --stage)  STAGE="$2"; shift 2;;
    *)        echo "Unknown arg: $1"; exit 1;;
  esac
done

if [ -f ".env.deploy" ]; then
  set -a
  source .env.deploy
  set +a
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "${ACCOUNT_ID}" ]; then
  echo "❌ AWS CLI not configured. Run 'aws configure' first."
  exit 1
fi

COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:-us-east-1_AyPBc56Z0}"
COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:-4kj08f4s31sog5l603f20s2krf}"
COGNITO_CLIENT_SECRET="${COGNITO_CLIENT_SECRET:-}"

if [ -z "${COGNITO_USER_POOL_ID}" ] || [ -z "${COGNITO_CLIENT_ID}" ]; then
  echo "❌ Missing Cognito env vars. Export COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID before deploy."
  exit 1
fi

ECR_REPO="${PROJECT}-backend"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"
CLUSTER="${PROJECT}-cluster"
SERVICE="${PROJECT}-service"
TASK_FAMILY="${PROJECT}-task"
S3_MODELS="${PROJECT}-models-${ACCOUNT_ID}"
S3_FRONTEND="${PROJECT}-frontend-${ACCOUNT_ID}"
S3_BUILD="${PROJECT}-build-${ACCOUNT_ID}"
TASK_ROLE="${PROJECT}-task-role"
EXEC_ROLE="${PROJECT}-exec-role"
CODEBUILD_ROLE="${PROJECT}-codebuild-role"
CODEBUILD_PROJECT="${PROJECT}-build"
LOG_GROUP="/ecs/${PROJECT}"
ALB_NAME="${PROJECT}-alb"
TG_NAME="${PROJECT}-tg"
SG_NAME="${PROJECT}-sg"
CPU=16384
MEMORY=61440
GPU_INSTANCE_TYPE="g5.4xlarge"
ASG_NAME="${PROJECT}-gpu-asg"
LAUNCH_TEMPLATE="${PROJECT}-gpu-lt"
CAP_PROVIDER="${PROJECT}-gpu-cap"

USE_GPU="${USE_GPU:-false}"
if [ "${USE_GPU}" = "true" ]; then
  CPU=16384
  MEMORY=61440
  DEVICE_MODE="cuda"
  GPU_RESOURCE_JSON=',"resourceRequirements":[{"type":"GPU","value":"1"}]'
  TASK_SIZE_LABEL="${CPU} CPU / ${MEMORY} MiB / 1x GPU"
else
  CPU=4096
  MEMORY=8192
  DEVICE_MODE="cpu"
  GPU_RESOURCE_JSON=''
  TASK_SIZE_LABEL="${CPU} CPU / ${MEMORY} MiB / CPU"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  PolyPred AWS Deployment                              ║"
echo "║  Region:   ${REGION}                                     ║"
echo "║  Account:  ${ACCOUNT_ID}                          ║"
echo "║  GPU:      ${GPU_INSTANCE_TYPE} (24 GB VRAM, 16 vCPU, 64 GB)   ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "  Cognito Pool:   ${COGNITO_USER_POOL_ID}"
echo "  Cognito Client: ${COGNITO_CLIENT_ID}"
echo "  Runtime Mode:   ${DEVICE_MODE}"
if [ -n "${COGNITO_CLIENT_SECRET}" ]; then
  echo "  Cognito Secret: set"
else
  echo "  Cognito Secret: empty (expected for no-secret app client)"
fi

# ═══════════════════════════════════════════════════════════
#  Step 1: ECR Repository
# ═══════════════════════════════════════════════════════════
echo "━━━ [1/11] ECR Repository ━━━"
aws ecr describe-repositories --repository-names "${ECR_REPO}" --region "${REGION}" > /dev/null 2>&1 || \
  aws ecr create-repository --repository-name "${ECR_REPO}" --region "${REGION}" \
    --image-scanning-configuration scanOnPush=true > /dev/null
echo "  ✓ ECR: ${ECR_URI}"

# ═══════════════════════════════════════════════════════════
#  Step 2: S3 Buckets
# ═══════════════════════════════════════════════════════════
echo "━━━ [2/11] S3 Buckets ━━━"
for BUCKET in "${S3_MODELS}" "${S3_FRONTEND}" "${S3_BUILD}"; do
  aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null || \
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" \
      $([ "${REGION}" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=${REGION}" || echo "") > /dev/null
  echo "  ✓ s3://${BUCKET}"
done

# ═══════════════════════════════════════════════════════════
#  Step 3: Upload backend source to S3 for CodeBuild
# ═══════════════════════════════════════════════════════════
echo "━━━ [3/11] Upload Backend Source ━━━"
TMPZIP="/tmp/polypred-backend-src.zip"
cd "${SCRIPT_DIR}/backend"
cp -r ../Specific_Models_Final ./Specific_Models_Final
zip -r "${TMPZIP}" . -x ".venv/*" "__pycache__/*" "*.pyc" ".git/*" "scripts/*" > /dev/null 2>&1
rm -rf ./Specific_Models_Final
aws s3 cp "${TMPZIP}" "s3://${S3_BUILD}/backend-src.zip" --region "${REGION}" > /dev/null
rm -f "${TMPZIP}"
cd "${SCRIPT_DIR}"
echo "  ✓ Source uploaded to s3://${S3_BUILD}/backend-src.zip"

# ═══════════════════════════════════════════════════════════
#  Step 4: VPC + Networking (use default VPC)
# ═══════════════════════════════════════════════════════════
echo "━━━ [4/11] VPC + Networking ━━━"
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region "${REGION}" 2>/dev/null)
if [ "${VPC_ID}" = "None" ] || [ -z "${VPC_ID}" ]; then
  VPC_ID=$(aws ec2 create-default-vpc --query 'Vpc.VpcId' --output text --region "${REGION}" 2>/dev/null || true)
  if [ -z "${VPC_ID}" ]; then echo "❌ No default VPC. Create: aws ec2 create-default-vpc"; exit 1; fi
fi
echo "  ✓ VPC: ${VPC_ID}"

SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" "Name=default-for-az,Values=true" \
  --query 'Subnets[*].SubnetId' --output text --region "${REGION}")
SUBNET_A=$(echo "${SUBNETS}" | awk '{print $1}')
SUBNET_B=$(echo "${SUBNETS}" | awk '{print $2}')
if [ -z "${SUBNET_B}" ]; then SUBNET_B="${SUBNET_A}"; fi
echo "  ✓ Subnets: ${SUBNET_A}, ${SUBNET_B}"

SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text --region "${REGION}" 2>/dev/null)
if [ "${SG_ID}" = "None" ] || [ -z "${SG_ID}" ]; then
  SG_ID=$(aws ec2 create-security-group --group-name "${SG_NAME}" --description "PolyPred ALB+ECS" \
    --vpc-id "${VPC_ID}" --query 'GroupId' --output text --region "${REGION}")
  aws ec2 authorize-security-group-ingress --group-id "${SG_ID}" --protocol tcp --port 80 --cidr 0.0.0.0/0 --region "${REGION}" > /dev/null
  aws ec2 authorize-security-group-ingress --group-id "${SG_ID}" --protocol tcp --port 443 --cidr 0.0.0.0/0 --region "${REGION}" > /dev/null
  aws ec2 authorize-security-group-ingress --group-id "${SG_ID}" --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region "${REGION}" > /dev/null
fi
echo "  ✓ SG: ${SG_ID}"

# ═══════════════════════════════════════════════════════════
#  Step 4c: Private Cognito Connectivity
# ═══════════════════════════════════════════════════════════
echo "━━━ [4c/11] Cognito VPC Endpoint ━━━"
COGNITO_VPCE_SERVICE="com.amazonaws.${REGION}.cognito-idp"
COGNITO_VPCE_ID=$(aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=service-name,Values=${COGNITO_VPCE_SERVICE}" \
  --query 'VpcEndpoints[0].VpcEndpointId' --output text --region "${REGION}" 2>/dev/null || echo "None")

if [ "${COGNITO_VPCE_ID}" = "None" ] || [ -z "${COGNITO_VPCE_ID}" ]; then
  COGNITO_VPCE_ID=$(aws ec2 create-vpc-endpoint \
    --vpc-id "${VPC_ID}" \
    --vpc-endpoint-type Interface \
    --service-name "${COGNITO_VPCE_SERVICE}" \
    --subnet-ids "${SUBNET_A}" "${SUBNET_B}" \
    --security-group-ids "${SG_ID}" \
    --private-dns-enabled \
    --query 'VpcEndpoint.VpcEndpointId' --output text --region "${REGION}")
  echo "  ✓ Created Cognito endpoint: ${COGNITO_VPCE_ID}"
else
  echo "  ✓ Cognito endpoint exists: ${COGNITO_VPCE_ID}"
fi

# ═══════════════════════════════════════════════════════════
#  Step 4b: GPU EC2 Auto Scaling Group + Capacity Provider
# ═══════════════════════════════════════════════════════════
echo "━━━ [4b/11] GPU Capacity Provider ━━━"

# Get the latest ECS-optimized GPU AMI
GPU_AMI=$(aws ssm get-parameters --names /aws/service/ecs/optimized-ami/amazon-linux-2/gpu/recommended \
  --query 'Parameters[0].Value' --output text --region "${REGION}" | python3 -c "import sys,json; print(json.load(sys.stdin)['image_id'])")
echo "  ✓ GPU AMI: ${GPU_AMI}"

# Create/update Launch Template for GPU instances
LT_ID=$(aws ec2 describe-launch-templates --launch-template-names "${LAUNCH_TEMPLATE}" \
  --query 'LaunchTemplates[0].LaunchTemplateId' --output text --region "${REGION}" 2>/dev/null || echo "None")

USER_DATA=$(cat <<'USERDATA' | base64
#!/bin/bash
echo ECS_CLUSTER=polypred-cluster >> /etc/ecs/ecs.config
echo ECS_ENABLE_GPU_SUPPORT=true >> /etc/ecs/ecs.config
USERDATA
)

if [ "${LT_ID}" = "None" ] || [ -z "${LT_ID}" ]; then
  LT_ID=$(aws ec2 create-launch-template \
    --launch-template-name "${LAUNCH_TEMPLATE}" \
    --launch-template-data "{
      \"ImageId\": \"${GPU_AMI}\",
      \"InstanceType\": \"${GPU_INSTANCE_TYPE}\",
      \"UserData\": \"${USER_DATA}\",
      \"SecurityGroupIds\": [\"${SG_ID}\"],
      \"IamInstanceProfile\": {\"Name\": \"ecsInstanceRole\"},
      \"BlockDeviceMappings\": [{
        \"DeviceName\": \"/dev/xvda\",
        \"Ebs\": {\"VolumeSize\": 100, \"VolumeType\": \"gp3\"}
      }]
    }" \
    --query 'LaunchTemplate.LaunchTemplateId' --output text --region "${REGION}")
else
  aws ec2 create-launch-template-version \
    --launch-template-id "${LT_ID}" --source-version 1 \
    --launch-template-data "{
      \"ImageId\": \"${GPU_AMI}\",
      \"InstanceType\": \"${GPU_INSTANCE_TYPE}\",
      \"UserData\": \"${USER_DATA}\",
      \"SecurityGroupIds\": [\"${SG_ID}\"],
      \"IamInstanceProfile\": {\"Name\": \"ecsInstanceRole\"},
      \"BlockDeviceMappings\": [{
        \"DeviceName\": \"/dev/xvda\",
        \"Ebs\": {\"VolumeSize\": 100, \"VolumeType\": \"gp3\"}
      }]
    }" \
    --region "${REGION}" > /dev/null
fi
echo "  ✓ Launch Template: ${LT_ID}"

# Create ecsInstanceRole if it doesn't exist
aws iam get-role --role-name ecsInstanceRole > /dev/null 2>&1 || {
  aws iam create-role --role-name ecsInstanceRole \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' > /dev/null
  aws iam attach-role-policy --role-name ecsInstanceRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role
  aws iam attach-role-policy --role-name ecsInstanceRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
}
aws iam get-instance-profile --instance-profile-name ecsInstanceRole > /dev/null 2>&1 || {
  aws iam create-instance-profile --instance-profile-name ecsInstanceRole > /dev/null
  aws iam add-role-to-instance-profile --instance-profile-name ecsInstanceRole --role-name ecsInstanceRole
  sleep 10  # IAM propagation
}

# Create/update Auto Scaling Group
ASG_EXISTS=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "${ASG_NAME}" \
  --query 'AutoScalingGroups[0].AutoScalingGroupName' --output text --region "${REGION}" 2>/dev/null || echo "None")

if [ "${ASG_EXISTS}" = "None" ] || [ -z "${ASG_EXISTS}" ]; then
  aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name "${ASG_NAME}" \
    --launch-template "LaunchTemplateId=${LT_ID},Version=\$Latest" \
    --min-size 0 --max-size 1 --desired-capacity 1 \
    --vpc-zone-identifier "${SUBNET_A},${SUBNET_B}" \
    --new-instances-protected-from-scale-in \
    --tags "Key=Name,Value=${PROJECT}-gpu,PropagateAtLaunch=true" \
    --region "${REGION}"
else
  aws autoscaling update-auto-scaling-group \
    --auto-scaling-group-name "${ASG_NAME}" \
    --launch-template "LaunchTemplateId=${LT_ID},Version=\$Latest" \
    --min-size 0 --max-size 1 --desired-capacity 1 \
    --region "${REGION}"
fi
echo "  ✓ ASG: ${ASG_NAME} (${GPU_INSTANCE_TYPE})"

# Create ECS Capacity Provider
CAP_EXISTS=$(aws ecs describe-capacity-providers --capacity-providers "${CAP_PROVIDER}" \
  --query 'capacityProviders[0].name' --output text --region "${REGION}" 2>/dev/null || echo "None")

if [ "${CAP_EXISTS}" = "None" ] || [ -z "${CAP_EXISTS}" ]; then
  ASG_ARN=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "${ASG_NAME}" \
    --query 'AutoScalingGroups[0].AutoScalingGroupARN' --output text --region "${REGION}")
  aws ecs create-capacity-provider \
    --name "${CAP_PROVIDER}" \
    --auto-scaling-group-provider "autoScalingGroupArn=${ASG_ARN},managedScaling={status=ENABLED,targetCapacity=100,minimumScalingStepSize=1,maximumScalingStepSize=1},managedTerminationProtection=ENABLED" \
    --region "${REGION}" > /dev/null
fi

# Attach capacity provider to cluster
aws ecs put-cluster-capacity-providers \
  --cluster "${CLUSTER}" \
  --capacity-providers "${CAP_PROVIDER}" \
  --default-capacity-provider-strategy "capacityProvider=${CAP_PROVIDER},weight=1,base=1" \
  --region "${REGION}" > /dev/null 2>&1 || true
echo "  ✓ Capacity Provider: ${CAP_PROVIDER}"

# ═══════════════════════════════════════════════════════════
#  Step 5: IAM Roles
# ═══════════════════════════════════════════════════════════
echo "━━━ [5/11] IAM Roles ━━━"
ECS_TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
CB_TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

for ROLE in "${TASK_ROLE}" "${EXEC_ROLE}"; do
  aws iam get-role --role-name "${ROLE}" > /dev/null 2>&1 || \
    aws iam create-role --role-name "${ROLE}" --assume-role-policy-document "${ECS_TRUST}" > /dev/null
done

aws iam get-role --role-name "${CODEBUILD_ROLE}" > /dev/null 2>&1 || \
  aws iam create-role --role-name "${CODEBUILD_ROLE}" --assume-role-policy-document "${CB_TRUST}" > /dev/null

aws iam attach-role-policy --role-name "${EXEC_ROLE}" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true

# Task role: S3 + logs
aws iam put-role-policy --role-name "${TASK_ROLE}" --policy-name "${PROJECT}-access" --policy-document "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[
    {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::${S3_MODELS}\",\"arn:aws:s3:::${S3_MODELS}/*\"]},
    {\"Effect\":\"Allow\",\"Action\":[\"logs:CreateLogStream\",\"logs:PutLogEvents\"],\"Resource\":\"*\"}
  ]
}"

# CodeBuild role: ECR + S3 + logs
aws iam put-role-policy --role-name "${CODEBUILD_ROLE}" --policy-name "${PROJECT}-codebuild" --policy-document "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[
    {\"Effect\":\"Allow\",\"Action\":[\"ecr:GetAuthorizationToken\"],\"Resource\":\"*\"},
    {\"Effect\":\"Allow\",\"Action\":[\"ecr:BatchCheckLayerAvailability\",\"ecr:GetDownloadUrlForLayer\",\"ecr:BatchGetImage\",\"ecr:PutImage\",\"ecr:InitiateLayerUpload\",\"ecr:UploadLayerPart\",\"ecr:CompleteLayerUpload\"],\"Resource\":\"arn:aws:ecr:${REGION}:${ACCOUNT_ID}:repository/${ECR_REPO}\"},
    {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:GetBucketLocation\",\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::${S3_BUILD}\",\"arn:aws:s3:::${S3_BUILD}/*\"]},
    {\"Effect\":\"Allow\",\"Action\":[\"logs:CreateLogGroup\",\"logs:CreateLogStream\",\"logs:PutLogEvents\"],\"Resource\":\"*\"}
  ]
}"
echo "  ✓ Roles ready"

# Sleep briefly so IAM propagates
sleep 5

# ═══════════════════════════════════════════════════════════
#  Step 6: CloudWatch Log Group
# ═══════════════════════════════════════════════════════════
echo "━━━ [6/11] CloudWatch Logs ━━━"
aws logs create-log-group --log-group-name "${LOG_GROUP}" --region "${REGION}" 2>/dev/null || true
aws logs create-log-group --log-group-name "/codebuild/${PROJECT}" --region "${REGION}" 2>/dev/null || true
echo "  ✓ Log groups ready"

# ═══════════════════════════════════════════════════════════
#  Step 7: CodeBuild - build Docker image on AWS (fast!)
# ═══════════════════════════════════════════════════════════
echo "━━━ [7/11] Building Docker Image on AWS (CodeBuild) ━━━"
echo "  Building natively on x86_64 with fast networking - full PyTorch GPU..."

CODEBUILD_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${CODEBUILD_ROLE}"

# Create/update CodeBuild project
aws codebuild create-project \
  --name "${CODEBUILD_PROJECT}" \
  --source "{\"type\":\"S3\",\"location\":\"${S3_BUILD}/backend-src.zip\"}" \
  --artifacts "{\"type\":\"NO_ARTIFACTS\"}" \
  --environment "{
    \"type\":\"LINUX_CONTAINER\",
    \"image\":\"aws/codebuild/standard:7.0\",
    \"computeType\":\"BUILD_GENERAL1_LARGE\",
    \"privilegedMode\":true,
    \"environmentVariables\":[
      {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"${REGION}\"},
      {\"name\":\"AWS_ACCOUNT_ID\",\"value\":\"${ACCOUNT_ID}\"},
      {\"name\":\"IMAGE_REPO_NAME\",\"value\":\"${ECR_REPO}\"},
      {\"name\":\"IMAGE_TAG\",\"value\":\"latest\"}
    ]
  }" \
  --service-role "${CODEBUILD_ROLE_ARN}" \
  --region "${REGION}" > /dev/null 2>&1 || \
aws codebuild update-project \
  --name "${CODEBUILD_PROJECT}" \
  --source "{\"type\":\"S3\",\"location\":\"${S3_BUILD}/backend-src.zip\"}" \
  --environment "{
    \"type\":\"LINUX_CONTAINER\",
    \"image\":\"aws/codebuild/standard:7.0\",
    \"computeType\":\"BUILD_GENERAL1_LARGE\",
    \"privilegedMode\":true,
    \"environmentVariables\":[
      {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"${REGION}\"},
      {\"name\":\"AWS_ACCOUNT_ID\",\"value\":\"${ACCOUNT_ID}\"},
      {\"name\":\"IMAGE_REPO_NAME\",\"value\":\"${ECR_REPO}\"},
      {\"name\":\"IMAGE_TAG\",\"value\":\"latest\"}
    ]
  }" \
  --service-role "${CODEBUILD_ROLE_ARN}" \
  --region "${REGION}" > /dev/null 2>&1

# Start build
BUILD_ID=$(aws codebuild start-build \
  --project-name "${CODEBUILD_PROJECT}" \
  --buildspec-override '{
    "version": "0.2",
    "phases": {
      "pre_build": {
        "commands": [
          "echo Logging in to ECR...",
          "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"
        ]
      },
      "build": {
        "commands": [
          "echo Building Docker image with full PyTorch GPU...",
          "docker build --platform linux/amd64 -t $IMAGE_REPO_NAME:$IMAGE_TAG .",
          "docker tag $IMAGE_REPO_NAME:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME:$IMAGE_TAG"
        ]
      },
      "post_build": {
        "commands": [
          "echo Pushing image to ECR...",
          "docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME:$IMAGE_TAG",
          "echo Build completed successfully"
        ]
      }
    }
  }' \
  --region "${REGION}" \
  --query 'build.id' --output text)

echo "  Build started: ${BUILD_ID}"
echo "  Waiting for build to complete..."

# Poll build status
while true; do
  STATUS=$(aws codebuild batch-get-builds --ids "${BUILD_ID}" \
    --query 'builds[0].buildStatus' --output text --region "${REGION}" 2>/dev/null)
  PHASE=$(aws codebuild batch-get-builds --ids "${BUILD_ID}" \
    --query 'builds[0].currentPhase' --output text --region "${REGION}" 2>/dev/null)

  if [ "${STATUS}" = "SUCCEEDED" ]; then
    echo ""
    echo "  ✓ Docker image built and pushed to ECR!"
    break
  elif [ "${STATUS}" = "FAILED" ] || [ "${STATUS}" = "FAULT" ] || [ "${STATUS}" = "TIMED_OUT" ]; then
    echo ""
    echo "  ❌ Build failed: ${STATUS}"
    echo "  Check logs: aws codebuild batch-get-builds --ids ${BUILD_ID} --region ${REGION}"
    exit 1
  fi

  printf "  ⏳ Status: %-12s Phase: %-20s\r" "${STATUS}" "${PHASE}"
  sleep 15
done

# ═══════════════════════════════════════════════════════════
#  Step 8: Load Balancer
# ═══════════════════════════════════════════════════════════
echo "━━━ [8/11] Load Balancer ━━━"

ALB_ARN=$(aws elbv2 describe-load-balancers --names "${ALB_NAME}" --query 'LoadBalancers[0].LoadBalancerArn' --output text --region "${REGION}" 2>/dev/null || echo "None")
if [ "${ALB_ARN}" = "None" ] || [ -z "${ALB_ARN}" ]; then
  ALB_ARN=$(aws elbv2 create-load-balancer --name "${ALB_NAME}" --subnets "${SUBNET_A}" "${SUBNET_B}" \
    --security-groups "${SG_ID}" --scheme internet-facing --type application \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text --region "${REGION}")
fi
ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns "${ALB_ARN}" \
  --query 'LoadBalancers[0].DNSName' --output text --region "${REGION}")
echo "  ✓ ALB: ${ALB_DNS}"

TG_ARN=$(aws elbv2 describe-target-groups --names "${TG_NAME}" --query 'TargetGroups[0].TargetGroupArn' --output text --region "${REGION}" 2>/dev/null || echo "None")
if [ "${TG_ARN}" = "None" ] || [ -z "${TG_ARN}" ]; then
  TG_ARN=$(aws elbv2 create-target-group --name "${TG_NAME}" --protocol HTTP --port 8000 \
    --vpc-id "${VPC_ID}" --target-type ip --health-check-path "/health" \
    --health-check-interval-seconds 30 --healthy-threshold-count 2 \
    --query 'TargetGroups[0].TargetGroupArn' --output text --region "${REGION}")
fi

LISTENER_ARN=$(aws elbv2 describe-listeners --load-balancer-arn "${ALB_ARN}" \
  --query 'Listeners[0].ListenerArn' --output text --region "${REGION}" 2>/dev/null || echo "None")
if [ "${LISTENER_ARN}" = "None" ] || [ -z "${LISTENER_ARN}" ]; then
  aws elbv2 create-listener --load-balancer-arn "${ALB_ARN}" --protocol HTTP --port 80 \
    --default-actions "Type=forward,TargetGroupArn=${TG_ARN}" --region "${REGION}" > /dev/null
fi
echo "  ✓ Listener: HTTP:80 → backend"

BACKEND_URL="http://${ALB_DNS}"

# ═══════════════════════════════════════════════════════════
#  Step 9: ECS Cluster + Task + Service
# ═══════════════════════════════════════════════════════════
echo "━━━ [9/11] ECS Cluster & Service ━━━"

aws ecs describe-clusters --clusters "${CLUSTER}" --query 'clusters[0].status' --output text --region "${REGION}" 2>/dev/null | grep -q ACTIVE || \
  aws ecs create-cluster --cluster-name "${CLUSTER}" --region "${REGION}" > /dev/null
echo "  ✓ Cluster: ${CLUSTER}"

TASK_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${TASK_ROLE}"
EXEC_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EXEC_ROLE}"

aws ecs register-task-definition \
  --family "${TASK_FAMILY}" \
  --network-mode awsvpc \
  --requires-compatibilities EC2 \
  --cpu "${CPU}" --memory "${MEMORY}" \
  --task-role-arn "${TASK_ROLE_ARN}" \
  --execution-role-arn "${EXEC_ROLE_ARN}" \
  --container-definitions "[{
    \"name\":\"${PROJECT}-backend\",
    \"image\":\"${ECR_URI}:latest\",
    \"cpu\":${CPU},
    \"memory\":${MEMORY},
    \"portMappings\":[{\"containerPort\":8000,\"protocol\":\"tcp\"}],
    \"environment\":[
      {\"name\":\"S3_BUCKET\",\"value\":\"${S3_MODELS}\"},
      {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"${REGION}\"},
      {\"name\":\"ALLOWED_ORIGINS\",\"value\":\"*\"},
      {\"name\":\"DEVICE\",\"value\":\"${DEVICE_MODE}\"},
      {\"name\":\"COGNITO_USER_POOL_ID\",\"value\":\"${COGNITO_USER_POOL_ID}\"},
      {\"name\":\"COGNITO_CLIENT_ID\",\"value\":\"${COGNITO_CLIENT_ID}\"},
      {\"name\":\"COGNITO_CLIENT_SECRET\",\"value\":\"${COGNITO_CLIENT_SECRET}\"},
      {\"name\":\"AWS_EC2_METADATA_DISABLED\",\"value\":\"true\"}
    ]${GPU_RESOURCE_JSON},
    \"logConfiguration\":{
      \"logDriver\":\"awslogs\",
      \"options\":{
        \"awslogs-group\":\"${LOG_GROUP}\",
        \"awslogs-region\":\"${REGION}\",
        \"awslogs-stream-prefix\":\"ecs\"
      }
    },
    \"essential\":true
  }]" --region "${REGION}" > /dev/null
echo "  ✓ Task: ${TASK_FAMILY} (${TASK_SIZE_LABEL})"

# Delete old Fargate service if it exists (can't change launch type in-place)
EXISTING_SVC=$(aws ecs describe-services --cluster "${CLUSTER}" --services "${SERVICE}" \
  --query 'services[0].status' --output text --region "${REGION}" 2>/dev/null || echo "None")
if [ "${EXISTING_SVC}" = "ACTIVE" ]; then
  # Check if old service uses Fargate
  OLD_LAUNCH=$(aws ecs describe-services --cluster "${CLUSTER}" --services "${SERVICE}" \
    --query 'services[0].launchType' --output text --region "${REGION}" 2>/dev/null || echo "")
  if [ "${OLD_LAUNCH}" = "FARGATE" ]; then
    echo "  Deleting old Fargate service to switch to EC2 GPU..."
    aws ecs update-service --cluster "${CLUSTER}" --service "${SERVICE}" \
      --desired-count 0 --region "${REGION}" > /dev/null
    sleep 5
    aws ecs delete-service --cluster "${CLUSTER}" --service "${SERVICE}" \
      --force --region "${REGION}" > /dev/null
    echo "  Waiting for old service to drain..."
    sleep 15
  else
    echo "  Updating EC2 GPU service (force new deployment)..."
    aws ecs update-service --cluster "${CLUSTER}" --service "${SERVICE}" \
      --task-definition "${TASK_FAMILY}" \
      --force-new-deployment --desired-count 1 --region "${REGION}" > /dev/null
    EXISTING_SVC="UPDATED"
  fi
fi

if [ "${EXISTING_SVC}" != "UPDATED" ]; then
  echo "  Creating EC2 GPU service..."
  aws ecs create-service \
    --cluster "${CLUSTER}" \
    --service-name "${SERVICE}" \
    --task-definition "${TASK_FAMILY}" \
    --desired-count 1 \
    --capacity-provider-strategy "capacityProvider=${CAP_PROVIDER},weight=1,base=1" \
    --load-balancers "targetGroupArn=${TG_ARN},containerName=${PROJECT}-backend,containerPort=8000" \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_A},${SUBNET_B}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}" \
    --region "${REGION}" > /dev/null
fi
echo "  ✓ Service: ${SERVICE} (GPU-accelerated)"

# ═══════════════════════════════════════════════════════════
#  Step 10: Build & Deploy Frontend to S3
# ═══════════════════════════════════════════════════════════
echo "━━━ [10/11] Building & Deploying Frontend ━━━"

cd "${SCRIPT_DIR}/frontend"
echo "  Building Next.js with relative API_URL for CloudFront usage..."
NEXT_PUBLIC_API_URL="" npm run build >/dev/null 2>&1 || NEXT_PUBLIC_API_URL="" npm run build
echo "  ✓ Frontend built (static export)"

aws s3 sync out/ "s3://${S3_FRONTEND}/" --delete --region "${REGION}" > /dev/null
echo "  ✓ Uploaded to s3://${S3_FRONTEND}/"

aws s3 website "s3://${S3_FRONTEND}" --index-document index.html --error-document index.html --region "${REGION}"

aws s3api put-public-access-block --bucket "${S3_FRONTEND}" --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" --region "${REGION}" 2>/dev/null || true

aws s3api put-bucket-policy --bucket "${S3_FRONTEND}" --policy "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{
    \"Sid\":\"PublicRead\",
    \"Effect\":\"Allow\",
    \"Principal\":\"*\",
    \"Action\":\"s3:GetObject\",
    \"Resource\":\"arn:aws:s3:::${S3_FRONTEND}/*\"
  }]
}" --region "${REGION}"
cd "${SCRIPT_DIR}"
echo "  ✓ S3 website hosting enabled"

# ═══════════════════════════════════════════════════════════
#  Step 11: CloudFront CDN
# ═══════════════════════════════════════════════════════════
echo "━━━ [11/11] CloudFront CDN ━━━"
S3_WEBSITE_ENDPOINT="${S3_FRONTEND}.s3-website-${REGION}.amazonaws.com"

CF_DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='PolyPred Frontend'].Id | [0]" \
  --output text 2>/dev/null || echo "None")

if [ "${CF_DIST_ID}" = "None" ] || [ -z "${CF_DIST_ID}" ] || [ "${CF_DIST_ID}" = "null" ]; then
  CF_CONFIG=$(cat <<CFEOF
{
  "CallerReference": "polypred-$(date +%s)",
  "Comment": "PolyPred Frontend",
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "S3-${S3_FRONTEND}",
      "DomainName": "${S3_WEBSITE_ENDPOINT}",
      "CustomOriginConfig": {
        "HTTPPort": 80,
        "HTTPSPort": 443,
        "OriginProtocolPolicy": "http-only"
      }
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-${S3_FRONTEND}",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] }
    },
    "ForwardedValues": { "QueryString": false, "Cookies": { "Forward": "none" } },
    "MinTTL": 0, "DefaultTTL": 86400, "MaxTTL": 31536000,
    "Compress": true
  },
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "CustomErrorResponses": {
    "Quantity": 2,
    "Items": [
      { "ErrorCode": 404, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 0 },
      { "ErrorCode": 403, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 0 }
    ]
  }
}
CFEOF
)
  CF_DIST_ID=$(aws cloudfront create-distribution --distribution-config "${CF_CONFIG}" \
    --query 'Distribution.Id' --output text 2>/dev/null || echo "skipped")
fi

if [ "${CF_DIST_ID}" != "skipped" ] && [ -n "${CF_DIST_ID}" ]; then
  CF_DOMAIN=$(aws cloudfront get-distribution --id "${CF_DIST_ID}" --query 'Distribution.DomainName' --output text 2>/dev/null || echo "")
  echo "  ✓ CloudFront: https://${CF_DOMAIN}"
  FRONTEND_URL="https://${CF_DOMAIN}"
  
  echo "  Invalidating CloudFront edge caches..."
  aws cloudfront create-invalidation --distribution-id "${CF_DIST_ID}" --paths "/*" > /dev/null 2>&1
  # Also invalidate the copolpred.com custom domain distribution
  CUSTOM_CF_ID="E1UUS1V1XNA37S"
  echo "  Invalidating copolpred.com CDN (${CUSTOM_CF_ID})..."
  aws cloudfront create-invalidation --distribution-id "${CUSTOM_CF_ID}" --paths "/*" > /dev/null 2>&1
else
  FRONTEND_URL="http://${S3_WEBSITE_ENDPOINT}"
  echo "  ⚠ CloudFront skipped - using S3 website URL"
fi

# ═══════════════════════════════════════════════════════════
#  Wait for backend
# ═══════════════════════════════════════════════════════════
echo ""
echo "━━━ Waiting for backend to start... ━━━"
for i in $(seq 1 40); do
  RUNNING=$(aws ecs describe-services --cluster "${CLUSTER}" --services "${SERVICE}" \
    --query 'services[0].deployments[0].runningCount' --output text --region "${REGION}" 2>/dev/null || echo "0")
  if [ "${RUNNING}" != "0" ] && [ "${RUNNING}" != "None" ]; then
    echo "  ✓ Backend running! (${RUNNING} task)"
    break
  fi
  printf "  ⏳ Waiting for ECS task... (%d/40)\r" "$i"
  sleep 15
done

# Test health
sleep 10
HEALTH=$(curl -s --max-time 10 "${BACKEND_URL}/health" 2>/dev/null || echo '{"status":"pending"}')
echo "  Health check: ${HEALTH}"

# ═══════════════════════════════════════════════════════════
#  DONE
# ═══════════════════════════════════════════════════════════
echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                🚀 PolyPred Deployment Complete!                  ║"
echo "╠════════════════════════════════════════════════════════════════════╣"
echo "║                                                                  ║"
echo "║  🌐 SHARE THIS URL:                                             ║"
echo "║     ${FRONTEND_URL}"
echo "║                                                                  ║"
echo "║  🔗 Backend API:  ${BACKEND_URL}"
echo "║  📊 API Docs:     ${BACKEND_URL}/docs"
echo "║                                                                  ║"
echo "║  AWS Resources:                                                  ║"
echo "║    ECR:     ${ECR_URI}"
echo "║    ECS:     ${CLUSTER} / ${SERVICE}"
echo "║    ALB:     ${ALB_DNS}"
echo "║    S3:      s3://${S3_FRONTEND}/"
echo "║    Logs:    ${LOG_GROUP}"
echo "║                                                                  ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "💡 Redeploy:    ./deploy-aws.sh"
echo "💡 Tear down:   ./teardown-aws.sh --confirm"
