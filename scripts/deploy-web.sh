#!/usr/bin/env bash
# Sync web/ to S3 and invalidate CloudFront so the new files go live.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/infra/terraform/envs/prod"

BUCKET=$(terraform output -raw site_bucket)
DIST_ID=$(terraform output -raw cloudfront_distribution_id)
SITE_URL=$(terraform output -raw site_url)

cd "$REPO_ROOT"

echo "→ aws s3 sync web/ -> s3://$BUCKET"
# HTML: short cache, must-revalidate (so updates show up on hard reload).
# JS/CSS: longer cache; CloudFront invalidation is what makes them update.
aws s3 sync web/ "s3://$BUCKET/" --delete \
  --exclude "*" --include "*.html" \
  --cache-control "public, max-age=60, must-revalidate"

aws s3 sync web/ "s3://$BUCKET/" --delete \
  --exclude "*.html" \
  --cache-control "public, max-age=86400"

echo "→ invalidating CloudFront /*"
aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --query 'Invalidation.Id' --output text

echo "✓ frontend deployed. live at: $SITE_URL"
