#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
#  PolyPred - Tear Down AWS Resources
#  Usage: ./teardown-aws.sh [--region us-east-1] [--confirm]
# ══════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT="polypred"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
CONFIRM=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --region)  REGION="$2"; shift 2;;
    --confirm) CONFIRM=true; shift;;
    *)         echo "Unknown: $1"; exit 1;;
  esac
done

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${PROJECT}-backend"
CLUSTER="${PROJECT}-cluster"
SERVICE="${PROJECT}-service"
TASK_FAMILY="${PROJECT}-task"
S3_MODELS="${PROJECT}-models-${ACCOUNT_ID}"
S3_FRONTEND="${PROJECT}-frontend-${ACCOUNT_ID}"
ALB_NAME="${PROJECT}-alb"
TG_NAME="${PROJECT}-tg"
SG_NAME="${PROJECT}-sg"
LOG_GROUP="/ecs/${PROJECT}"
TASK_ROLE="${PROJECT}-task-role"
EXEC_ROLE="${PROJECT}-exec-role"
ASG_NAME="${PROJECT}-gpu-asg"
LAUNCH_TEMPLATE="${PROJECT}-gpu-lt"
CAP_PROVIDER="${PROJECT}-gpu-cap"
CODEBUILD_ROLE="${PROJECT}-codebuild-role"
CODEBUILD_PROJECT="${PROJECT}-build"
S3_BUILD="${PROJECT}-build-${ACCOUNT_ID}"

if [ "${CONFIRM}" != true ]; then
  echo "⚠️  This will DELETE all PolyPred AWS resources in ${REGION}."
  echo "    Run with --confirm to proceed."
  echo ""
  echo "    ./teardown-aws.sh --confirm"
  exit 0
fi

echo "Tearing down PolyPred in ${REGION}..."

# 1. Delete ECS service
echo "[1] ECS Service..."
aws ecs update-service --cluster "${CLUSTER}" --service "${SERVICE}" --desired-count 0 --region "${REGION}" 2>/dev/null || true
aws ecs delete-service --cluster "${CLUSTER}" --service "${SERVICE}" --force --region "${REGION}" 2>/dev/null || true

# 2. Deregister task definitions
echo "[2] Task Definitions..."
for TD in $(aws ecs list-task-definitions --family-prefix "${TASK_FAMILY}" --query 'taskDefinitionArns[*]' --output text --region "${REGION}" 2>/dev/null); do
  aws ecs deregister-task-definition --task-definition "${TD}" --region "${REGION}" > /dev/null 2>&1 || true
done

# 3. Delete ECS cluster
echo "[3] ECS Cluster..."
# Remove capacity providers before deleting cluster
aws ecs put-cluster-capacity-providers --cluster "${CLUSTER}" \
  --capacity-providers "" --default-capacity-provider-strategy "" \
  --region "${REGION}" 2>/dev/null || true
aws ecs delete-cluster --cluster "${CLUSTER}" --region "${REGION}" 2>/dev/null || true

# 3b. GPU Capacity Provider + ASG + Launch Template
echo "[3b] GPU Resources..."
# Delete capacity provider (can't be deleted directly, just deregister)
aws ecs delete-capacity-provider --capacity-provider "${CAP_PROVIDER}" --region "${REGION}" 2>/dev/null || true

# Delete ASG
aws autoscaling update-auto-scaling-group --auto-scaling-group-name "${ASG_NAME}" \
  --min-size 0 --max-size 0 --desired-capacity 0 --region "${REGION}" 2>/dev/null || true
sleep 5
aws autoscaling delete-auto-scaling-group --auto-scaling-group-name "${ASG_NAME}" \
  --force-delete --region "${REGION}" 2>/dev/null || true

# Delete Launch Template
aws ec2 delete-launch-template --launch-template-name "${LAUNCH_TEMPLATE}" --region "${REGION}" 2>/dev/null || true

# Delete CodeBuild
aws codebuild delete-project --name "${CODEBUILD_PROJECT}" --region "${REGION}" 2>/dev/null || true
aws iam delete-role-policy --role-name "${CODEBUILD_ROLE}" --policy-name "${PROJECT}-codebuild" 2>/dev/null || true
aws iam delete-role --role-name "${CODEBUILD_ROLE}" 2>/dev/null || true

