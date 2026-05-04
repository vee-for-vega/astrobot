module "network" {
  source = "../../modules/network"

  project_name = var.project_name
}

module "iam" {
  source = "../../modules/iam"

  project_name = var.project_name
}

module "storage" {
  source = "../../modules/storage"

  project_name  = var.project_name
  bucket_suffix = var.bucket_suffix
}

module "ecr" {
  source = "../../modules/ecr"

  project_name = var.project_name
}

module "compute" {
  source = "../../modules/compute"

  project_name          = var.project_name
  vpc_id                = module.network.vpc_id
  subnet_id             = module.network.public_subnet_ids[0]
  instance_type         = var.instance_type
  instance_profile_name = module.iam.instance_profile_name
  ecr_repository_url    = module.ecr.repository_url
}

# Runtime IAM glue: lets the EC2 role pull from ECR and read the API key
# from SSM. Lives at env level because it spans iam + ecr + compute modules.
data "aws_iam_policy_document" "ec2_runtime" {
  statement {
    sid       = "EcrAuthToken"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [module.ecr.repository_arn]
  }

  statement {
    sid       = "SsmReadApiKey"
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = [module.compute.api_key_parameter_arn]
  }
}

resource "aws_iam_policy" "ec2_runtime" {
  name        = "${var.project_name}-ec2-runtime"
  description = "Runtime perms for the bot EC2 — ECR pull + read the API key from SSM."
  policy      = data.aws_iam_policy_document.ec2_runtime.json
}

resource "aws_iam_role_policy_attachment" "ec2_runtime" {
  role       = module.iam.role_name
  policy_arn = aws_iam_policy.ec2_runtime.arn
}

# Coming next:
#   module "cdn" { ... }   # CloudFront in front of S3 + OAC bucket policy
