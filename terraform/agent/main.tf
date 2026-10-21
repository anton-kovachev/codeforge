data "aws_caller_identity" "current" {}

locals {
  name_prefix                   = "${var.project_name}-${var.environment}"
  agentcore_runtime_name_prefix = "codeforge_agent_${var.environment}_runtime"
  account_id                    = data.aws_caller_identity.current.account_id

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  app_hash = filebase64sha256("${var.app_dir}/Dockerfile")
}

resource "aws_iam_role" "bedrock_agentcore_runtime_role" {
  name = "${local.name_prefix}-bedrock-agentcore-runtime-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
      }
    ]
  })
  tags = local.common_tags
}


resource "aws_iam_policy" "bedrock_agentcore_runtime_role_policy" {
  name        = "${local.name_prefix}-bedrock-agentcore-runtime-policy"
  path        = "/"
  description = "Bedrock AgentCore runtime policy"

  # Terraform's "jsonencode" function converts a
  # Terraform expression result to valid JSON syntax.
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "VisualEditor0",
        "Effect" : "Allow",
        "Action" : [
          "bedrock-agentcore:GetResourceApiKey",
          "logs:DescribeLogStreams",
          "bedrock:InvokeModel",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "bedrock:InvokeModelWithResponseStream",
          "logs:CreateLogGroup"
        ],
        "Resource" : [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:${var.aws_region}:${local.account_id}:*",
          "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:token-vault/default/apikeycredentialprovider/*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default/workload-identity/first-*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:token-vault/default",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default",
          "arn:aws:ecr:${var.aws_region}:${local.account_id}:repository/*"
        ]
      },
      {
        "Sid" : "VisualEditor1",
        "Effect" : "Allow",
        "Action" : [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT"
        ],
        "Resource" : [
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default/workload-identity/first-*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default"
        ]
      },
      {
        "Sid" : "VisualEditor2",
        "Effect" : "Allow",
        "Action" : "bedrock-agentcore:InvokeAgentRuntime",
        "Resource" : "arn:aws:bedrock-agentcore:eu-north-1:456097556049:runtime/*"
      },
      {
        "Sid" : "VisualEditor3",
        "Effect" : "Allow",
        "Action" : [
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:GetMemory",
          "bedrock-agentcore:RetrieveMemoryRecords",
          "bedrock-agentcore:ListActors",
          "bedrock-agentcore:ListSessions",
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:DeleteEvent",
          "bedrock-agentcore:ListEvents",
          "bedrock-agentcore:DeleteMemoryRecord",
          "bedrock-agentcore:ListMemoryRecords"
        ],
        "Resource" : "arn:aws:bedrock-agentcore:eu-north-1:456097556049:memory/*"
      },
      {
        "Sid" : "VisualEditor4",
        "Effect" : "Allow",
        "Action" : "cloudwatch:PutMetricData",
        "Resource" : "*",
        "Condition" : {
          "StringEquals" : {
            "cloudwatch:namespace" : "bedrock-agentcore"
          }
        }
      },
      {
        "Sid" : "VisualEditor5",
        "Effect" : "Allow",
        "Action" : [
          "bedrock-mantle:GetAccountDataRetention",
          "bedrock-mantle:PutAccountDataRetention",
          "xray:PutTelemetryRecords",
          "bedrock-agentcore:CreateMemory",
          "bedrock-mantle:*",
          "bedrock-mantle:CallWithBearerToken",
          "xray:GetSamplingRules",
          "ecr:GetAuthorizationToken",
          "xray:GetSamplingTargets",
          "xray:PutTraceSegments"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "VisualEditor6",
        "Effect" : "Allow",
        "Action" : [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "bedrock-agentcore:GetResourceOauth2Token"
        ],
        "Resource" : [
          "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:token-vault/default/oauth2credentialprovider/*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default/workload-identity/first-*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:token-vault/default",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default"
        ]
      },
      {
        "Sid" : "VisualEditor7",
        "Effect" : "Allow",
        "Action" : "bedrock-mantle:*",
        "Resource" : "arn:aws:bedrock-mantle:${var.aws_region}:${local.account_id}:project/default"
      },
      {
        "Sid" : "VisualEditor8",
        "Effect" : "Allow",
        "Action" : "logs:DescribeLogGroups",
        "Resource" : "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:*"
      }
  ] })

  tags = local.common_tags
}

resource "aws_iam_policy" "bedrock_agentcore_runtime_role_xray_policy" {
  name = "${local.name_prefix}-agentcore-runtime-xray-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_agentcore_runtime_role_attachment" {
  role       = aws_iam_role.bedrock_agentcore_runtime_role.name
  policy_arn = aws_iam_policy.bedrock_agentcore_runtime_role_policy.arn
}

resource "aws_iam_role_policy_attachment" "bedrock_agentcore_runtime_role_xray_attachment" {
  role       = aws_iam_role.bedrock_agentcore_runtime_role.name
  policy_arn = aws_iam_policy.bedrock_agentcore_runtime_role_xray_policy.arn
}

resource "aws_ecr_repository" "bedrock_agentcore_repository" {
  name                 = "${local.name_prefix}-repository"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = local.common_tags
}

resource "null_resource" "build_and_push_app_image" {
  triggers = {
    dockerfile_hash = local.app_hash
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    working_dir = path.module
    command     = <<-EOT
        source set -a && .${path.module}${var.app_dir}/.env && set +a
        docker build -t ${resource.aws_ecr_repository.bedrock_agentcore_repository.name}:latest ${var.app_dir} --platform linux/arm64 --provenance false --build-arg AWS_REGION=${var.aws_region}  
        aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com
        docker tag ${resource.aws_ecr_repository.bedrock_agentcore_repository.name}:latest ${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${resource.aws_ecr_repository.bedrock_agentcore_repository.name}:latest
        docker push ${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${resource.aws_ecr_repository.bedrock_agentcore_repository.name}:latest
        EOT
  }

  depends_on = [aws_ecr_repository.bedrock_agentcore_repository]
}

resource "aws_bedrockagentcore_agent_runtime" "bedrock_agentcore_runtime" {
  agent_runtime_name = local.agentcore_runtime_name_prefix
  role_arn           = aws_iam_role.bedrock_agentcore_runtime_role.arn

  agent_runtime_artifact {
    container_configuration {
      #   container_uri = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.name_prefix}-${resource.aws_ecr_repository.bedrock_agentcore_repository.name}:latest"
      container_uri = "${aws_ecr_repository.bedrock_agentcore_repository.repository_url}:latest"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  lifecycle_configuration {
    idle_runtime_session_timeout = 900
    max_lifetime                 = 28800
  }

  environment_variables = {
    AWS_BEARER_TOKEN_BEDROCK = var.aws_bearer_token_bedrock
  }

  tags       = local.common_tags
  depends_on = [aws_ecr_repository.bedrock_agentcore_repository, null_resource.build_and_push_app_image]
}

resource "aws_bedrockagentcore_agent_runtime_endpoint" "bedrock_agentcore_runtime_endpoint" {
  name             = "${local.agentcore_runtime_name_prefix}_endpoint"
  agent_runtime_id = aws_bedrockagentcore_agent_runtime.bedrock_agentcore_runtime.agent_runtime_id
  description      = "Endpoint for agent runtime communication"


  tags       = local.common_tags
  depends_on = [aws_bedrockagentcore_agent_runtime.bedrock_agentcore_runtime]
}
