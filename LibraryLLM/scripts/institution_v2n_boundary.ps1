# Read-only bounded firewall, observed Mongo PID and database directory ACL audit.
$ErrorActionPreference='Stop'
$payload=[Console]::In.ReadToEnd() | ConvertFrom-Json
$result=@{changes_performed=$false;raw_command_lines_recorded=$false;external_exposure='UNKNOWN'}
try {
    $profiles=@(Get-NetFirewallProfile -ErrorAction Stop | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction)
    $result.firewall_profiles=$profiles
    $result.firewall_profile_status=if($profiles.Count -gt 0){'OBSERVED'}else{'NOT_VERIFIED_EMPTY_PROVIDER'}
} catch {$result.firewall_profile_status='NOT_VERIFIED';$result.firewall_error_type=$_.Exception.GetType().Name}
try {
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$payload.mongo_pid)" -ErrorAction Stop
    if($process) {
        $argvStatus=if($null -eq $process.CommandLine){'NOT_VERIFIED_INACCESSIBLE'}elseif([string]$process.CommandLine -match 'mongodb(?:\+srv)?://[^\s]+@|--password|--uri'){'CREDENTIAL_PATTERN_PRESENT'}else{'NO_PATTERN_OBSERVED'}
        $result.mongo_process=@{pid=$process.ProcessId;executable=$process.ExecutablePath;name=$process.Name;owner='NOT_VERIFIED';command_line_credential_scan=$argvStatus}
        try {$owner=Invoke-CimMethod -InputObject $process -MethodName GetOwner -ErrorAction Stop;if($owner.ReturnValue -eq 0){$result.mongo_process.owner=$owner.Domain+'\'+$owner.User}} catch {}
        $result.mongo_services=@(Get-CimInstance Win32_Service -Filter "ProcessId = $([int]$payload.mongo_pid)" -ErrorAction Stop | Select-Object Name,StartName,State,StartMode)
    } else {$result.mongo_process_status='NOT_VERIFIED_EMPTY_PROVIDER'}
} catch {$result.mongo_process_status='NOT_VERIFIED';$result.mongo_process_error_type=$_.Exception.GetType().Name}
if($payload.dbpath) {
    try {$acl=Get-Acl -LiteralPath ([string]$payload.dbpath);$result.database_path_acl=@{path=$payload.dbpath;owner=$acl.Owner;protected=$acl.AreAccessRulesProtected;sddl=$acl.Sddl;access_text=$acl.AccessToString}}
    catch {$result.database_path_acl_status='NOT_VERIFIED';$result.database_path_error_type=$_.Exception.GetType().Name}
} else {$result.database_path_acl_status='NOT_VERIFIED_NO_PATH'}
$result | ConvertTo-Json -Depth 7
