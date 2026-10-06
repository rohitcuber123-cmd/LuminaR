# Hidden normal-stack launcher. WMI invocation keeps it independent of the
# terminal execution lifetime; this starts only the five existing services.
$ErrorActionPreference='Stop'
$eventsProject='D:\SDC\LibraryLLM'
$eventsPython=Join-Path $eventsProject '.venv\Scripts\python.exe'
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
$env:ASSISTANT_ROUTER_V2_VARIANT=''
$env:ASSISTANT_ROUTER_V2_RETRY='0'
$env:ASSISTANT_PROFILE_PATH=Join-Path $eventsProject 'reports\events_v1_1_assistant_profiles.jsonl'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONUTF8='1'
foreach ($eventsService in @(@{port=8002;module='backend.main'},@{port=8003;module='search.api'},@{port=8004;module='recommendation.api'},@{port=8005;module='rag.api'})) {
    if (Get-NetTCPConnection -State Listen -LocalPort $eventsService.port -ErrorAction SilentlyContinue) {continue}
    Start-Process -FilePath $eventsPython -ArgumentList @('-m','uvicorn',"$($eventsService.module):app",'--host','127.0.0.1','--port',"$($eventsService.port)") -WorkingDirectory $eventsProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $eventsProject "reports\events_v1_1_restored_$($eventsService.port).out.log") -RedirectStandardError (Join-Path $eventsProject "reports\events_v1_1_restored_$($eventsService.port).err.log")
}
if (-not (Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath 'C:\Program Files\nodejs\node.exe' -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort' -WorkingDirectory (Join-Path $eventsProject 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $eventsProject 'reports\events_v1_1_restored_vite.out.log') -RedirectStandardError (Join-Path $eventsProject 'reports\events_v1_1_restored_vite.err.log')
}
