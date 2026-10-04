param([ValidateSet('baseline','final','local')][string]$Phase = 'local', [switch]$RagOnly)
$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:ASSISTANT_ENABLED = 'true'
$env:ASSISTANT_MUTATING_ACTIONS_ENABLED = 'false'
$env:LUMINAR_MOCK_LLM = '0'
$env:LUMINAR_DEBUG_PROMPT = '0'
$env:ASSISTANT_PROFILE_PATH = Join-Path $projectPath "reports\part3_repair_profiles_$Phase.jsonl"
$serviceSpecs = @(@('backend.main',8002),@('search.api',8003),@('recommendation.api',8004),@('rag.api',8005))
if ($RagOnly) { $serviceSpecs = ,@('rag.api',8005) }
$started = @()
foreach ($spec in $serviceSpecs) {
    if (Get-NetTCPConnection -LocalPort $spec[1] -State Listen -ErrorAction SilentlyContinue) { throw "Port $($spec[1]) already occupied; no duplicate worker started." }
    $service = Start-Process -FilePath (Join-Path $projectPath '.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn',"$($spec[0]):app",'--host','127.0.0.1','--port',"$($spec[1])",'--workers','1') -WorkingDirectory $projectPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectPath "reports\part3_repair_${Phase}_$($spec[1])_stdout.log") -RedirectStandardError (Join-Path $projectPath "reports\part3_repair_${Phase}_$($spec[1])_stderr.log")
    $started += @{ module=$spec[0]; port=$spec[1]; pid=$service.Id }
}
$started | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectPath "reports\part3_repair_${Phase}_pids.json")
$started | ConvertTo-Json
