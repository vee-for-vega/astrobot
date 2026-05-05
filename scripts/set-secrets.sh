#!/usr/bin/env bash
# Set the three SecureString SSM params: Anthropic API key, demo password,
# JWT signing key. Run once after `terraform apply`, and any time you rotate.
set -euo pipefail

cd "$(dirname "$0")/../infra/terraform/envs/prod"

API_KEY_PARAM=$(terraform output -raw api_key_parameter_name)
PW_PARAM=$(terraform output -raw auth_password_parameter_name)
JWT_PARAM=$(terraform output -raw jwt_signing_key_parameter_name)

read -rsp "Anthropic API key (sk-ant-...): " ANTHROPIC_KEY; echo
read -rsp "Demo password (will appear on resume): " DEMO_PW; echo

# Generate a random JWT signing key — 48 bytes base64. No human ever needs to type this.
JWT_KEY=$(openssl rand -base64 48 | tr -d '\n')

aws ssm put-parameter --name "$API_KEY_PARAM" --value "$ANTHROPIC_KEY" --type SecureString --overwrite >/dev/null
aws ssm put-parameter --name "$PW_PARAM"     --value "$DEMO_PW"        --type SecureString --overwrite >/dev/null
aws ssm put-parameter --name "$JWT_PARAM"    --value "$JWT_KEY"        --type SecureString --overwrite >/dev/null

echo "✓ all three params set."
echo "→ next: ./scripts/deploy-image.sh to build + push the bot image"
