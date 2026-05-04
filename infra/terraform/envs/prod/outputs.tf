output "vpc_id" {
  description = "VPC the prod env runs in."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs across AZs."
  value       = module.network.public_subnet_ids
}