# 4. Delete ALB + Target Group + Listener
echo "[4] Load Balancer..."
ALB_ARN=$(aws elbv2 describe-load-balancers --names "${ALB_NAME}" --query 'LoadBalancers[0].LoadBalancerArn' --output text --region "${REGION}" 2>/dev/null || echo "None")
if [ "${ALB_ARN}" != "None" ] && [ -n "${ALB_ARN}" ]; then
  for LN in $(aws elbv2 describe-listeners --load-balancer-arn "${ALB_ARN}" --query 'Listeners[*].ListenerArn' --output text --region "${REGION}" 2>/dev/null); do
    aws elbv2 delete-listener --listener-arn "${LN}" --region "${REGION}" 2>/dev/null || true
  done
  aws elbv2 delete-load-balancer --load-balancer-arn "${ALB_ARN}" --region "${REGION}" 2>/dev/null || true
fi
TG_ARN=$(aws elbv2 describe-target-groups --names "${TG_NAME}" --query 'TargetGroups[0].TargetGroupArn' --output text --region "${REGION}" 2>/dev/null || echo "None")
if [ "${TG_ARN}" != "None" ] && [ -n "${TG_ARN}" ]; then
  aws elbv2 delete-target-group --target-group-arn "${TG_ARN}" --region "${REGION}" 2>/dev/null || true
fi

# 5. Delete CloudFront
echo "[5] CloudFront..."
S3_WEBSITE="${S3_FRONTEND}.s3-website-${REGION}.amazonaws.com"
CF_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?Origins.Items[0].DomainName=='${S3_WEBSITE}'].Id | [0]" --output text 2>/dev/null || echo "None")
if [ "${CF_ID}" != "None" ] && [ -n "${CF_ID}" ] && [ "${CF_ID}" != "null" ]; then
  echo "  Disabling CloudFront ${CF_ID}... (full deletion can take minutes)"
  ETAG=$(aws cloudfront get-distribution-config --id "${CF_ID}" --query 'ETag' --output text)
  CONFIG=$(aws cloudfront get-distribution-config --id "${CF_ID}" --query 'DistributionConfig')
  DISABLED=$(echo "${CONFIG}" | python3 -c "import sys,json; c=json.load(sys.stdin); c['Enabled']=False; print(json.dumps(c))")
  aws cloudfront update-distribution --id "${CF_ID}" --if-match "${ETAG}" --distribution-config "${DISABLED}" > /dev/null 2>&1 || true
  echo "  CloudFront disabled (delete manually once status=Deployed: aws cloudfront delete-distribution --id ${CF_ID} --if-match <etag>)"
fi

# 6. Empty & delete S3 buckets
echo "[6] S3 Buckets..."
for BUCKET in "${S3_MODELS}" "${S3_FRONTEND}" "${S3_BUILD}"; do
  aws s3 rm "s3://${BUCKET}" --recursive --region "${REGION}" 2>/dev/null || true
  aws s3api delete-bucket --bucket "${BUCKET}" --region "${REGION}" 2>/dev/null || true
done

# 7. ECR
echo "[7] ECR..."
aws ecr delete-repository --repository-name "${ECR_REPO}" --force --region "${REGION}" 2>/dev/null || true

# 8. Security Group
echo "[8] Security Group..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region "${REGION}" 2>/dev/null || echo "None")
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text --region "${REGION}" 2>/dev/null || echo "None")
if [ "${SG_ID}" != "None" ] && [ -n "${SG_ID}" ]; then
  # Wait a bit for ENIs to detach
  sleep 5
  aws ec2 delete-security-group --group-id "${SG_ID}" --region "${REGION}" 2>/dev/null || \
    echo "  ⚠ SG ${SG_ID} still in use, delete manually later"
fi

# 9. IAM Roles
echo "[9] IAM..."
aws iam delete-role-policy --role-name "${TASK_ROLE}" --policy-name "${PROJECT}-access" 2>/dev/null || true
aws iam delete-role --role-name "${TASK_ROLE}" 2>/dev/null || true
aws iam detach-role-policy --role-name "${EXEC_ROLE}" --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true
aws iam delete-role --role-name "${EXEC_ROLE}" 2>/dev/null || true

# 10. CloudWatch
echo "[10] CloudWatch..."
aws logs delete-log-group --log-group-name "${LOG_GROUP}" --region "${REGION}" 2>/dev/null || true

echo ""
echo "✅ PolyPred AWS resources torn down."
