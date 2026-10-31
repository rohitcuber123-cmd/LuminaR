# A restricted token in an owned directory; no account/service/production ACL change.
param([string]$Path)
$ErrorActionPreference='Stop'
$resolved=[IO.Path]::GetFullPath($Path)
if($resolved -notlike ([IO.Path]::GetTempPath().TrimEnd('\')+'\luminar-v2o-auth-*\*')) {throw 'OWNED_SCOPE_REQUIRED'}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class LuminarRestrictedProbe {
 [StructLayout(LayoutKind.Sequential)] public struct SidAndAttributes { public IntPtr Sid; public uint Attributes; }
 [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFile(string p,uint access,uint share,IntPtr sa,uint disposition,uint flags,IntPtr template);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr p,uint rights,out IntPtr token);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool CreateRestrictedToken(IntPtr token,uint flags,uint dc,IntPtr disable,uint pc,IntPtr privileges,uint sc,ref SidAndAttributes sids,out IntPtr restricted);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool ConvertStringSidToSid(string s,out IntPtr sid);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool ImpersonateLoggedOnUser(IntPtr token);
 [DllImport("advapi32.dll")] static extern bool RevertToSelf();
 [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr p);
 public static int ReadAttempt(string path) {
  IntPtr token=IntPtr.Zero, restricted=IntPtr.Zero, sid=IntPtr.Zero;
  try {
   if(!OpenProcessToken(GetCurrentProcess(),0x0002|0x0008|0x0004,out token))return -10;
   if(!ConvertStringSidToSid("S-1-5-32-545",out sid))return -11;
   var entry=new SidAndAttributes { Sid=sid, Attributes=0 };
   if(!CreateRestrictedToken(token,1,0,IntPtr.Zero,0,IntPtr.Zero,1,ref entry,out restricted))return -12;
   if(!ImpersonateLoggedOnUser(restricted))return -13;
   try {
    var handle=CreateFile(path,0x80000000,1,IntPtr.Zero,3,0,IntPtr.Zero);
    if(handle==new IntPtr(-1))return Marshal.GetLastWin32Error();
    CloseHandle(handle);return 0;
   } finally {RevertToSelf();}
  } finally {if(token!=IntPtr.Zero)CloseHandle(token);if(restricted!=IntPtr.Zero)CloseHandle(restricted);if(sid!=IntPtr.Zero)LocalFree(sid);}
 }
}
'@
$ownerRead=$false
$stream=[IO.File]::OpenRead($resolved);try {$ownerRead=$stream.Length -gt 0} finally {$stream.Dispose()}
$code=[LuminarRestrictedProbe]::ReadAttempt($resolved)
@{owner_read_allowed=$ownerRead;restricted_token_read_error=$code;restricted_token_denied=($code -eq 5);actual_other_service_account_tested=$false;production_acl_changed=$false} | ConvertTo-Json -Compress
