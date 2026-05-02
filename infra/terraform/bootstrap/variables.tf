variable "project_name" {
  description = "Used as a prefix for the state bucket and lock table."
  type        = string
  default     = "astrobot"
}

variable "region" {
  description = "AWS region. us-east-1 is required for CloudFront ACM certs later."
  type        = string
  default     = "us-east-1"
}

variable "account_suffix" {
  description = <<-EOT
    Short string to make the S3 bucket name globally unique across all of AWS.
    Use the last 4 digits of your AWS account ID, your initials + a number,
    or any short lowercase string. Example: "ms42" or "9b7c".
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{2,16}$", var.account_suffix))
    error_message = "account_suffix must be 2-16 chars, lowercase letters, digits, or hyphens."
  }
}
