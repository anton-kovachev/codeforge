output "bedrock_agentcore_runtime_id" {
  value       = aws_bedrockagentcore_agent_runtime.bedrock_agentcore_runtime.agent_runtime_id
  description = "The ID of the Bedrock Agentcore runtime"
}

output "bedrock_agentcore_runtime_arn" {
  value       = aws_bedrockagentcore_agent_runtime.bedrock_agentcore_runtime.agent_runtime_arn
  description = "The ARN of the Bedrock Agentcore runtime"
}

output "bedrock_agentcore_runtime_endpoint_arn" {
  value       = aws_bedrockagentcore_agent_runtime_endpoint.bedrock_agentcore_runtime_endpoint.agent_runtime_endpoint_arn
  description = "The ARN of the Bedrock Agentcore runtime endpoint"
}

output "bedrock_agentcore_runtime_endpoint_name" {
  value       = aws_bedrockagentcore_agent_runtime_endpoint.bedrock_agentcore_runtime_endpoint.name
  description = "The name of the Bedrock Agentcore runtime endpoint"
}
