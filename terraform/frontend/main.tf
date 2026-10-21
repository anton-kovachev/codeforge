data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }


  # Rebuild and redeploy whenever any frontend source changes (.env, build output and deps excluded).
  src_files = [for f in fileset(var.app_dir, "**") : f
    if !startswith(f, "node_modules/") && !startswith(f, "dist/") && !startswith(f, ".git/") && f != ".env" && !startswith(f, ".env.")
  ]
  src_hash = sha256(join("", concat(
    [for f in sort(local.src_files) : filesha256("${var.app_dir}/${f}")],
    [for k in sort(keys(var.build_env)) : "${k}=${var.build_env[k]}"]
  )))
}

resource "aws_s3_bucket" "frontend" {
  bucket        = "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
  tags          = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  # SPA: unknown paths fall back to the app so client-side routing works.
  error_document {
    key = "index.html"
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

resource "null_resource" "build_frontend" {
  triggers = {
    src_hash = local.src_hash
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    working_dir = "${path.module}/${var.app_dir}"
    command     = "pnpm install --frozen-lockfile && pnpm build"
    environment = var.build_env
  }
}

resource "null_resource" "deploy_frontend" {
  triggers = {
    src_hash = local.src_hash
    bucket   = aws_s3_bucket.frontend.id
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    working_dir = "${path.module}/${var.app_dir}"
    command     = <<-EOT
      set -euo pipefail
      # Hashed assets are immutable; index.html must always be revalidated.
      aws s3 sync dist s3://${aws_s3_bucket.frontend.id} --region ${var.aws_region} --delete \
        --exclude "index.html" --cache-control "public,max-age=31536000,immutable"
      aws s3 cp dist/index.html s3://${aws_s3_bucket.frontend.id}/index.html --region ${var.aws_region} \
        --cache-control "no-cache" --content-type "text/html; charset=utf-8"
    EOT
  }

  depends_on = [null_resource.build_frontend, aws_s3_bucket_policy.frontend, aws_s3_bucket_website_configuration.frontend]
}
