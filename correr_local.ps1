# ════════════════════════════════════════════════════════════════════
# correr_local.ps1 — corre el bot en local cargando .secrets6.env
# ════════════════════════════════════════════════════════════════════
# El codigo NO autocarga el .env, asi que este script lee .secrets6.env y setea
# las variables de entorno antes de lanzar Python con el venv de Windows.
#
# Uso:
#   .\correr_local.ps1 smoke                 # smoke de 3 mensajes
#   .\correr_local.ps1 smoke -AllNemotron    # todo el pipeline sobre Nemotron (key gratis)
#   .\correr_local.ps1 molino                # corre correr_pruebas.py (las 100 preguntas)
#   .\correr_local.ps1 server                # levanta uvicorn en :8080
#   .\correr_local.ps1 smoke verifika_prod   # tienda explicita
# ════════════════════════════════════════════════════════════════════
param(
    [Parameter(Position=0)][string]$Modo = "smoke",
    [Parameter(Position=1)][string]$Tienda = "",
    [switch]$AllNemotron,
    [switch]$AllKimi,
    [switch]$CorrectorKimi,
    [string]$KimiModel = "",
    [switch]$AllGemini,
    [switch]$AllOpenRouter,
    [string]$OrModel = "",
    [switch]$SinCorrector,
    [switch]$InterpGroq,
    [switch]$Aplicar,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$Resto
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Salida en UTF-8 para que los acentos no salgan como signos raros en consola.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$envFile = Join-Path $root ".secrets6.env"
if (-not (Test-Path $envFile)) { throw "No encuentro .secrets6.env en $root" }

# Cargar variables del archivo (ignora comentarios y lineas vacias)
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $idx = $line.IndexOf("=")
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        Set-Item -Path "Env:$name" -Value $value
    }
}

# El bot lee GCP_PROJECT; el .env viejo usaba PROJECT_ID. Lo espejamos.
if (-not $env:GCP_PROJECT -and $env:PROJECT_ID) { $env:GCP_PROJECT = $env:PROJECT_ID }
if (-not $env:GCP_PROJECT) { $env:GCP_PROJECT = "memory-engine-v1" }

# Override opcional: todo el pipeline sobre Nemotron (sin DeepSeek).
if ($AllNemotron) {
    $env:LLM_PROVIDER = "nemotron"
    $env:INTERPRETER_PROVIDER = "nemotron"
    $env:VERIFIKA_CORRECTOR_PROVIDER = "nemotron"
    Write-Host "[modo] TODO el pipeline sobre Nemotron" -ForegroundColor Cyan
}

# Override opcional: Kimi (Moonshot) gratis via NVIDIA. La clave vive en
# .secrets7.env, asi que la cargamos ademas del .secrets6.env de base.
if ($AllKimi -or $CorrectorKimi) {
    $kimiFile = Join-Path $root ".secrets7.env"
    if (-not (Test-Path $kimiFile)) { throw "No encuentro .secrets7.env (clave de Kimi) en $root" }
    Get-Content $kimiFile | ForEach-Object {
        $line = $_.Trim().TrimStart([char]0xFEFF)
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            Set-Item -Path "Env:$($line.Substring(0, $idx).Trim())" -Value $line.Substring($idx + 1).Trim()
        }
    }
    # Override del modelo NVIDIA a probar (ej qwen/qwen3-next-80b-a3b-instruct).
    # Etiqueta el CSV de salida para no pisar corridas al comparar.
    if ($KimiModel) {
        $env:KIMI_MODEL = $KimiModel
        $env:BENCH_TAG = ($KimiModel -split "/")[-1]
        Write-Host "[modelo] $KimiModel  (CSV -> resultados_multiturno_$($env:BENCH_TAG).csv)" -ForegroundColor Cyan
    }
}
# Override opcional: OpenRouter (una clave, cientos de modelos). Clave en .secrets10.env.
if ($AllOpenRouter) {
    $orFile = Join-Path $root ".secrets10.env"
    if (-not (Test-Path $orFile)) { throw "No encuentro .secrets10.env (clave de OpenRouter) en $root" }
    Get-Content $orFile | ForEach-Object {
        $line = $_.Trim().TrimStart([char]0xFEFF)
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            Set-Item -Path "Env:$($line.Substring(0, $idx).Trim())" -Value $line.Substring($idx + 1).Trim()
        }
    }
    if ($OrModel) { $env:OPENROUTER_MODEL = $OrModel }
    $env:LLM_PROVIDER = "openrouter"
    $env:INTERPRETER_PROVIDER = "openrouter"
    $env:VERIFIKA_CORRECTOR_PROVIDER = "openrouter"
    $env:VERIFIKA_CORRECTOR_MODEL = $env:OPENROUTER_MODEL
    $env:BENCH_TAG = "or-" + ($env:OPENROUTER_MODEL -split "/")[-1]
    Write-Host "[modo] TODO el pipeline sobre OpenRouter ($($env:OPENROUTER_MODEL))" -ForegroundColor Cyan
}

