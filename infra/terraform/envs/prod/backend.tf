terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "astrobot-tf-state-7061"
    key          = "envs/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true # S3-native locking (Terraform 1.10+); replaces the DynamoDB table pattern.
  }
}
