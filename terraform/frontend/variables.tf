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
  default     = "codeforge-frontend"
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "app_dir" {
  description = "The directory of the React (Vite) frontend application"
  type        = string
  default     = "../../debugforge-frontend"
}

variable "build_env" {
  description = "Environment variables (e.g. VITE_API_URL) exposed to the frontend build"
  type        = map(string)
  default     = {}
}
