variable "project_name" {
  type = string
}

variable "site_bucket_id" {
  description = "S3 bucket name from the storage module."
  type        = string
}

variable "site_bucket_arn" {
  description = "S3 bucket ARN. Used in the bucket policy that grants CloudFront read access."
  type        = string
}

variable "site_bucket_regional_domain_name" {
  description = "Regional S3 endpoint, e.g. astrobot-site-7061.s3.us-east-1.amazonaws.com. OAC requires this exact form."
  type        = string
}

variable "api_origin_domain" {
  description = "DNS name of the EC2/EIP. CloudFront proxies /api/* to this origin over HTTP."
  type        = string
}
