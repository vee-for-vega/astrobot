variable "project_name" {
  description = "Used as a prefix for the bucket name."
  type        = string
}

variable "bucket_suffix" {
  description = <<-EOT
    Short string to make the S3 bucket name globally unique. Reuse the same
    suffix you used for the bootstrap bucket (e.g. last 4 of account ID).
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{2,16}$", var.bucket_suffix))
    error_message = "bucket_suffix must be 2-16 chars, lowercase letters, digits, or hyphens."
  }
}
