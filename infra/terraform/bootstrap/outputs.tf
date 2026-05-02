output "state_bucket" {
  description = "Name of the S3 bucket holding remote Terraform state. Plug into envs/prod/backend.tf."
  value       = aws_s3_bucket.tf_state.id
}

output "lock_table" {
  description = "Name of the DynamoDB table used for state locking. Plug into envs/prod/backend.tf."
  value       = aws_dynamodb_table.tf_lock.name
}

output "region" {
  description = "Region the bucket and table live in."
  value       = var.region
}
