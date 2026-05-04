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

# Coming in later steps:
#   module "ecr"     { ... }   # Docker registry for the bot image
#   module "compute" { ... }   # EC2 + EBS + security group + user_data
#   module "cdn"     { ... }   # CloudFront in front of S3 + OAC bucket policy
