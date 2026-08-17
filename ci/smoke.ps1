$ErrorActionPreference = "Stop"

$failures = 0

function Check([string]$Name, [scriptblock]$Check) {
    try {
        $result = & $Check
        if ($result) {
            Write-Host "[PASS] $Name" -ForegroundColor Green
        } else {
            Write-Host "[FAIL] $Name" -ForegroundColor Red
            $script:failures++
        }
    } catch {
        Write-Host "[FAIL] $Name — $($_.Exception.Message)" -ForegroundColor Red
        $script:failures++
    }
}

Check "Backend /health" {
    (Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing).StatusCode -eq 200
}

Check "Backend API отвечает (GET /api/v1/companies)" {
    (Invoke-WebRequest -Uri "http://localhost:8000/api/v1/companies" -UseBasicParsing).StatusCode -eq 200
}

Check "Frontend раздаёт SPA (http://localhost:3000)" {
    $r = Invoke-WebRequest -Uri "http://localhost:3000/" -UseBasicParsing
    $r.StatusCode -eq 200 -and $r.Content -match "<div id=`"root`">"
}

Check "Nginx-прокси /api -> backend (http://localhost:3000/api/v1/companies)" {
    (Invoke-WebRequest -Uri "http://localhost:3000/api/v1/companies" -UseBasicParsing).StatusCode -eq 200
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "Smoke: все проверки пройдены." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Smoke: пройдено с ошибками ($failures). Стенд не поднимался? Запустите .\ci\up.ps1" -ForegroundColor Red
    exit 1
}
