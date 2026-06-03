output "public_ip" {
  description = "Stable Elastic IP of the bot instance."
  value       = aws_eip.bot.public_ip
}

output "public_dns" {
  description = "Auto-assigned EC2 DNS name."
  value       = aws_instance.bot.public_dns
}

output "eip_public_dns" {
  description = "Public DNS for the Elastic IP. Stable across instance restarts. Used as a CloudFront custom origin."
  value       = aws_eip.bot.public_dns
}

output "instance_id" {
  description = "Useful for `aws ssm start-session --target <id>`."
  value       = aws_instance.bot.id
}

output "api_key_parameter_arn" {
  description = "ARN of the SSM SecureString param. Used to scope the role's ssm:GetParameter policy."
  value       = aws_ssm_parameter.anthropic_api_key.arn
}

output "api_key_parameter_name" {
  description = "Name of the SSM param. Use with `aws ssm put-parameter --name <this>`."
  value       = aws_ssm_parameter.anthropic_api_key.name
}

output "secret_parameter_arns" {
  description = "All SecureString param ARNs the EC2 role needs read access to."
  value = [
    aws_ssm_parameter.anthropic_api_key.arn,
  ]
}
