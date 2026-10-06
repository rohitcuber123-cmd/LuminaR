$ErrorActionPreference='Stop'
$eventsProject='D:\SDC\LibraryLLM'
$eventsPython=Join-Path $eventsProject '.venv\Scripts\python.exe'
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
$env:ASSISTANT_ROUTER_V2_VARIANT=''
$env:ASSISTANT_ROUTER_V2_RETRY='0'
$env:ASSISTANT_PROFILE_PATH=Join-Path $eventsProject 'reports\events_assistant_profiles.jsonl'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONUTF8='1'
foreach ($eventsService in @(@{port=8003;module='search.api'},@{port=8004;module='recommendation.api'},@{port=8005;module='rag.api'})) {
    if (Get-NetTCPConnection -State Listen -LocalPort $eventsService.port -ErrorAction SilentlyContinue) {
        Write-Output "Existing $($eventsService.module) listener retained."
        continue
    }
    $eventsArgs=@('-m','uvicorn',"$($eventsService.module):app",'--host','127.0.0.1','--port',"$($eventsService.port)")
    $eventsLaunch=Start-Process -FilePath $eventsPython -ArgumentList $eventsArgs -WorkingDirectory $eventsProject -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $eventsProject "reports\events_$($eventsService.port).out.log") -RedirectStandardError (Join-Path $eventsProject "reports\events_$($eventsService.port).err.log")
    Write-Output "Started existing $($eventsService.module) launcher $($eventsLaunch.Id)."
}
