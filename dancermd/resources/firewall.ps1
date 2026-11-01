# Allows phones to reach DanceRMD through Windows Firewall.
# Run: right-click > "Run with PowerShell" (the script asks for administrator rights itself).
param([int]$Port = 8765)

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Port $Port"
    exit
}

# Clicking "Cancel" on the first-run firewall prompt makes Windows add BLOCK rules for the program.
# Block rules always win over allow rules, so remove them (python.exe when running from source,
# DanceRMD.exe, and RemoteLaptop.exe from version 1.x).
$blocked = Get-NetFirewallRule -Direction Inbound -Action Block -ErrorAction SilentlyContinue |
    Where-Object { ($_ | Get-NetFirewallApplicationFilter).Program -match 'python|DanceRMD|RemoteLaptop' }
if ($blocked) {
    $blocked | Remove-NetFirewallRule
    Write-Host "Removed $(@($blocked).Count) blocking rule(s)"
}

Remove-NetFirewallRule -DisplayName 'Remote Laptop' -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName 'DanceRMD' -ErrorAction SilentlyContinue
# Allow both Private and Public profiles: Windows often classifies a newly joined Wi-Fi as Public.
# Every connection still needs the access code, so other people on the network can't take control.
New-NetFirewallRule -DisplayName 'DanceRMD' -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort $Port -Profile Private, Public | Out-Null
Write-Host "TCP port $Port is now open for DanceRMD." -ForegroundColor Green
Read-Host 'Press Enter to close'
