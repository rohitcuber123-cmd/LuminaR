# Read-only bounded listener/process and ACL audit. Never emits raw command lines.
$ErrorActionPreference='Stop'
$auditRoot='D:\SDC\LibraryLLM'
$auditPorts=@(8000,8002,8003,8004,8005,5173,27017)
$listeners=@()
$connectionRows=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -in $auditPorts})
foreach($auditPort in $auditPorts) {
    foreach($connection in @($connectionRows | Where-Object {$_.LocalPort -eq $auditPort})) {
        $process=Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
        $role='UNKNOWN_LISTENER'
        if($process.CommandLine -match 'uvicorn\s+backend\.main:app') {$role='CORE_API'}
        elseif($process.CommandLine -match 'uvicorn\s+search\.api:app') {$role='SEARCH_API_HOSTS_TENANT_WORKER'}
        elseif($process.CommandLine -match 'uvicorn\s+rag\.api:app') {$role='RAG_QWEN'}
        elseif($process.CommandLine -match 'uvicorn\s+recommendation\.api:app') {$role='RECOMMENDATION'}
        elseif($process.Name -eq 'mongod.exe') {$role='MONGODB'}
        elseif($process.CommandLine -match 'vite') {$role='FRONTEND_VITE'}
        $ownerName='NOT_AVAILABLE'
        try {$account=Invoke-CimMethod -InputObject $process -MethodName GetOwner -ErrorAction Stop;if($account.ReturnValue -eq 0){$ownerName=$account.Domain+'\'+$account.User}} catch {}
        $serviceRows=@(Get-CimInstance Win32_Service -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue | ForEach-Object {@{name=$_.Name;account=$_.StartName;state=$_.State;start_mode=$_.StartMode}})
        $listeners+=@{port=$auditPort;address=$connection.LocalAddress;pid=$connection.OwningProcess;parent_pid=$process.ParentProcessId;services=$serviceRows;
            executable=$process.ExecutablePath;name=$process.Name;started_at=$process.CreationDate;role=$role;owner=$ownerName;
            evidence='Bounded listener PID/module/owner observation only; no tenant-worker UUID/supervisor attestation.'}
    }
}
$aclRows=@()
foreach($relative in @('.env','frontend/.env','frontend/.env.local','scripts/start_local.py','.local/logs','local-data/library-intelligence','rag/private_documents')) {
    $target=Join-Path $auditRoot $relative
    if(Test-Path -LiteralPath $target) {
        try {
            $acl=Get-Acl -LiteralPath $target
            $aclRows+=@{path=$relative;exists=$true;owner=$acl.Owner;protected=$acl.AreAccessRulesProtected;sddl=$acl.Sddl;access_text=$acl.AccessToString}
        } catch {$aclRows+=@{path=$relative;exists=$true;status='ACL_NOT_AVAILABLE';error_type=$_.Exception.GetType().Name;error_code=$_.FullyQualifiedErrorId}}
    } else {$aclRows+=@{path=$relative;exists=$false}}
}
@{captured_at=[DateTime]::UtcNow.ToString('o');current_identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;
    listeners=$listeners;filesystem_acls=$aclRows;raw_command_lines_recorded=$false;process_control_performed=$false;acl_changes_performed=$false} | ConvertTo-Json -Depth 8
