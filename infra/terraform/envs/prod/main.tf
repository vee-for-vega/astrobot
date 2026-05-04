module "network" {
  source = "../../modules/network"

  project_name = var.project_name
}

# Coming in later steps:
#   module "iam"     { ... }   # EC2 instance role + SSM access
#   module "storage" { ... }   # S3 static-site bucket
#   module "compute" { ... }   # EC2 + EBS + security group + user_data
#   module "cdn"     { ... }   # CloudFront in front of S3
