variable "project_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  description = "Public subnet to launch the EC2 in."
  type        = string
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "instance_profile_name" {
  description = "From the iam module."
  type        = string
}

variable "ecr_repository_url" {
  description = "From the ecr module. Used by user_data to pull the image."
  type        = string
}

variable "root_volume_size_gb" {
  type    = number
  default = 30
}
