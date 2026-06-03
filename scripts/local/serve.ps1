#!/usr/bin/env pwsh
# 게이트웨이 기동/종료/상태 — Windows 네이티브 PowerShell.
#   powershell -ExecutionPolicy Bypass -File scripts\local\serve.ps1 start|stop|status
# 환경변수: GW_PORT(기본 8000) · ENV_FILE(기본 .env.local) · PYTHON(기본 python)
param([string]$Action = "start")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Port = if ($env:GW_PORT) { $env:GW_PORT } else { "8000" }
$Dir  = Join-Path $Root ".local"
$Log  = Join-Path $Dir "gateway.log"
$PidFile = Join-Path $Dir "gateway.pid"
$Py   = if ($env:PYTHON) { $env:PYTHON } else { "python" }
if (-not $env:ENV_FILE) { $env:ENV_FILE = ".env.local" }
$env:GW_PORT = $Port
New-Item -ItemType Directory -Force -Path $Dir | Out-Null

function Test-Healthy {
  try { Invoke-WebRequest "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true }
  catch { return $false }
}

switch ($Action) {
  "start" {
    if (Test-Healthy) { Write-Host "✓ 이미 실행 중 · http://localhost:$Port"; break }
    Set-Location $Root
    $proc = Start-Process -FilePath $Py -ArgumentList "scripts/run_gateway.py" -PassThru `
              -WindowStyle Hidden -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
    $proc.Id | Out-File -Encoding ascii $PidFile
    for ($i = 0; $i -lt 40; $i++) {
      if (Test-Healthy) { Write-Host "✓ 기동 완료 · http://localhost:$Port · log=$Log"; return }
      Start-Sleep 1
    }
    Write-Host "✗ 기동 실패(health 미응답) — 로그:"; if (Test-Path $Log) { Get-Content $Log -Tail 30 }
  }
  "stop" {
    if (Test-Path $PidFile) {
      Stop-Process -Id (Get-Content $PidFile) -ErrorAction SilentlyContinue
      Remove-Item $PidFile -ErrorAction SilentlyContinue
      Write-Host "종료"
    } else { Write-Host ":$Port PID 파일 없음/이미 종료" }
  }
  "status" { if (Test-Healthy) { "RUNNING :$Port" } else { "NOT running :$Port" } }
  default  { "usage: serve.ps1 start|stop|status" }
}
