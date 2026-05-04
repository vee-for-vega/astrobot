output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs, one per AZ. Order matches public_subnet_cidrs."
  value       = aws_subnet.public[*].id
}

output "vpc_cidr" {
  description = "CIDR of the VPC. Useful for security group rules that allow VPC-internal traffic."
  value       = aws_vpc.this.cidr_block
}
