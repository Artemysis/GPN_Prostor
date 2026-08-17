$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
docker compose -f (Join-Path $Root "docker-compose.yml") --project-directory $Root logs -f --tail=100 @args
