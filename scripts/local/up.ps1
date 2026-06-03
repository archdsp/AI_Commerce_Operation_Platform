#!/usr/bin/env pwsh
# ── 로컬 전 구간 원커맨드 기동 (Windows 네이티브 PowerShell) ─────────────────
# Docker 인프라(MySQL·Redpanda·Qdrant) + Ollama로 데이터→스트리밍→집계→RAG→게이트웨이까지.
#   powershell -ExecutionPolicy Bypass -File scripts\local\up.ps1
# 사전: Docker Desktop · Ollama(Windows) · Python + pip install -r requirements.txt. 상세 docs/LOCAL.md
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
$env:ENV_FILE = ".env.local"
$Py = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$ComposeFile = "docker-compose.local.yml"

function Wait-Health($Name, $Timeout = 120) {
  $i = 0; Write-Host -NoNewline "   $Name health 대기"
  while ($true) {
    $status = (docker inspect -f '{{.State.Health.Status}}' $Name 2>$null)
    if ($status -eq "healthy") { Write-Host " ✓"; break }
    $i += 2; if ($i -ge $Timeout) { Write-Host " ✗ timeout"; docker logs --tail 25 $Name; throw "$Name health timeout" }
    Start-Sleep 2; Write-Host -NoNewline "."
  }
}
function Wait-Http($Url, $Timeout = 60) {
  $i = 0; Write-Host -NoNewline "   $Url 대기"
  while ($true) {
    try { Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 2 | Out-Null; Write-Host " ✓"; break } catch {}
    $i += 2; if ($i -ge $Timeout) { Write-Host " ✗ timeout"; throw "$Url timeout" }
    Start-Sleep 2; Write-Host -NoNewline "."
  }
}

Write-Host "▶ 0/8 사전 점검"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "docker 필요 — Docker Desktop 설치/실행" }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw "ollama 필요 — https://ollama.com" }
if (-not (Test-Path .env.local)) { Copy-Item .env.local.example .env.local; Write-Host "   .env.local 생성(예시 복사)" }
$mLine = (Select-String -Path .env.local -Pattern '^VLLM_MODEL=' | Select-Object -First 1).Line
$Model = if ($mLine) { ($mLine -split '=', 2)[1].Trim() } else { "qwen2.5:7b" }
if (-not $Model) { $Model = "qwen2.5:7b" }

Write-Host "▶ 1/8 인프라 기동 (MySQL · Redpanda · Qdrant)"
docker compose -f $ComposeFile up -d
Wait-Health "acop-mysql" 150
Wait-Health "acop-redpanda" 90
Wait-Http "http://localhost:6333/readyz" 60

Write-Host "▶ 2/8 Ollama 모델 준비: $Model"
try { Invoke-WebRequest "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 3 | Out-Null }
catch { throw "Ollama 서버 미응답 — 'ollama serve'(또는 Ollama 앱) 실행 후 재시도" }
if (-not (ollama list | Select-String $Model)) { ollama pull $Model }

Write-Host "▶ 3/8 MySQL 스키마 + 샘플 적재 + api_keys 시드"
& $Py scripts/setup_mysql.py
Write-Host "▶ 4/8 엣지 샤드 생성 (샘플 데이터)"
& $Py scripts/prepare_edges.py
Write-Host "▶ 5/8 Kafka 토픽 생성"
& $Py scripts/kafka_admin.py --create
Write-Host "▶ 6/8 발행 → 감성/VOC 분석 → 카테고리 집계"
& $Py scripts/run.py --rate 4000 --duration 120
& $Py scripts/review_analyzer.py --duration 30
& $Py scripts/metric_aggregator.py --duration 30
Write-Host "▶ 7/8 RAG 적재 (리뷰 임베딩 → Qdrant)"
& $Py scripts/reload_qdrant.py --limit 6000
Write-Host "▶ 8/8 게이트웨이 기동"
& "$Root/scripts/local/serve.ps1" start

Write-Host ""
Write-Host "✅ 로컬 기동 완료"
Write-Host "   • 웹 UI    : http://localhost:8000"
Write-Host "   • 데모 키  : oy_demo_md_key  (voc: oy_demo_voc_key · ops: oy_demo_ops_key)"
Write-Host "   • 종료     : powershell -ExecutionPolicy Bypass -File scripts\local\down.ps1"