# Override opcional: Gemini gratis (free tier). La clave vive en .secrets8.env.
if ($AllGemini) {
    $geminiFile = Join-Path $root ".secrets8.env"
    if (-not (Test-Path $geminiFile)) { throw "No encuentro .secrets8.env (clave de Gemini) en $root" }
    Get-Content $geminiFile | ForEach-Object {
        $line = $_.Trim().TrimStart([char]0xFEFF)
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            Set-Item -Path "Env:$($line.Substring(0, $idx).Trim())" -Value $line.Substring($idx + 1).Trim()
        }
    }
    $env:LLM_PROVIDER = "gemini"
    $env:INTERPRETER_PROVIDER = "gemini"
    $env:VERIFIKA_CORRECTOR_PROVIDER = "gemini"
    $env:VERIFIKA_CORRECTOR_MODEL = $env:GEMINI_MODEL
    $env:BENCH_TAG = "gemini-" + $env:GEMINI_MODEL
    Write-Host "[modo] TODO el pipeline sobre Gemini ($($env:GEMINI_MODEL))" -ForegroundColor Cyan
}

if ($AllKimi) {
    $env:LLM_PROVIDER = "kimi"
    $env:INTERPRETER_PROVIDER = "kimi"
    $env:VERIFIKA_CORRECTOR_PROVIDER = "kimi"
    $env:VERIFIKA_CORRECTOR_MODEL = $env:KIMI_MODEL
    Write-Host "[modo] TODO el pipeline sobre Kimi ($($env:KIMI_MODEL))" -ForegroundColor Cyan
}
elseif ($CorrectorKimi) {
    $env:CORRECTOR_ANCLADO = "true"
    $env:VERIFIKA_CORRECTOR_PROVIDER = "kimi"
    $env:VERIFIKA_CORRECTOR_MODEL = $env:KIMI_MODEL
    Write-Host "[modo] Corrector sobre Kimi ($($env:KIMI_MODEL)), resto igual" -ForegroundColor Cyan
}

# Interpretador en Groq aunque el resto vaya al modelo a prueba. Asi se mide el
# bot como saldria a produccion: el interpretador no necesita el modelo grande y
# en Groq tarda menos de 1s (en OpenRouter promedia 4s con picos de 22s).
if ($InterpGroq) {
    $env:INTERPRETER_PROVIDER = "groq"
    Write-Host "[modo] Interpretador sobre Groq, resto segun -All*" -ForegroundColor Cyan
}

# Apagar el corrector LLM (mide solo Solver + verificadores deterministas; mucho
# mas rapido, util para el molino largo).
if ($SinCorrector) {
    $env:CORRECTOR_ANCLADO = "false"
    Write-Host "[modo] corrector LLM APAGADO" -ForegroundColor Cyan
}

if ($Tienda) { $env:SMOKE_TIENDA = $Tienda }

$py = Join-Path $root "venv-win\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "No encuentro el venv: $py" }

Write-Host "[provider] Solver=$($env:LLM_PROVIDER) Interpreter=$($env:INTERPRETER_PROVIDER) Corrector=$($env:VERIFIKA_CORRECTOR_PROVIDER)" -ForegroundColor Green

switch ($Modo) {
    "smoke"        { & $py "smoke_local.py" $env:SMOKE_TIENDA }
    "molino"       { & $py "correr_pruebas.py" }
    "molino-multi" { & $py "correr_molino_multiturno.py" $env:SMOKE_TIENDA }
    "molino-focos" { & $py "correr_molino_focos.py" $env:SMOKE_TIENDA }
    "arnes"        {
        # Arnes de aserciones por turno (estilo Promptfoo/DeepEval). Acepta
        # flags extra: --solo a01,a05 | --solo-fallidos
        $extra = @()
        if ($Tienda) { $extra += $Tienda }
        if ($Resto) { $extra += $Resto }
        & $py "arnes_aserciones.py" @extra
    }
    "py"           {
        # Passthrough generico: corre cualquier script con el venv y las env
        # de .secrets6.env cargadas. Ej: .\correr_local.ps1 py scripts\x.py arg1
        $scriptArgs = @()
        if ($Tienda) { $scriptArgs += $Tienda }
        if ($Resto) { $scriptArgs += $Resto }
        & $py @scriptArgs
    }
    "enriquecer"   {
        # Completa origen/contenido_caja/garantia_detalle del catalogo por codigo.
        # Sin -Aplicar es dry-run (muestra y no escribe). Tienda default verifika_prod.
        $extra = @()
        if ($Tienda) { $extra += $Tienda }
        if ($Aplicar) { $extra += "--aplicar" }
        & $py "scripts\enriquecer_catalogo.py" @extra
    }
    "server"       { & $py -m uvicorn app.main:app --host 127.0.0.1 --port 8080 }
    default        { throw "Modo desconocido: $Modo. Use smoke | molino | molino-multi | molino-focos | arnes | enriquecer | server" }
}
