output "repository_url" {
  description = "Full image URL prefix. Tag images as <this>:<tag> and docker push."
  value       = aws_ecr_repository.bot.repository_url
}

output "repository_arn" {
  description = "ARN of the repo. Useful if we need to grant cross-account or fine-grained pull access."
  value       = aws_ecr_repository.bot.arn
}
