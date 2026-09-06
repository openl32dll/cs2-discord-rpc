<#
.SYNOPSIS
    CS2 Discord Rich Presence script'ini Windows'ta oturum açtığın anda
    arka planda (konsol penceresi açmadan) otomatik başlatan bir Görev
    Zamanlayıcı (Task Scheduler) görevi oluşturur.

.NOTES
    - Yönetici (Administrator) yetkisi GEREKMEZ; görev sadece senin
      kullanıcı hesabın için, oturum açılışında çalışacak şekilde kurulur.
    - Discord masaüstü uygulaması genelde zaten Windows ile birlikte
      açılır; script Discord'a bağlanana kadar birkaç saniyede bir
      otomatik dener, o yüzden sıralama konusunda endişelenmene gerek yok.

.USAGE
    PowerShell'i normal kullanıcı olarak aç (admin gerekmez):
        cd cs2-discord-rpc
        powershell -ExecutionPolicy Bypass -File windows_autostart\install_autostart.ps1

    Kaldırmak için:
        powershell -ExecutionPolicy Bypass -File windows_autostart\uninstall_autostart.ps1
#>

$ErrorActionPreference = "Stop"

$TaskName = "CS2DiscordRPC"
$ScriptDir = Split-Path -Parent $PSScriptRoot            # cs2-discord-rpc klasörünün tam yolu
$ScriptPath = Join-Path $ScriptDir "cs2_discord_rpc.py"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "cs2_discord_rpc.py bulunamadi: $ScriptPath"
    exit 1
}

if (-not (Test-Path (Join-Path $ScriptDir "config.json"))) {
    Write-Warning ("config.json bulunamadi. Discord Client ID'ni ayarlamadan script calismaz.`n" +
        "Once 'config.example.json' dosyasini 'config.json' olarak kopyala ve icine kendi " +
        "Client ID'ni yaz (README.md).")
}

# Konsol penceresi acmadan calistirmak icin pythonw.exe tercih edilir.
$PythonExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $PythonExe) {
    Write-Error "python.exe / pythonw.exe bulunamadi. Python'un PATH'e ekli oldugundan emin ol."
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
    -Description "CS2 oynarken Discord'da harita/mod/round durumunu gosterir" | Out-Null

Write-Host "Gorev olusturuldu: '$TaskName'."
Write-Host "Bir sonraki oturum acisinda otomatik baslayacak."
Write-Host ""
Write-Host "Hemen simdi baslatmak icin:"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
