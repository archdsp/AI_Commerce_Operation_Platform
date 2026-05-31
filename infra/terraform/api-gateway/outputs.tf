output "invoke_url" {
  description = "REST API 호출 base URL (스테이지 포함)"
  value       = aws_api_gateway_stage.acop.invoke_url
}

output "rest_api_id" {
  value = aws_api_gateway_rest_api.acop.id
}

output "example_curl" {
  description = "스모크 테스트 예시 (KEY는 api_keys 중 하나)"
  value       = "curl -H 'X-API-Key: <KEY>' -H 'Content-Type: application/json' -d '{\"query\":\"카테고리별 매출 상위 5개\"}' ${aws_api_gateway_stage.acop.invoke_url}/v1/chat"
}
