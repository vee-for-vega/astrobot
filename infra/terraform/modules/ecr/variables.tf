variable "project_name" {
  description = "Used as the ECR repository name."
  type        = string
}

variable "max_image_count" {
  description = "How many tagged images to keep before lifecycle policy expires older ones."
  type        = number
  default     = 10
}
