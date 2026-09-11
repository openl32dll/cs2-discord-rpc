<#
.SYNOPSIS
    Creates a Windows Task Scheduler task that starts the CS2 Discord Rich
    Presence script in the background (no console window) automatically
    whenever you log in.

.NOTES
    - Administrator privileges are NOT required; the task is set up for
      your own user account only, running at logon.
    - The Discord desktop app usually already starts with Windows; the
      script automatically retries every few seconds until it can connect
      to Discord, so you don't need to worry about ordering.

.USAGE
    Open PowerShell as a regular user (no admin needed):
        cd cs2-discord-rpc
        powershell -ExecutionPolicy Bypass -File windows_autostart\install_autostart.ps1

    To remove it:
        powershell -ExecutionPolicy Bypass -File windows_autostart\uninstall_autostart.ps1
#>

$ErrorActionPreference = "Stop"

$TaskName = "CS2DiscordRPC"
$ScriptDir = Split-Path -Parent $PSScriptRoot            # full path to the cs2-discord-rpc folder
$ScriptPath = Join-Path $ScriptDir "cs2_discord_rpc.py"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "cs2_discord_rpc.py not found: $ScriptPath"
    exit 1
}

if (-not (Test-Path (Join-Path $ScriptDir "config.json"))) {
    Write-Warning ("config.json not found. The script won't run without a Discord Client ID.`n" +
        "First copy 'config.example.json' to 'config.json' and put your own " +
        "Client ID in it (see README.md).")
}

# pythonw.exe is preferred so no console window is opened.
$PythonExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $PythonExe) {
    Write-Error "python.exe / pythonw.exe not found. Make sure Python is on your PATH."
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Shows your CS2 map/mode/round status on Discord" | Out-Null

Write-Host "Task created: '$TaskName'."
Write-Host "It will start automatically at your next login."
Write-Host ""
Write-Host "To start it right now:"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
