variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "eu-north-1"
}

variable "environment" {
  description = "The environment to deploy resources in"
  type        = string
  default     = "development"
}

variable "project_name" {
  description = "The name of the project"
  type        = string
  default     = "codeforge-api"
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "app_dir" {
  description = "The directory of the API application (contains the Dockerfile)"
  type        = string
  default     = "../../api"
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 1024
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds (max 900)"
  type        = number
  default     = 900
}

variable "agent_runtime_arn" {
  description = "ARN of the Bedrock AgentCore runtime (AGENT_RUNTIME_ARN)"
  type        = string
}

variable "agent_runtime_endpoint_arn" {
  description = "ARN of the Bedrock AgentCore runtime endpoint"
  type        = string
}

variable "agent_endpoint_name" {
  description = "Name of the Bedrock AgentCore runtime endpoint (AGENT_ENDPOINT_NAME)"
  type        = string
  default     = "DEFAULT"
}

variable "cors_origins" {
  description = "Comma separated list of allowed CORS origins (CORS_ORIGINS)"
  type        = string
  default     = "http://localhost:3000"
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL used to validate JWTs (CLERK_JWKS_URL)"
  type        = string
}
