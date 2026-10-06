param([ValidateSet('dependencies','restart-search','experimental-rag','restore-rag')][string]$Mode='dependencies')
$ErrorActionPreference='Stop'
$projectRoot='D:\SDC\LibraryLLM'
$pythonExe=Join-Path $projectRoot '.venv\Scripts\python.exe'
$reportRoot=Join-Path $projectRoot 'reports'
Set-Location -LiteralPath $projectRoot
function Start-Api([string]$Module,[int]$Port,[string]$LogName) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $Port already has a listener; refusing to create a duplicate service."
    }
    $process=Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn',"${Module}:app",'--host','127.0.0.1','--port',"$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reportRoot "$LogName.out.log") -RedirectStandardError (Join-Path $reportRoot "$LogName.err.log")
    return @{launcher_pid=$process.Id;port=$Port;module=$Module}
}
if ($Mode -eq 'dependencies') {
    $started=@()
    $started+=Start-Api 'backend.main' 8002 'assistant_router_v5_core'
    $started+=Start-Api 'search.api' 8003 'assistant_router_v5_search_service'
    $started+=Start-Api 'recommendation.api' 8004 'assistant_router_v5_recommendation'
    if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) {throw 'Vite listener already exists'}
    $vite=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c','npm run dev -- --host 127.0.0.1 --port 5173') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reportRoot 'assistant_router_v5_vite.out.log') -RedirectStandardError (Join-Path $reportRoot 'assistant_router_v5_vite.err.log')
    $started+=@{launcher_pid=$vite.Id;port=5173;module='vite'}
    $started | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'assistant_router_v5_dependency_processes.json')
    $started | ConvertTo-Json
} elseif ($Mode -eq 'restart-search') {
    Start-Api 'search.api' 8003 'assistant_router_v5_search_restarted' | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'assistant_router_v5_search_restarted_process.json')
} elseif ($Mode -eq 'experimental-rag') {
    $env:ASSISTANT_ROUTER_MODE='router_v5'
    $env:ASSISTANT_ROUTER_V2_VARIANT=''
    $env:ASSISTANT_ROUTER_V2_RETRY='0'
    $env:ASSISTANT_PROFILE_PATH=Join-Path $reportRoot 'assistant_router_v5_live_profiles.jsonl'
    Start-Api 'rag.api' 8005 'assistant_router_v5_rag' | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'assistant_router_v5_experimental_process.json')
} else {
    $registration=Get-Content -LiteralPath (Join-Path $reportRoot 'assistant_router_v5_experimental_process.json') -Raw | ConvertFrom-Json
    $listener=Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $service=Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
        if ($service.CommandLine -notmatch 'uvicorn rag.api:app' -or $service.ParentProcessId -ne $registration.launcher_pid) {throw 'RAG listener identity mismatch; refusing termination'}
        $workers=Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq $service.ProcessId -and $_.CommandLine -match 'multiprocessing.spawn'}
        foreach ($worker in $workers) {Stop-Process -Id $worker.ProcessId -ErrorAction SilentlyContinue}
        Stop-Process -Id $service.ProcessId -ErrorAction SilentlyContinue
        Stop-Process -Id $registration.launcher_pid -ErrorAction SilentlyContinue
        # Windows may briefly retain a LISTEN row after process termination.
        for ($exitWait=0; $exitWait -lt 15; $exitWait++) {
            if (-not (Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue)) {break}
            Start-Sleep -Milliseconds 100
        }
    }
    $env:ASSISTANT_ROUTER_MODE='existing_qwen'
    $env:ASSISTANT_ROUTER_V2_VARIANT=''
    $env:ASSISTANT_ROUTER_V2_RETRY='0'
    $env:ASSISTANT_PROFILE_PATH=Join-Path $reportRoot 'assistant_router_v5_restored_profiles.jsonl'
    Start-Api 'rag.api' 8005 'assistant_router_v5_restored_rag' | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'assistant_router_v5_restored_process.json')
}
