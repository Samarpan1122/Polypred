variable "project_name" {
  default = "polypred"
}

variable "aws_region" {
  default = "us-east-1"
}

variable "environment" {
  default = "production"
}

variable "backend_image_tag" {
  default = "latest"
}

variable "backend_cpu" {
  default = 1024
  description = "Fargate CPU units (1024 = 1 vCPU)"
}

variable "backend_memory" {
  default = 4096
  description = "Fargate memory (MB) - needs room for PyTorch + RDKit"
}

variable "frontend_domain" {
  default = ""
  description = "Custom domain for CloudFront (leave empty for default)"
}
