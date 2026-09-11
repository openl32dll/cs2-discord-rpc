<#
.SYNOPSIS
    Removes the "CS2DiscordRPC" task created by install_autostart.ps1 from
    Windows Task Scheduler.

.USAGE
    powershell -ExecutionPolicy Bypass -File windows_autostart\uninstall_autostart.ps1
#>

$ErrorActionPreference = "Stop"

$TaskName = "CS2DiscordRPC"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task '$TaskName' removed."
} else {
    Write-Host "No task named '$TaskName' was found (not installed)."
}
