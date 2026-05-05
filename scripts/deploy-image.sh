#!/usr/bin/env bash
# Build the bot image, push to ECR, and tell the EC2 to pull the new one.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/infra/terraform/envs/prod"

REGION=$(terraform output -raw region 2>/dev/null || echo "us-east-1")
ECR_URL=$(terraform output -raw ecr_repository_url)
INSTANCE_ID=$(terraform output -raw bot_instance_id)
REGISTRY="${ECR_URL%%/*}"

cd "$REPO_ROOT"

echo "→ docker login to $REGISTRY"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$REGISTRY"

echo "→ docker build"
docker build -f api/Dockerfile -t astrobot:latest .

echo "→ tag + push"
docker tag astrobot:latest "$ECR_URL:latest"
docker push "$ECR_URL:latest"

echo "→ restarting astrobot.service on $INSTANCE_ID via SSM"
aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["systemctl restart astrobot.service"]' \
  --query 'Command.CommandId' --output text >/dev/null

echo "✓ image deployed. tail logs with:"
echo "    aws ssm start-session --target $INSTANCE_ID"
echo "    journalctl -u astrobot.service -f"
