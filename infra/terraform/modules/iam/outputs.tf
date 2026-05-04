output "instance_profile_name" {
  description = "Name of the EC2 instance profile. The compute module attaches this to the EC2."
  value       = aws_iam_instance_profile.ec2.name
}

output "role_arn" {
  description = "ARN of the EC2 role. Useful for cross-referencing in IAM trust policies elsewhere."
  value       = aws_iam_role.ec2.arn
}
