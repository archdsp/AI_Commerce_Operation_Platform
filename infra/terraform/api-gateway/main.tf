###############################################################################
# AI Commerce Ops — AWS API Gateway (REST) IaC
#
#   Client ──X-API-Key──▶ [REST API]  ──X-Origin-Secret 주입──▶ [FastAPI / EC2:8000]
#                          · API Key + Usage Plan(throttle/quota)
#                          · {proxy+} HTTP_PROXY 통합
#
# REST API를 쓰는 이유: HTTP API엔 없는 "API Key + Usage Plan(키별 rate limit/quota)"과
# 통합 타임아웃 상향(>29s, 쿼터 증설) 때문 — LLM 에이전트(vLLM 2~3회+교차리전 RDS) 특성에 부합.
# 측정 지연: /v1/chat 성공 ~7~16s, self-correction 시 더 높음.
###############################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

locals {
  # use_vpc_link=true → 내부 NLB DNS:listener_port / false → 공개 EC2 host:port
  backend_base       = var.use_vpc_link ? "http://${join("", aws_lb.nlb[*].dns_name)}:${var.nlb_listener_port}" : "http://${var.backend_host}:${var.backend_port}"
  backend_uri_proxy  = "${local.backend_base}/{proxy}"
  backend_uri_health = "${local.backend_base}/health"
}

resource "aws_api_gateway_rest_api" "acop" {
  name        = "${var.name_prefix}-rest"
  description = "AI Commerce Ops — FastAPI 게이트웨이 앞단 (인증/throttle/quota 관리형)"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# ── /health : 인증 없이 개방 (LB/모니터 헬스체크). FastAPI도 /health는 시크릿 미적용 ──
resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.acop.id
  parent_id   = aws_api_gateway_rest_api.acop.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_method" "health_get" {
  rest_api_id      = aws_api_gateway_rest_api.acop.id
  resource_id      = aws_api_gateway_resource.health.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = false
}

resource "aws_api_gateway_integration" "health_get" {
  rest_api_id             = aws_api_gateway_rest_api.acop.id
  resource_id             = aws_api_gateway_resource.health.id
  http_method             = aws_api_gateway_method.health_get.http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "GET"
  uri                     = local.backend_uri_health
  timeout_milliseconds    = 29000

  connection_type = var.use_vpc_link ? "VPC_LINK" : "INTERNET"
  connection_id   = one(aws_api_gateway_vpc_link.this[*].id)
}

# ── {proxy+} : 그 외 전 경로(/v1/*) — API Key 필수 + X-Origin-Secret 주입 ──
# 명시적 /health 리소스가 greedy proxy보다 우선하므로 헬스체크는 키 없이 통과.
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.acop.id
  parent_id   = aws_api_gateway_rest_api.acop.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy_any" {
  rest_api_id      = aws_api_gateway_rest_api.acop.id
  resource_id      = aws_api_gateway_resource.proxy.id
  http_method      = "ANY"
  authorization    = "NONE"
  api_key_required = true # ← Usage Plan 적용을 위해 API Key 강제

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "proxy_any" {
  rest_api_id             = aws_api_gateway_rest_api.acop.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy_any.http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  uri                     = local.backend_uri_proxy
  timeout_milliseconds    = var.integration_timeout_ms # 기본 29000; >29000은 계정 쿼터 상향 필요

  connection_type = var.use_vpc_link ? "VPC_LINK" : "INTERNET"
  connection_id   = one(aws_api_gateway_vpc_link.this[*].id)

  request_parameters = {
    "integration.request.path.proxy" = "method.request.path.proxy"
    # 정적 값은 작은따옴표로 감싼다 → 백엔드(FastAPI)가 이 헤더로 우회 직접호출 차단
    "integration.request.header.X-Origin-Secret" = "'${var.origin_secret}'"
  }
}

# ── 배포 + 스테이지 ──
resource "aws_api_gateway_deployment" "acop" {
  rest_api_id = aws_api_gateway_rest_api.acop.id

  triggers = {
    redeploy = sha1(jsonencode([
      aws_api_gateway_resource.health.id,
      aws_api_gateway_method.health_get.id,
      aws_api_gateway_integration.health_get.id,
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy_any.id,
      aws_api_gateway_integration.proxy_any.id,
      local.backend_base,
      var.use_vpc_link,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "acop" {
  rest_api_id   = aws_api_gateway_rest_api.acop.id
  deployment_id = aws_api_gateway_deployment.acop.id
  stage_name    = var.stage_name
}

# ── 팀별 API Key + Usage Plan(throttle/quota) ──
resource "aws_api_gateway_api_key" "team" {
  for_each = var.api_keys
  name     = "${var.name_prefix}-${each.key}"
  value    = each.value # FastAPI commerce_ops.api_keys 의 평문 키와 동일해야 사용량 로깅 연결됨
}

resource "aws_api_gateway_usage_plan" "acop" {
  name = "${var.name_prefix}-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.acop.id
    stage  = aws_api_gateway_stage.acop.stage_name
  }

  throttle_settings {
    rate_limit  = var.rate_limit # req/sec (100/min ≈ 1.67 → 기본 2)
    burst_limit = var.burst_limit
  }

  quota_settings {
    limit  = var.quota_limit
    period = var.quota_period # DAY / WEEK / MONTH
  }
}

resource "aws_api_gateway_usage_plan_key" "team" {
  for_each      = var.api_keys
  key_id        = aws_api_gateway_api_key.team[each.key].id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.acop.id
}
