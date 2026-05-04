module "network" {
  source = "../../modules/network"

  project_name = var.project_name
}

module "iam" {
  source = "../../modules/iam"

  project_name = var.project_name
}

module "storage" {
  source = "../../modules/storage"

  project_name  = var.project_name
  bucket_suffix = var.bucket_suffix
}

module "ecr" {
  source = "../../modules/ecr"

  project_name = var.project_name
}

# Coming in later steps:
#   module "compute" { ... }   # EC2 + EBS + security group + user_data
#   module "cdn"     { ... }   # CloudFront in front of S3 + OAC bucket policy
