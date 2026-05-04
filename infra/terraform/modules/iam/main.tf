# Trust policy: defines who can assume this role.
# EC2 service principal — any EC2 that's launched with this role
# attached can take on its permissions.
data "aws_iam_policy_document" "ec2_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.project_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
  description        = "Role assumed by the chatbot EC2 instance. Grants SSM and CloudWatch access."
}

# AWS-managed policy: lets the instance register with Session Manager
# to shell in via 'aws ssm start-session' instead of SSH.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# AWS-managed policy: lets the CloudWatch Agent on the instance ship logs
# and metrics to CloudWatch.
resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# Instance profiles are the wrapper AWS uses to pass a role to an EC2.
resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}
