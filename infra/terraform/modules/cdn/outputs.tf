output "distribution_id" {
  description = "Use with: aws cloudfront create-invalidation --distribution-id <this> --paths '/*'"
  value       = aws_cloudfront_distribution.main.id
}

output "distribution_domain_name" {
  description = "The xxxx.cloudfront.net hostname. Public URL of the site."
  value       = aws_cloudfront_distribution.main.domain_name
}

output "distribution_arn" {
  description = "ARN of the distribution. Useful when adding ACM certs or WAF later."
  value       = aws_cloudfront_distribution.main.arn
}
