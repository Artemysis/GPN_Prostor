$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent

function Wait-Url([string]$Url, [string]$Name, [int]$Tries = 90) {
    for ($i = 1; $i -le $Tries; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -lt 500) {
                Write-Host "[OK] $Name отвечает ($Url)" -ForegroundColor Green
                return $true
            }
        } catch { }
        Write-Host "  ожидание: $Name ... ($i/$Tries)"
        Start-Sleep -Seconds 2
    }
    Write-Host "[FAIL] $Name не поднялся за отведённое время ($Url)" -ForegroundColor Red
    return $false
}

Write-Host "=== ПРОСТОР 2.0 — подъём локального стенда ===" -ForegroundColor Cyan

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker не найден. Установите Docker Desktop."
}

$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Root ".env.example") $envFile
    Write-Host "[INFO] Создан .env из .env.example" -ForegroundColor Yellow
}

$envContent = Get-Content $envFile -Raw
if ($envContent -match 'LLM_API_KEY=\s*$') {
    Write-Host "[WARN] В .env пустой LLM_API_KEY — ИИ-функции (чат, fill-ai, анализ) работать не будут." -ForegroundColor Yellow
    Write-Host "       Стенд без ключа всё равно поднимется: справочники, заявки, конструктор ТЗ." -ForegroundColor Yellow
}

Write-Host "`n[1/3] Сборка образов (первый раз долго: качаются Python, Node, PyTorch)..." -ForegroundColor Cyan
docker compose -f (Join-Path $Root "docker-compose.yml") --project-directory $Root build
if ($LASTEXITCODE -ne 0) { throw "Сборка не удалась." }

Write-Host "`n[2/3] Запуск контейнеров (postgres, minio, redis, backend, frontend)..." -ForegroundColor Cyan
docker compose -f (Join-Path $Root "docker-compose.yml") --project-directory $Root up -d
if ($LASTEXITCODE -ne 0) { throw "Запуск не удался." }

Write-Host "`n[3/3] Ожидание готовности сервисов..." -ForegroundColor Cyan
$backendOk = Wait-Url "http://localhost:8000/health" "Backend"
$frontendOk = Wait-Url "http://localhost:3000/" "Frontend"

Write-Host ""
Write-Host "=== Стенд поднят ===" -ForegroundColor Green
Write-Host "  Frontend (SPA):        http://localhost:3000"
Write-Host "  Backend API (Swagger): http://localhost:8000/docs"
Write-Host "  Health:                http://localhost:8000/health"
Write-Host "  MinIO Console:         http://localhost:9001  (minioadmin/minioadmin)"
Write-Host ""
Write-Host "Логи:     .\ci\logs.ps1"
Write-Host "Проверки: .\ci\smoke.ps1"
Write-Host "Останов:  .\ci\down.ps1       (с удалением данных: .\ci\down.ps1 -Volumes)"

if (-not ($backendOk -and $frontendOk)) { exit 1 }
