output "s3_bucket_name" {
  value = aws_s3_bucket.models.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "api_gateway_url" {
  value = aws_apigatewayv2_api.main.api_endpoint
}

output "vpc_id" {
  value = aws_vpc.main.id
}
