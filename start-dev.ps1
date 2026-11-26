[CmdletBinding()]
param(
    [switch]$SkipDependencyCheck
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$frontendRoot = Join-Path (Split-Path -Parent $projectRoot) "frontend-agenteVendedor"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$venvUvicorn = Join-Path $projectRoot ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "No se encontró el entorno virtual en $venvPython. Créelo e instale las dependencias con: py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

if (-not (Test-Path -LiteralPath $frontendRoot)) {
    throw "No se encontró la carpeta del frontend: $frontendRoot"
}

if (-not $SkipDependencyCheck) {
    if (-not (Test-Path -LiteralPath $venvUvicorn)) {
        throw "Uvicorn no está instalado en el entorno virtual. Ejecute: .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    }

    if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules"))) {
        throw "No se encontraron las dependencias del frontend. Ejecute: cd frontend; npm install"
    }
}

$backendCommand = "Set-Location -LiteralPath '$projectRoot'; & '$venvUvicorn' main:app --reload --host 127.0.0.1 --port 8000"
$frontendCommand = "Set-Location -LiteralPath '$frontendRoot'; npm run dev"

Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $backendCommand
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $frontendCommand

Write-Host "Backend iniciado en http://127.0.0.1:8000"
Write-Host "Frontend iniciando en http://localhost:5173"
Write-Host "LM Studio debe estar iniciado antes de enviar consultas."
