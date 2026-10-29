param(
    [string]$Origin = 'http://192.168.100.3:5021',
    [string]$ToolRoot = 'C:\Users\richa\Mis Proyectos\cineapp-render\.local\android-tools'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:JAVA_HOME = (Get-ChildItem (Join-Path $ToolRoot 'jdk') -Directory | Select-Object -First 1).FullName
$env:ANDROID_HOME = Join-Path $ToolRoot 'sdk-home'
$env:GRADLE_USER_HOME = Join-Path $ToolRoot 'gradle-cache'
& (Join-Path $projectRoot 'android-tv/gradlew.bat') -p (Join-Path $projectRoot 'android-tv') "-PtvOrigin=$Origin" :app:assembleDebug :app:lintDebug --no-daemon --console=plain
if ($LASTEXITCODE -ne 0) { throw 'La compilación o revisión de Android TV no pasó.' }
$output = Join-Path $projectRoot '.local/tv-apk'
New-Item -ItemType Directory -Force $output | Out-Null
$apk = Join-Path $output 'QueHay-TV-0.1.apk'
Copy-Item -LiteralPath (Join-Path $projectRoot 'android-tv/app/build/outputs/apk/debug/app-debug.apk') -Destination $apk
& (Join-Path $env:ANDROID_HOME 'build-tools/35.0.0/apksigner.bat') verify --verbose $apk
if ($LASTEXITCODE -ne 0) { throw 'La firma del APK TV no pudo verificarse.' }
Get-FileHash -Algorithm SHA256 $apk
