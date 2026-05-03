variable "project_name" {
  description = "Resource name prefix and Project tag value."
  type        = string
  default     = "astrobot"
}

variable "environment" {
  description = "Environment name. Drives the Environment tag and resource naming."
  type        = string
  default     = "prod"
}

variable "region" {
  description = "AWS region. us-east-1 is required for CloudFront ACM certs."
  type        = string
  default     = "us-east-1"
}

# t3.small for now. Switch to t4g.small once stable —
# requires the ARM (linux/arm64) Docker image variant.
variable "instance_type" {
  description = "EC2 instance type for the chatbot host."
  type        = string
  default     = "t3.small"
}
