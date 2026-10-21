output "frontend_bucket_name" {
  value       = aws_s3_bucket.frontend.id
  description = "Name of the S3 bucket hosting the frontend"
}

output "frontend_website_url" {
  value       = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
  description = "S3 static website URL of the frontend"
}
