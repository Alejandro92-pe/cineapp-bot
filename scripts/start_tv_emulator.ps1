param([switch]$Headless)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$runtime=Join-Path $projectRoot '.local/tv-emulator'
$env:ANDROID_HOME=Join-Path $runtime 'sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
$env:ANDROID_AVD_HOME=Join-Path $runtime 'avd'
$env:ANDROID_USER_HOME=Join-Path $runtime 'user'
$env:ANDROID_EMULATOR_HOME=$env:ANDROID_USER_HOME
$adb=Join-Path $env:ANDROID_HOME 'platform-tools/adb.exe'
$emulator=Join-Path $env:ANDROID_HOME 'emulator/emulator.exe'
$serial='emulator-5560'
$avd='QueHay_TV_720'
$apk=Join-Path $projectRoot '.local/tv-apk/QueHay-TV-0.1.apk'
if (-not (Test-Path $emulator) -or -not (Test-Path $apk)) { throw 'Faltan el emulador o la APK TV. No se instala nada automaticamente.' }
& (Join-Path $env:ANDROID_HOME 'emulator/emulator-check.exe') accel
if ($LASTEXITCODE -ne 0) { throw 'La aceleracion no esta disponible. Revisarla antes de arrancar; este script nunca reinicia Windows.' }
# Separate PowerShell process: a running LAN service can exit its helper safely.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start_tv_lan.ps1')
if ($LASTEXITCODE -ne 0) { throw 'No pudo iniciarse el servidor local.' }
$devices=(& $adb devices) -join "`n"
if ($devices -notmatch "(?m)^$serial\s") {
    $argsList=@('-avd',$avd,'-port','5560','-accel','on','-gpu','host','-no-snapshot','-no-boot-anim','-netdelay','none','-netspeed','full','-no-metrics')
    if ($Headless) { $argsList+='-no-window' }
    # The emulator itself is the interactive window requested by the user.
    Start-Process -FilePath $emulator -ArgumentList $argsList -WindowStyle $(if($Headless){'Hidden'}else{'Normal'}) -RedirectStandardOutput (Join-Path $runtime 'emulator.out') -RedirectStandardError (Join-Path $runtime 'emulator.err') | Out-Null
}
Write-Output 'Esperando a Android TV; el primer arranque puede tardar unos minutos...'
$ready=$false
for($attempt=0;$attempt -lt 120;$attempt++) {
    # Offline is normal during boot; native stderr must not terminate PowerShell 5.
    $ErrorActionPreference='Continue'
    $boot=(& $adb -s $serial shell getprop sys.boot_completed 2>$null) -join ''
    $ErrorActionPreference='Stop'
    if ($boot.Trim() -eq '1') { $ready=$true;break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'Android TV no termino de arrancar. Revisar .local/tv-emulator/emulator.err; no se han borrado datos.' }
$name=(& $adb -s $serial emu avd name 2>$null) -join "`n"
if ($name -notmatch $avd) { throw 'El puerto 5560 pertenece a otro emulador. No se instala la APK en ese dispositivo.' }
& $adb -s $serial install -r $apk
if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar la APK TV.' }
& $adb -s $serial shell am start -n live.quehay.tv.preview/live.quehay.tv.MainActivity
if ($LASTEXITCODE -ne 0) { throw 'No se pudo abrir Que Hay TV.' }
Write-Output 'Listo. Flechas y Enter para navegar. Usa el control Back de la barra del emulador para volver.'
Write-Output 'Vinculacion desde el celular: http://192.168.100.3:5021/tv/vincular'
