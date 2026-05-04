data "aws_region" "current" {}

# Latest Amazon Linux 2023 x86_64 AMI. AWS publishes a known-name pattern,
# we resolve it dynamically so the AMI ID stays current as patches ship.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Inbound 80/443 from anywhere; locked down to CloudFront in step 6."
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.project_name}-ec2-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.ec2.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP from anywhere. Narrow to CloudFront prefix list later."
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.ec2.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS. Defensive open, in case we serve TLS directly later."
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.ec2.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound. Needed for ECR, SSM, Anthropic API."
}

# SecureString param for the Anthropic API key. Created with a placeholder;
# set the real value via:
#   aws ssm put-parameter --name /astrobot/anthropic_api_key \
#     --value "sk-ant-..." --type SecureString --overwrite
resource "aws_ssm_parameter" "anthropic_api_key" {
  name        = "/${var.project_name}/anthropic_api_key"
  type        = "SecureString"
  value       = "REPLACE_ME"
  description = "Anthropic API key — set the real value out-of-band via aws ssm put-parameter."

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_instance" "bot" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = var.instance_profile_name

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region          = data.aws_region.current.name
    ecr_url         = var.ecr_repository_url
    ssm_param_name  = aws_ssm_parameter.anthropic_api_key.name
  })

  # Re-run user_data if the script content changes. Without this, edits to
  # the bootstrap script are silently ignored on existing instances.
  user_data_replace_on_change = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gb
    encrypted             = true
    delete_on_termination = true
  }

  metadata_options {
    http_tokens   = "required" # IMDSv2 only — IMDSv1 is the SSRF footgun
    http_endpoint = "enabled"
  }

  tags = {
    Name = "${var.project_name}-bot"
  }
}

resource "aws_eip" "bot" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-bot-eip"
  }
}

resource "aws_eip_association" "bot" {
  instance_id   = aws_instance.bot.id
  allocation_id = aws_eip.bot.id
}
