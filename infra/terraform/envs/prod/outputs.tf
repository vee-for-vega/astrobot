output "region" {
  description = "AWS region for this env. Used by deploy scripts."
  value       = var.region
}

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

output "bot_public_ip" {
  description = "Stable Elastic IP of the bot EC2."
  value       = module.compute.public_ip
}

output "bot_instance_id" {
  description = "Use with: aws ssm start-session --target <this>"
  value       = module.compute.instance_id
}

output "api_key_parameter_name" {
  description = "Set the real API key with: aws ssm put-parameter --name <this> --value sk-ant-... --type SecureString --overwrite"
  value       = module.compute.api_key_parameter_name
}

output "site_url" {
  description = "Public URL of the site. CloudFront *.cloudfront.net hostname over HTTPS."
  value       = "https://${module.cdn.distribution_domain_name}"
}

output "cloudfront_distribution_id" {
  description = "Use with: aws cloudfront create-invalidation --distribution-id <this> --paths '/*'"
  value       = module.cdn.distribution_id
}
