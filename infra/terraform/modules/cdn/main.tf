data "aws_caller_identity" "current" {}

# OAC: lets CloudFront sign requests to S3 with SigV4. Replaces the older
# Origin Access Identity (OAI) pattern. Required for new distributions.
resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.project_name}-site-oac"
  description                       = "OAC for the static site bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  comment             = "${var.project_name} site + api"
  price_class         = "PriceClass_100" # NA + EU edges only. Cheaper. Other classes add Asia/SA.

  # Origin 1: S3 bucket holding the static frontend.
  origin {
    origin_id                = "s3-site"
    domain_name              = var.site_bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  # Origin 2: the EC2 backend. CloudFront talks HTTP to it; viewers still get HTTPS.
  origin {
    origin_id   = "ec2-api"
    domain_name = var.api_origin_domain

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Default behavior: serve from S3 (the frontend).
  default_cache_behavior {
    target_origin_id       = "s3-site"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # CachingOptimized: AWS-managed policy with sensible TTLs and gzip/brotli.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # /api/* routes to the EC2. No caching, all methods, forward everything.
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "ec2-api"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # CachingDisabled + AllViewer: no caching, forward all headers/cookies/qs to origin.
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Default CloudFront cert covers *.cloudfront.net. Add aliases + ACM cert
  # later when we have a domain.
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# Bucket policy: lets THIS CloudFront distribution (and only this one)
# read from the site bucket via OAC.
data "aws_iam_policy_document" "site_bucket" {
  statement {
    sid       = "AllowCloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${var.site_bucket_arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.main.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = var.site_bucket_id
  policy = data.aws_iam_policy_document.site_bucket.json
}
