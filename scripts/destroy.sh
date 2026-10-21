#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT=${1:-development}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
TERRAFORM_ROOT="$PROJECT_ROOT/terraform"
AWS_REGION=${AWS_REGION:-${DEFAULT_AWS_REGION:-eu-north-1}}
export AWS_REGION

if [[ -z "${TF_VAR_aws_bearer_token_bedrock:-${AWS_BEARER_TOKEN_BEDROCK:-}}" ]]; then
  echo "Set TF_VAR_aws_bearer_token_bedrock or AWS_BEARER_TOKEN_BEDROCK before destroying." >&2
  exit 1
fi
if [[ -z "${TF_VAR_clerk_jwks_url:-${CLERK_JWKS_URL:-}}" ]]; then
  echo "Set TF_VAR_clerk_jwks_url or CLERK_JWKS_URL before destroying." >&2
  exit 1
fi

export TF_VAR_aws_bearer_token_bedrock=${TF_VAR_aws_bearer_token_bedrock:-${AWS_BEARER_TOKEN_BEDROCK:-}}
export TF_VAR_clerk_jwks_url=${TF_VAR_clerk_jwks_url:-${CLERK_JWKS_URL:-}}

prepare_phase() {
  local phase_dir=$1
  cd "$phase_dir"
  terraform init -input=false || return

  if ! terraform workspace select "$ENVIRONMENT" >/dev/null 2>&1; then
    echo "Terraform workspace '$ENVIRONMENT' does not exist in $phase_dir; skipping." >&2
    return 2
  fi

  local vars_file="terraform.${ENVIRONMENT}.tfvars"
  if [[ -f "$vars_file" ]]; then
    PHASE_VAR_FILE=(-var-file="$vars_file")
  else
    PHASE_VAR_FILE=()
  fi
}

destroy_phase() {
  local phase_dir=$1
  local prepare_status
  shift
  if prepare_phase "$phase_dir"; then
    :
  else
    prepare_status=$?
    if [[ "$prepare_status" -eq 2 ]]; then
      return 0
    fi
    return "$prepare_status"
  fi

  terraform destroy -input=false -auto-approve \
    "${PHASE_VAR_FILE[@]}" \
    -var="environment=$ENVIRONMENT" \
    -var="aws_region=$AWS_REGION" \
    "$@"
}

echo "Destroying frontend ($ENVIRONMENT)..."
destroy_phase "$TERRAFORM_ROOT/frontend"

echo "Destroying API Lambda ($ENVIRONMENT)..."
if prepare_phase "$TERRAFORM_ROOT/agent"; then
  AGENT_RUNTIME_ARN=$(terraform output -raw bedrock_agentcore_runtime_arn)
  AGENT_RUNTIME_ENDPOINT_ARN=$(terraform output -raw bedrock_agentcore_runtime_endpoint_arn)
  AGENT_ENDPOINT_NAME=$(terraform output -raw bedrock_agentcore_runtime_endpoint_name)
  destroy_phase "$TERRAFORM_ROOT/api" \
    -var="agent_runtime_arn=$AGENT_RUNTIME_ARN" \
    -var="agent_runtime_endpoint_arn=$AGENT_RUNTIME_ENDPOINT_ARN" \
    -var="agent_endpoint_name=$AGENT_ENDPOINT_NAME"
else
  PREPARE_STATUS=$?
  if [[ "$PREPARE_STATUS" -eq 2 ]]; then
    echo "AgentCore workspace is missing; API phase will be skipped." >&2
  else
    exit "$PREPARE_STATUS"
  fi
fi

echo "Destroying AgentCore runtime ($ENVIRONMENT)..."
destroy_phase "$TERRAFORM_ROOT/agent"

echo "Destroy complete."
