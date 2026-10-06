param([switch]$Restart)
$ErrorActionPreference='Stop'
$projectRoot='D:\SDC\LibraryLLM'
$pythonExe=Join-Path $projectRoot '.venv\Scripts\python.exe'
$listener=Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    if (-not $Restart) {throw 'Core already running; refusing duplicate service'}
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    $parent=Get-CimInstance Win32_Process -Filter "ProcessId = $($process.ParentProcessId)"
    if ($process.CommandLine -notmatch 'uvicorn backend.main:app' -or $parent.CommandLine -notlike "*$pythonExe*") {throw 'Core process identity mismatch'}
    Stop-Process -Id $process.ProcessId
    Stop-Process -Id $parent.ProcessId -ErrorAction SilentlyContinue
    for ($attempt=0;$attempt -lt 50;$attempt++) {if (-not (Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue)) {break};Start-Sleep -Milliseconds 100}
}
if (Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue) {throw 'Core port still occupied'}
$env:PYTHONUTF8='1'
$process=Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8002') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'reports\events_core.out.log') -RedirectStandardError (Join-Path $projectRoot 'reports\events_core.err.log')
@{launcher_pid=$process.Id;port=8002;module='backend.main'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'reports\events_core_process.json')
Write-Output "Core Events started $($process.Id)"
