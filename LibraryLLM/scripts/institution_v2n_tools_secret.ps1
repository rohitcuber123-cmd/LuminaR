# Restrict only a newly owned disposable directory before writing tool config.
# Config plaintext contains synthetic credentials only; never a production secret.
$ErrorActionPreference='Stop'
try {
    $payload=[Console]::In.ReadToEnd() | ConvertFrom-Json
    $scope=[IO.Path]::GetFullPath([string]$payload.fixture_root)
    $tempRoot=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    if(([IO.Directory]::GetParent($scope).FullName -ne $tempRoot) -or ([IO.Path]::GetFileName($scope) -notlike 'luminar-v2n-auth-*')) {throw 'FIXTURE_SCOPE_REQUIRED'}
    $target=Join-Path $scope 'tools-secret'
    if(Test-Path -LiteralPath $target) {throw 'NEW_DIRECTORY_REQUIRED'}
    [void][IO.Directory]::CreateDirectory($target)
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $systemSid=New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false);$acl.SetOwner($identity.User)
    foreach($sid in @($identity.User,$systemSid)) {
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
    }
    Set-Acl -LiteralPath $target -AclObject $acl
    $path=Join-Path $target 'mongo-tools.yml'
    [IO.File]::WriteAllText($path, 'uri: '+([string]$payload.uri | ConvertTo-Json -Compress))
    $actual=Get-Acl -LiteralPath $path
    @{directory_protected=(Get-Acl -LiteralPath $target).AreAccessRulesProtected;file_sddl=$actual.Sddl;current_sid=$identity.User.Value;secret_returned=$false} | ConvertTo-Json -Compress
} catch {
    [Console]::Error.WriteLine('OWNED_TOOL_CONFIG_FAILED')
    exit 3
}
