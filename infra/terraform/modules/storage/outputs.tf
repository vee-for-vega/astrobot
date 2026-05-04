output "bucket_id" {
  description = "Bucket name. Used by deploy scripts and the cdn module."
  value       = aws_s3_bucket.site.id
}

output "bucket_arn" {
  description = "Bucket ARN. The cdn module uses this in the OAC bucket policy."
  value       = aws_s3_bucket.site.arn
}

output "bucket_regional_domain_name" {
  description = "Regional S3 endpoint for the bucket. CloudFront's OAC origin requires this exact form."
  value       = aws_s3_bucket.site.bucket_regional_domain_name
}
