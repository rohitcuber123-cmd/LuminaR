param([switch]$Frontend)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:PYTHONUTF8='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$taskStarted=@()
foreach ($taskSpec in @(@('backend.main',8002),@('search.api',8003),@('recommendation.api',8004))) {
    if (Get-NetTCPConnection -LocalPort $taskSpec[1] -State Listen -ErrorAction SilentlyContinue) { continue }
    $taskProcess=Start-Process -FilePath (Join-Path $taskRoot '.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn',"$($taskSpec[0]):app",'--host','127.0.0.1','--port',"$($taskSpec[1])",'--workers','1') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot "reports\kg_service_$($taskSpec[1])_stdout.log") -RedirectStandardError (Join-Path $taskRoot "reports\kg_service_$($taskSpec[1])_stderr.log")
    $taskStarted+=@{pid=$taskProcess.Id;module=$taskSpec[0];port=$taskSpec[1]}
}
if ($Frontend -and -not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    $taskVite=Start-Process -FilePath 'C:\Program Files\nodejs\node.exe' -ArgumentList @((Join-Path $taskRoot 'frontend\node_modules\vite\bin\vite.js'),'--host','127.0.0.1','--port','5173') -WorkingDirectory (Join-Path $taskRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot 'reports\kg_vite_stdout.log') -RedirectStandardError (Join-Path $taskRoot 'reports\kg_vite_stderr.log')
    $taskStarted+=@{pid=$taskVite.Id;module='vite';port=5173}
}
$taskStarted | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot 'reports\kg_service_pids.json') -Encoding UTF8
$taskStarted | ConvertTo-Json
