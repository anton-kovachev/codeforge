#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT=${1:-development}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
TERRAFORM_ROOT="$PROJECT_ROOT/terraform"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
AWS_REGION=${AWS_REGION:-${DEFAULT_AWS_REGION:-eu-north-1}}
export AWS_REGION
CLERK_PUBLISHABLE_KEY=${CLERK_PUBLISHABLE_KEY:-${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-${VITE_CLERK_PUBLISHABLE_KEY:-}}}

if [[ -z "${TF_VAR_aws_bearer_token_bedrock:-${AWS_BEARER_TOKEN_BEDROCK:-}}" ]]; then
  echo "Set TF_VAR_aws_bearer_token_bedrock or AWS_BEARER_TOKEN_BEDROCK before deploying." >&2
  exit 1
fi
if [[ -z "${TF_VAR_clerk_jwks_url:-${CLERK_JWKS_URL:-}}" ]]; then
  echo "Set TF_VAR_clerk_jwks_url or CLERK_JWKS_URL before deploying." >&2
  exit 1
fi
if [[ -z "$CLERK_PUBLISHABLE_KEY" ]]; then
  echo "Set CLERK_PUBLISHABLE_KEY before deploying the frontend." >&2
  exit 1
fi

export TF_VAR_aws_bearer_token_bedrock=${TF_VAR_aws_bearer_token_bedrock:-${AWS_BEARER_TOKEN_BEDROCK:-}}
export TF_VAR_clerk_jwks_url=${TF_VAR_clerk_jwks_url:-${CLERK_JWKS_URL:-}}

prepare_phase() {
  local phase_dir=$1
  cd "$phase_dir"
  terraform init -input=false || return

  if ! terraform workspace select "$ENVIRONMENT" >/dev/null 2>&1; then
    terraform workspace new "$ENVIRONMENT" >/dev/null
  fi

  local vars_file="terraform.${ENVIRONMENT}.tfvars"
  if [[ -f "$vars_file" ]]; then
    PHASE_VAR_FILE=(-var-file="$vars_file")
  else
    PHASE_VAR_FILE=()
  fi
}

apply_phase() {
  local phase_dir=$1
  shift
  prepare_phase "$phase_dir"
  terraform apply -input=false -auto-approve \
    "${PHASE_VAR_FILE[@]}" \
    -var="environment=$ENVIRONMENT" \
    -var="aws_region=$AWS_REGION" \
    "$@"
}

echo "Deploying AgentCore runtime ($ENVIRONMENT)..."
apply_phase "$TERRAFORM_ROOT/agent"
AGENT_RUNTIME_ARN=$(terraform output -raw bedrock_agentcore_runtime_arn)
AGENT_RUNTIME_ENDPOINT_ARN=$(terraform output -raw bedrock_agentcore_runtime_endpoint_arn)
AGENT_ENDPOINT_NAME=$(terraform output -raw bedrock_agentcore_runtime_endpoint_name)

echo "Deploying API Lambda ($ENVIRONMENT)..."
apply_phase "$TERRAFORM_ROOT/api" \
  -var="agent_runtime_arn=$AGENT_RUNTIME_ARN" \
  -var="agent_runtime_endpoint_arn=$AGENT_RUNTIME_ENDPOINT_ARN" \
  -var="agent_endpoint_name=$AGENT_ENDPOINT_NAME"
API_FUNCTION_URL=$(terraform output -raw api_function_url)

echo "Provisioning frontend hosting ($ENVIRONMENT)..."
apply_phase "$TERRAFORM_ROOT/frontend"
FRONTEND_BUCKET=$(terraform output -raw frontend_bucket_name)
FRONTEND_URL=$(terraform output -raw frontend_website_url)

echo "Building frontend for API $API_FUNCTION_URL..."
pnpm --dir "$FRONTEND_DIR" install --frozen-lockfile
NEXT_PUBLIC_CODEFORGE_API_BASE_URL="$API_FUNCTION_URL" \
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="$CLERK_PUBLISHABLE_KEY" \
  pnpm --dir "$FRONTEND_DIR" run build

echo "Uploading frontend to s3://$FRONTEND_BUCKET..."
aws s3 sync "$FRONTEND_DIR/out/" "s3://$FRONTEND_BUCKET/" --region "$AWS_REGION" --delete
echo "Frontend URL: $FRONTEND_URL"

echo "Deployment complete."
echo "API URL:      $API_FUNCTION_URL"
