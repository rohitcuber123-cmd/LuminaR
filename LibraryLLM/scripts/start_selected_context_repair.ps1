param([switch]$RestartRag)
$ErrorActionPreference='Stop'
$projectRoot='D:\SDC\LibraryLLM'
$pythonExe=Join-Path $projectRoot '.venv\Scripts\python.exe'
$reportRoot=Join-Path $projectRoot 'reports'
$listener=Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    if (-not $RestartRag) {throw 'Port 8005 already has a listener; refusing a duplicate RAG service.'}
    $service=Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    $parent=Get-CimInstance Win32_Process -Filter "ProcessId = $($service.ParentProcessId)"
    if ($service.CommandLine -notmatch 'uvicorn rag.api:app' -or $parent.CommandLine -notlike "*$pythonExe*") {
        throw 'RAG process identity mismatch; refusing termination.'
    }
    if (Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq $service.ProcessId}) {
        throw 'Unexpected RAG child processes; refusing restart without inspection.'
    }
    Stop-Process -Id $service.ProcessId
    Stop-Process -Id $parent.ProcessId -ErrorAction SilentlyContinue
    for ($attempt=0; $attempt -lt 50; $attempt++) {
        if (-not (Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue)) {break}
        Start-Sleep -Milliseconds 100
    }
}
if (Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue) {throw 'Port 8005 is still occupied.'}
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
$env:ASSISTANT_ROUTER_V2_VARIANT=''
$env:ASSISTANT_ROUTER_V2_RETRY='0'
$env:ASSISTANT_PROFILE_PATH=Join-Path $reportRoot 'assistant_selected_context_profiles.jsonl'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONUTF8='1'
$process=Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','rag.api:app','--host','127.0.0.1','--port','8005') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reportRoot 'assistant_selected_context_rag.out.log') -RedirectStandardError (Join-Path $reportRoot 'assistant_selected_context_rag.err.log')
@{launcher_pid=$process.Id;port=8005;module='rag.api';router_mode='existing_qwen'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'assistant_selected_context_process.json')
Write-Output "Started existing_qwen RAG launcher $($process.Id)"
