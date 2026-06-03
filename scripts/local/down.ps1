#!/usr/bin/env pwsh
# 로컬 스택 종료 — Windows 네이티브 PowerShell.
#   powershell -ExecutionPolicy Bypass -File scripts\local\down.ps1            # 컨테이너 정지(볼륨 보존)
#   powershell -ExecutionPolicy Bypass -File scripts\local\down.ps1 -Purge     # 볼륨까지 삭제(완전 초기화)
param([switch]$Purge)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

& "$Root/scripts/local/serve.ps1" stop

if ($Purge) {
  Write-Host "컨테이너 + 볼륨 삭제(완전 초기화)"
  docker compose -f docker-compose.local.yml down -v
} else {
  Write-Host "컨테이너 정지(볼륨 보존)"
  docker compose -f docker-compose.local.yml down
}
Write-Host "✓ 종료"
