output "vpc_id" {
  description = "VPC the prod env runs in."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs across AZs."
  value       = module.network.public_subnet_ids
}

output "site_bucket" {
  description = "S3 bucket holding the static frontend. Use with `aws s3 sync ./web s3://<this>/`."
  value       = module.storage.bucket_id
}

output "ecr_repository_url" {
  description = "Tag and push the bot image as <this>:<tag>."
  value       = module.ecr.repository_url
}
