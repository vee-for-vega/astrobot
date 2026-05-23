#!/usr/bin/env bash
# Build the vite app and sync web/dist to S3, then invalidate CloudFront.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ npm ci && npm run build (web/)"
cd "$REPO_ROOT/web"
npm ci
npm run build

cd "$REPO_ROOT/infra/terraform/envs/prod"

BUCKET=$(terraform output -raw site_bucket)
DIST_ID=$(terraform output -raw cloudfront_distribution_id)
SITE_URL=$(terraform output -raw site_url)

cd "$REPO_ROOT"

echo "→ aws s3 sync web/dist/ -> s3://$BUCKET"
# HTML: short cache, must-revalidate (so updates show up on hard reload).
# Hashed JS/CSS assets: long cache; CloudFront invalidation handles refresh.
aws s3 sync web/dist/ "s3://$BUCKET/" --delete \
  --exclude "*" --include "*.html" \
  --cache-control "public, max-age=60, must-revalidate"

aws s3 sync web/dist/ "s3://$BUCKET/" --delete \
  --exclude "*.html" \
  --cache-control "public, max-age=86400"

echo "→ invalidating CloudFront /*"
aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --query 'Invalidation.Id' --output text

echo "✓ frontend deployed. live at: $SITE_URL"
