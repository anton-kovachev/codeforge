variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "eu-north-1"
}

variable "aws_region_alias" {
  description = "The alias for the AWS region to deploy resources in"
  type        = string
  default     = "eu_north_1"
}

variable "environment" {
  description = "The environment to deploy resources in"
  type        = string
  default     = "development"
}

variable "project_name" {
  description = "The name of the project"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
  default = "codeforge-agent"
}

variable "app_dir" {
  description = "The directory of the application"
  type        = string
  default     = "../../agent"
}

variable "aws_bearer_token_bedrock" {
  description = "The AWS bearer token for Bedrock"
  type        = string
}
