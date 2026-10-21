output "api_function_url" {
  value       = aws_lambda_function_url.api.function_url
  description = "Public streaming Function URL of the API lambda"
}

output "api_lambda_function_name" {
  value       = aws_lambda_function.api.function_name
  description = "Name of the API lambda"
}

output "api_lambda_role_arn" {
  value       = aws_iam_role.lambda.arn
  description = "ARN of the API lambda execution role"
}

output "api_ecr_repository_url" {
  value       = aws_ecr_repository.api.repository_url
  description = "ECR repository URL holding the API image"
}
