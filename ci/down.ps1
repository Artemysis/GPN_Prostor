param([switch]$Volumes)

$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
$Compose = Join-Path $Root "docker-compose.yml"

if ($Volumes) {
    docker compose -f $Compose --project-directory $Root down -v
    Write-Host "[OK] Стенд остановлен, тома (данные БД и MinIO) удалены." -ForegroundColor Yellow
} else {
    docker compose -f $Compose --project-directory $Root down
    Write-Host "[OK] Стенд остановлен. Данные сохранены в томах (полная очистка: .\ci\down.ps1 -Volumes)" -ForegroundColor Green
}
