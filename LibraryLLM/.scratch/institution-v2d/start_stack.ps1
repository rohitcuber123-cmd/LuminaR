$ErrorActionPreference='Stop'
$v2dProject='D:\SDC\LibraryLLM'
$v2dPython=Join-Path $v2dProject '.venv\Scripts\python.exe'
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
$env:ASSISTANT_ROUTER_V2_VARIANT=''
$env:ASSISTANT_ROUTER_V2_RETRY='0'
$env:ASSISTANT_PROFILE_PATH=Join-Path $v2dProject '.scratch\institution-v2d\assistant_profiles.jsonl'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONUTF8='1'
foreach ($v2dService in @(@{port=8002;name='core';module='backend.main'},@{port=8003;name='search';module='search.api'},@{port=8004;name='recommendation';module='recommendation.api'},@{port=8005;name='rag';module='rag.api'})) {
  if (Get-NetTCPConnection -State Listen -LocalPort $v2dService.port -ErrorAction SilentlyContinue) {continue}
  Start-Process -FilePath $v2dPython -ArgumentList @('-m','uvicorn',"$($v2dService.module):app",'--host','127.0.0.1','--port',"$($v2dService.port)") -WorkingDirectory $v2dProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $v2dProject ".scratch\institution-v2d\$($v2dService.name).out.log") -RedirectStandardError (Join-Path $v2dProject ".scratch\institution-v2d\$($v2dService.name).err.log")
}
if (-not (Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath 'C:\Program Files\nodejs\node.exe' -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $v2dProject 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $v2dProject '.scratch\institution-v2d\vite.out.log') -RedirectStandardError (Join-Path $v2dProject '.scratch\institution-v2d\vite.err.log')
}
