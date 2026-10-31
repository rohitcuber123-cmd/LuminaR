# Disposable-only DPAPI/NTFS qualification. Secrets arrive through stdin, never argv.
param([ValidateSet('protect','verify','native','operator')][string]$Mode)
$ErrorActionPreference='Stop'
$fixtureStage='SCOPE_CHECK'
try {
    $payload=[Console]::In.ReadToEnd() | ConvertFrom-Json
    $scope=[IO.Path]::GetFullPath([string]$payload.fixture_root)
    $tempRoot=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    if(([IO.Directory]::GetParent($scope).FullName -ne $tempRoot) -or ([IO.Path]::GetFileName($scope) -notlike 'luminar-v2m-auth-*')) {throw 'FIXTURE_SCOPE_REQUIRED'}
    $secretPath=[IO.Path]::GetFullPath([string]$payload.secret_path)
    if(-not $secretPath.StartsWith($scope+'\',[StringComparison]::OrdinalIgnoreCase)) {throw 'FIXTURE_SECRET_PATH_REQUIRED'}
    $secretDir=[IO.Path]::GetDirectoryName($secretPath)
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $systemSid=New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    if($Mode -eq 'protect') {
        if(Test-Path -LiteralPath $secretPath) {throw 'FIXTURE_SECRET_ALREADY_EXISTS'}
        [void][IO.Directory]::CreateDirectory($secretDir)
        $dirAcl=New-Object Security.AccessControl.DirectorySecurity
        $dirAcl.SetAccessRuleProtection($true,$false);$dirAcl.SetOwner($identity.User)
        foreach($sid in @($identity.User,$systemSid)) {
            $rule=New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
            $dirAcl.AddAccessRule($rule)
        }
        $fixtureStage='DIRECTORY_ACL';Set-Acl -LiteralPath $secretDir -AclObject $dirAcl
        $secure=ConvertTo-SecureString -String ([string]$payload.secret) -AsPlainText -Force
        $fixtureStage='DPAPI_EXPORT';$secure | Export-Clixml -LiteralPath $secretPath
        $fileAcl=New-Object Security.AccessControl.FileSecurity
        $fileAcl.SetAccessRuleProtection($true,$false);$fileAcl.SetOwner($identity.User)
        foreach($sid in @($identity.User,$systemSid)) {$fileAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','Allow')))}
        $fixtureStage='FILE_ACL';Set-Acl -LiteralPath $secretPath -AclObject $fileAcl
    }
    $fixtureStage='DPAPI_IMPORT';$stored=Import-Clixml -LiteralPath $secretPath
    if($stored -isnot [Security.SecureString]) {throw 'DPAPI_SECURESTRING_REQUIRED'}
    $plain=(New-Object Net.NetworkCredential('',$stored)).Password
    if($Mode -in @('protect','verify')) {
        $fileAcl=Get-Acl -LiteralPath $secretPath;$dirAcl=Get-Acl -LiteralPath $secretDir
        @{mode=$Mode;recovered_matches=($plain -ceq [string]$payload.secret);file_protected=$fileAcl.AreAccessRulesProtected;
            directory_protected=$dirAcl.AreAccessRulesProtected;file_sddl=$fileAcl.Sddl;directory_sddl=$dirAcl.Sddl;
            current_sid=$identity.User.Value;encryption='Windows SecureString Export-Clixml DPAPI';secret_value_returned=$false} | ConvertTo-Json -Compress
    } else {
        if($payload.database -notlike 'luminar_v2m_fixture_*') {throw 'FIXTURE_DATABASE_REQUIRED'}
        if($Mode -eq 'native') {
            $env:V2M_TELEMETRY_URI=$plain
            $env:LUMINAR_WORKER_TELEMETRY_MONGO_URI=$plain
            $env:LUMINAR_V2M_ISOLATED_CHILD='1'
            $argsList=@($payload.script,'--scenario',$payload.scenario,'--output',$payload.output)
            if($payload.enabled -eq $true){$argsList+='--enabled'}
            if($payload.repetitions){$env:LUMINAR_V2M_BENCH_REPETITIONS=[string]$payload.repetitions}
            & $payload.python @argsList
        } else {
            $env:LUMINAR_OPERATOR_MONGO_URI=$plain
            $argsList=@($payload.script,'--database',$payload.database,'--library-id',$payload.library_id,'--format',$payload.format)
            if($payload.artifact_root){$argsList+=@('--artifact-root',$payload.artifact_root)}
            & $payload.python @argsList
        }
        $childExit=$LASTEXITCODE
        Remove-Item Env:\V2M_TELEMETRY_URI,Env:\LUMINAR_WORKER_TELEMETRY_MONGO_URI,Env:\LUMINAR_OPERATOR_MONGO_URI -ErrorAction SilentlyContinue
        exit $childExit
    }
    $plain=$null;$secure=$null;$stored=$null
} catch {
    # Never serialize the exception, input payload, URI or secret.
    [Console]::Error.WriteLine((@{error='DISPOSABLE_SECRET_FIXTURE_UNAVAILABLE';stage=$fixtureStage;type=$_.Exception.GetType().Name} | ConvertTo-Json -Compress))
    exit 3
}
