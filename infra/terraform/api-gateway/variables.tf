variable "region" {
  description = "AWS 리전 (백엔드 EC2와 동일 권장)"
  type        = string
  default     = "ap-northeast-2"
}

variable "name_prefix" {
  description = "리소스 이름 접두사"
  type        = string
  default     = "acop-gateway"
}

variable "backend_host" {
  description = "FastAPI 백엔드 호스트 — PoC: EC2 public DNS / 운영: 내부 NLB DNS"
  type        = string
}

variable "backend_port" {
  description = "FastAPI 포트"
  type        = number
  default     = 8000
}

variable "stage_name" {
  description = "스테이지 이름. 호출 경로에 포함됨(예: /prod/v1/chat). 커스텀 도메인 매핑 시 제거 가능"
  type        = string
  default     = "prod"
}

variable "origin_secret" {
  description = "FastAPI GATEWAY_ORIGIN_SECRET 와 동일한 값 (우회 직접호출 차단용 공유 시크릿)"
  type        = string
  sensitive   = true
}

variable "api_keys" {
  description = "팀→평문 API 키 맵. FastAPI commerce_ops.api_keys 의 평문과 동일해야 사용량 로깅이 연결됨"
  type        = map(string)
  sensitive   = true
  # 예: { md = "oy_demo_md_key", voc = "oy_demo_voc_key", ops = "oy_demo_ops_key" }
}

variable "rate_limit" {
  description = "Usage Plan throttle 정상 속도 (req/sec). 100 req/min ≈ 1.67"
  type        = number
  default     = 2
}

variable "burst_limit" {
  description = "Usage Plan throttle 버스트"
  type        = number
  default     = 10
}

variable "quota_limit" {
  description = "기간당 최대 요청 수"
  type        = number
  default     = 10000
}

variable "quota_period" {
  description = "quota 기간: DAY / WEEK / MONTH"
  type        = string
  default     = "DAY"
}

variable "integration_timeout_ms" {
  description = "통합 타임아웃(ms). REST API 기본/최대 29000; >29000은 계정 쿼터 상향 필요. LLM 꼬리 지연 대비"
  type        = number
  default     = 29000
}

# ── 운영용 사설 통합 (use_vpc_link=true 일 때만) ──
variable "use_vpc_link" {
  description = "true면 내부 NLB + VPC Link 사설 통합(운영, EC2 비공개). false면 공개 EC2 HTTP_PROXY(PoC)"
  type        = bool
  default     = false
}

variable "vpc_id" {
  description = "use_vpc_link=true 일 때 NLB target group의 VPC ID"
  type        = string
  default     = ""
}

variable "nlb_subnet_ids" {
  description = "use_vpc_link=true 일 때 내부 NLB가 위치할 서브넷 ID 목록"
  type        = list(string)
  default     = []
}

variable "backend_instance_id" {
  description = "use_vpc_link=true 일 때 NLB가 가리킬 FastAPI EC2 인스턴스 ID"
  type        = string
  default     = ""
}

variable "nlb_listener_port" {
  description = "내부 NLB 리스너 포트 (API Gateway가 이 포트로 NLB에 접속)"
  type        = number
  default     = 80
}
