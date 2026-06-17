# ════════════════════════════════════════════════════════════════════
# auditar.ps1 — corre la bateria de auditoria de codigo de Verifika.
# Herramientas gratis y de uso comercial. Config en pyproject.toml.
#   .\auditar.ps1            -> ruff + bandit (rapido, lo que se muestra)
#   .\auditar.ps1 -Todo      -> agrega mypy y pytest (mas lento)
# Semgrep no corre nativo en Windows: usarlo via Docker o WSL:
#   docker run --rm -v "${PWD}:/src" semgrep/semgrep semgrep scan --config auto /src
# ════════════════════════════════════════════════════════════════════
param([switch]$Todo)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$fallas = 0

Write-Host "`n=== RUFF (estilo y bugs) ===" -ForegroundColor Cyan
python -m ruff check app/ scripts/ correr_pruebas.py correr_molino_multiturno.py
if ($LASTEXITCODE -ne 0) { $fallas++ } else { Write-Host "OK" -ForegroundColor Green }

Write-Host "`n=== BANDIT (seguridad, medium o peor) ===" -ForegroundColor Cyan
python -m bandit -r app/ -q --severity-level medium
if ($LASTEXITCODE -ne 0) { $fallas++ } else { Write-Host "OK: sin hallazgos medium/high" -ForegroundColor Green }

if ($Todo) {
    Write-Host "`n=== MYPY (tipos, modo gradual) ===" -ForegroundColor Cyan
    python -m mypy
    if ($LASTEXITCODE -ne 0) { $fallas++ } else { Write-Host "OK" -ForegroundColor Green }

    Write-Host "`n=== PYTEST (tests/) ===" -ForegroundColor Cyan
    $py = Join-Path $root "venv-win\Scripts\python.exe"
    if (Test-Path $py) { & $py -m pytest tests/ -q } else { python -m pytest tests/ -q }
    if ($LASTEXITCODE -ne 0) { $fallas++ } else { Write-Host "OK" -ForegroundColor Green }
}

Write-Host "`n================================" -ForegroundColor Cyan
if ($fallas -eq 0) { Write-Host "AUDITORIA: TODO VERDE" -ForegroundColor Green }
else { Write-Host "AUDITORIA: $fallas herramienta(s) con hallazgos" -ForegroundColor Yellow }
exit $fallas
