#!/usr/bin/env bash
set -euo pipefail

cd frontend
echo "Building frontend..."
NEXT_PUBLIC_API_URL="http://polypred-alb-175898082.us-east-1.elb.amazonaws.com" npm run build
cd ..

echo "Creating S3 bucket..."
aws s3api create-bucket --bucket copolpred.com --region us-east-1 > /dev/null

echo "Syncing to S3..."
aws s3 sync frontend/out/ s3://copolpred.com/ --delete --region us-east-1 > /dev/null

echo "Configuring S3 website..."
aws s3 website s3://copolpred.com --index-document index.html --error-document index.html --region us-east-1

aws s3api put-public-access-block --bucket copolpred.com --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" --region us-east-1 2>/dev/null || true

aws s3api put-bucket-policy --bucket copolpred.com --policy '{
  "Version":"2012-10-17",
  "Statement":[{
    "Sid":"PublicRead",
    "Effect":"Allow",
    "Principal":"*",
    "Action":"s3:GetObject",
    "Resource":"arn:aws:s3:::copolpred.com/*"
  }]
}' --region us-east-1

echo "Creating Route 53 zone..."
HZ_ID=$(aws route53 create-hosted-zone --name copolpred.com --caller-reference $(date +%s) --query 'HostedZone.Id' --output text)

echo "Setting Alias record..."
cat > route53-s3.json <<EOF
{
  "Comment": "Alias to S3 website",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "copolpred.com.",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z3AQBSTGFYJSTF",
          "DNSName": "s3-website-us-east-1.amazonaws.com.",
          "EvaluateTargetHealth": false
        }
      }
    }
  ]
}
EOF
aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" --change-batch file://route53-s3.json > /dev/null

echo "==================== NAMESERVERS ===================="
aws route53 get-hosted-zone --id "$HZ_ID" --query 'DelegationSet.NameServers' --output table
echo "====================================================="
