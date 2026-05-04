resource "aws_s3_bucket" "site" {
  bucket = "${var.project_name}-site-${var.bucket_suffix}"
}

# Versioning: every PUT keeps the prior version. Roll back a broken
# frontend deploy by restoring the previous object version.
resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Encryption at rest. SSE-S3 (AES256) is free and managed by AWS.
resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public access at the bucket level, even if
# someone later adds a public bucket policy by mistake. CloudFront will read
# the bucket via Origin Access Control (OAC) — no public access needed.
resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket policy intentionally NOT defined here. The policy that allows
# CloudFront's OAC to GetObject lives in the cdn module — it
# needs to reference the CloudFront distribution ARN, which doesn't exist
# until that module is built.
