# AI Commerce Ops — API Gateway (Terraform)

FastAPI 게이트웨이(`src/gateway`) 앞단에 **AWS API Gateway(REST)** 를 두어 인증·throttle·quota·TLS를
관리형으로 처리하는 IaC.

```
Client ──X-API-Key──▶ [API Gateway REST]                     ──▶ [FastAPI / EC2:8000]
                       · API Key + Usage Plan(rate/quota)        · X-API-Key → api_keys (사용량 로깅)
                       · {proxy+} → HTTP_PROXY                   · X-Origin-Secret 검증(우회 차단)
                       · X-Origin-Secret 헤더 주입               · LangGraph → vLLM / RDS / Qdrant
```

## 왜 REST API인가 (HTTP API 아님)
- **API Key + Usage Plan**(키별 rate limit·quota)은 REST API 전용 — 이 프로젝트의 `api_keys`(md/voc/ops 팀) 모델에 부합.
- **통합 타임아웃을 29s 이상으로 상향 가능**(쿼터 증설) — LLM 에이전트는 vLLM 2~3회+교차리전 RDS로 꼬리 지연이 큼.
- 실측: `/v1/chat` 성공 ~7~16s, self-correction 시 더 큼.

## 구성 요소 (`main.tf`)
| 리소스 | 역할 |
|--------|------|
| `aws_api_gateway_rest_api` | REGIONAL REST API |
| `/health` (GET, 키 불필요) | LB/모니터 헬스체크 — greedy proxy보다 우선 |
| `{proxy+}` (ANY, **키 필수**) | `/v1/*` 전부를 백엔드로 프록시, `X-Origin-Secret` 주입 |
| `aws_api_gateway_api_key` ×N | 팀별 키 (값=FastAPI 평문 키와 동일) |
| `aws_api_gateway_usage_plan` (+ `_key`) | throttle(rate/burst) + quota |
| `deployment` + `stage` | 배포/스테이지 |

## 사용법
```bash
cd infra/terraform/api-gateway
cp terraform.tfvars.example terraform.tfvars   # 값 편집 (gitignore됨)
terraform init
terraform plan
terraform apply
terraform output invoke_url
```

호출 (스테이지가 경로에 포함됨):
```bash
BASE=$(terraform output -raw invoke_url)        # https://{id}.execute-api.{region}.amazonaws.com/prod
curl "$BASE/health"                             # 키 불필요
curl -H "X-API-Key: oy_demo_md_key" -H "Content-Type: application/json" \
     -d '{"query":"카테고리별 매출 상위 5개"}' "$BASE/v1/chat"
```

## ⚠️ 두 가지 정합 필수
1. **시크릿**: `origin_secret`(tfvars) == 백엔드 `.env` 의 `GATEWAY_ORIGIN_SECRET`.
   불일치 시 백엔드가 `/v1/*` 를 403으로 거부한다(엣지 우회 차단이 의도대로 동작하는 것).
2. **API 키**: `api_keys`(tfvars) 의 평문 == `commerce_ops.api_keys` 시드 평문.
   그래야 API Gateway가 throttle하고, FastAPI는 같은 키로 사용량을 로깅한다.

## 백엔드 준비
```bash
# EC2의 .env
echo "GATEWAY_ORIGIN_SECRET=<tfvars의 origin_secret과 동일>" >> .env
PYTHONPATH=src uvicorn gateway.app:app --host 0.0.0.0 --port 8000
```

## 보안 단계 (PoC → 운영)
- **현재(이 IaC)**: `backend_host` = **EC2 public DNS** 직접 프록시(PoC). 공개 8000은 `X-Origin-Secret`으로 보호.
  REST API 공개 통합은 고정 출구 IP가 없어 SG로 막기 어렵기 때문.
- **운영 권장**: `backend_host` 를 **내부 NLB DNS**로 바꾸고 `{proxy+}` 통합을 **VPC Link(`aws_api_gateway_vpc_link`)** 로 전환.
  EC2 8000은 비공개(SG는 NLB만 허용). 본 베이스라인에서 VPC Link/NLB 리소스는 미포함(다음 단계).
- 추가 권장: ACM 인증서 + 커스텀 도메인(스테이지 경로 제거), AWS WAF 연결, CloudWatch 액세스 로그.

## API Gateway에 올리지 않은 것
- **질의 해시 캐시**: API Gateway 캐시는 경로/쿼리 기준이라 POST 본문 해시엔 부적합 → 앱(Redis) 또는 v1 생략.
- **스트리밍**: 현재 통짜 JSON이라 무관. 토큰 스트리밍 도입 시 REST/HTTP API 불가 → WebSocket/Lambda streaming 필요.

> 참고: 이 디렉터리는 `terraform`이 로컬 미설치라 `terraform validate` 미수행. aws provider `~> 5.0` 스키마 기준 작성.
