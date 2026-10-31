# Bounded read-only metadata; never records command lines or data file contents.
$ErrorActionPreference='Stop'
$root='D:\SDC\LibraryLLM'
$result=@{production_mutations=$false;remote_reachability='NOT_VERIFIED'}
$result.interfaces=@(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object InterfaceAlias,IPAddress,PrefixLength,AddressState)
$result.listeners=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -in @(27017,8002,8003,8004,8005,5173)} | Select-Object LocalAddress,LocalPort,OwningProcess)
$result.processes=@()
foreach($process in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {$_.Name -in @('python.exe','mongod.exe','node.exe','cloudflared.exe','ngrok.exe','ssh.exe')})) {
    $kind=if($process.Name -eq 'mongod.exe'){'MONGO'}elseif($process.CommandLine -match 'uvicorn.+backend.main'){'CORE'}elseif($process.CommandLine -match 'uvicorn.+search.api'){'SEARCH_NATIVE_HOST'}elseif($process.CommandLine -match 'uvicorn.+rag.api'){'RAG'}elseif($process.CommandLine -match 'uvicorn.+recommendation.api'){'RECOMMENDATION'}elseif($process.Name -in @('cloudflared.exe','ngrok.exe','ssh.exe')){'POTENTIAL_TUNNEL_NOT_VERIFIED'}else{'OTHER_OR_TASK_PROCESS'}
    $result.processes+=@{pid=$process.ProcessId;parent_pid=$process.ParentProcessId;name=$process.Name;classification=$kind;command_line_available=($null -ne $process.CommandLine)}
}
try {
    $matched=@(Get-NetFirewallRule -DisplayName '*Mongo*' -ErrorAction Stop | Select-Object Name,Enabled,Direction,Action,Profile -First 20)
    $result.explicit_27017_filters=$matched
    $result.firewall_effective_port_policy='NOT_VERIFIED: Any/program/service/profile/inherited rules and off-host forwarding need operator review.'
} catch {$result.firewall_rule_status='NOT_VERIFIED';$result.firewall_error_type=$_.Exception.GetType().Name}
$paths=@((Join-Path $root '.env'),(Join-Path $root 'scripts'),(Join-Path $root '.local/logs'),(Join-Path $root 'local-data/library-intelligence'),(Join-Path $root 'rag/private_documents'),'C:\Program Files\MongoDB\Server\8.3\data')
$rows=@()
foreach($directory in $paths) {
    $targets=@($directory)
    if(Test-Path -LiteralPath $directory -PathType Container) {$targets+=@(Get-ChildItem -LiteralPath $directory -File -ErrorAction SilentlyContinue | Select-Object -First 3 -ExpandProperty FullName)}
    foreach($path in $targets) {try {$acl=Get-Acl -LiteralPath $path;$rows+=@{path=$path;owner=$acl.Owner;protected=$acl.AreAccessRulesProtected;sddl=$acl.Sddl}} catch {$rows+=@{path=$path;status='NOT_VERIFIED'}}}
}
$result.bounded_child_file_acls=$rows
$result | ConvertTo-Json -Depth 7
