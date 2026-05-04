variable "project_name" {
  description = "Used as a Name-tag prefix on every resource."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDRs for the public subnets, one per AZ. Length must match az_count."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "az_count" {
  description = "How many AZs to spread subnets across."
  type        = number
  default     = 2
}
