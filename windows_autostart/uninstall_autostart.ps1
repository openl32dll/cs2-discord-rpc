<#
.SYNOPSIS
    install_autostart.ps1 ile olusturulan "CS2DiscordRPC" gorevini
    Windows Görev Zamanlayıcı'dan kaldırır.

.USAGE
    powershell -ExecutionPolicy Bypass -File windows_autostart\uninstall_autostart.ps1
#>

$ErrorActionPreference = "Stop"

$TaskName = "CS2DiscordRPC"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "'$TaskName' gorevi kaldirildi."
} else {
    Write-Host "'$TaskName' adinda bir gorev bulunamadi (zaten kurulu degil)."
}
