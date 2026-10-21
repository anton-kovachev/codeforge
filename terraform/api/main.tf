data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
  registry    = "${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Rebuild and redeploy whenever any application source changes (.env is never baked in).
  app_files = [for f in fileset(var.app_dir, "**") : f
    if !startswith(f, ".venv/") && !startswith(f, "__pycache__/") && !endswith(f, ".pyc") && f != ".env" && !startswith(f, ".git/")
  ]
  app_hash  = substr(sha256(join("", [for f in sort(local.app_files) : filesha256("${var.app_dir}/${f}")])), 0, 16)
  image_uri = "${aws_ecr_repository.api.repository_url}:${local.app_hash}"
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-repository"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = local.common_tags
}

resource "null_resource" "build_and_push_app_image" {
  triggers = {
    app_hash = local.app_hash
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    working_dir = path.module
    command     = <<-EOT
      set -euo pipefail
      docker build -t ${aws_ecr_repository.api.name}:${local.app_hash} ${var.app_dir} --platform linux/arm64 --provenance false
      aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${local.registry}
      docker tag ${aws_ecr_repository.api.name}:${local.app_hash} ${local.image_uri}
      docker push ${local.image_uri}
    EOT
  }

  depends_on = [aws_ecr_repository.api]
}

resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "invoke_agentcore_runtime" {
  name        = "${local.name_prefix}-invoke-agentcore-runtime-policy"
  description = "Allow invoking the Bedrock AgentCore runtime and its endpoints"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "InvokeAgentCoreRuntime"
      Effect = "Allow"
      Action = [
        "bedrock-agentcore:InvokeAgentRuntime",
        "bedrock-agentcore:InvokeAgentRuntimeForUser"
      ]
      Resource = [
        var.agent_runtime_arn,
        var.agent_runtime_endpoint_arn
      ]
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "invoke_agentcore_runtime" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.invoke_agentcore_runtime.arn
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}-function"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-function"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = local.image_uri
  architectures = ["arm64"]
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout

  # AWS_REGION is reserved and injected by Lambda automatically.
  environment {
    variables = {
      AGENT_RUNTIME_ARN            = var.agent_runtime_arn
      AGENT_ENDPOINT_NAME          = var.agent_endpoint_name
      CORS_ORIGINS                 = var.cors_origins
      CLERK_JWKS_URL               = var.clerk_jwks_url
      AWS_LWA_INVOKE_MODE          = "response_stream"
      AWS_LWA_PORT                 = "8000"
      AWS_LWA_READINESS_CHECK_PATH = "/api/health"
    }
  }

  tags       = local.common_tags
  depends_on = [null_resource.build_and_push_app_image, aws_cloudwatch_log_group.lambda, aws_iam_role_policy_attachment.lambda_basic_execution]
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"
}

resource "aws_lambda_permission" "function_url_public" {
  statement_id           = "AllowPublicFunctionUrlInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "function_url_public_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.api.function_name
  principal                = "*"
  invoked_via_function_url = true
}
