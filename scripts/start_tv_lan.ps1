param([string]$LanHost='192.168.100.3',[int]$Port=5021)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$python='C:\Users\richa\Mis Proyectos\cineapp-render\.venv\Scripts\python.exe'
$snapshotRoot='C:\Users\richa\Mis Proyectos\cineapp-render\.local'
if (-not (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq $LanHost)) {
    throw "Esta PC ya no tiene la IP $LanHost. Hay que recompilar la APK de prueba con su nueva IP."
}
$listener=Get-NetTCPConnection -State Listen -LocalAddress $LanHost -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    $response=Invoke-WebRequest -Uri "http://${LanHost}:$Port/tv/api/me" -UseBasicParsing
    if ($response.StatusCode -ne 200) { throw 'El puerto está ocupado; no se detiene ningún proceso automáticamente.' }
    Write-Output "El servidor ya está disponible: http://${LanHost}:$Port/tv"
    exit
}
$output=Join-Path $projectRoot '.local/tv'
New-Item -ItemType Directory -Force $output | Out-Null
$process=Start-Process -FilePath $python -ArgumentList @('-m','tv.preview','--snapshot-root',('"'+$snapshotRoot+'"'),'--lan-host',$LanHost,'--port',$Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $output 'lan-server.out') -RedirectStandardError (Join-Path $output 'lan-server.err') -PassThru
Write-Output "Servidor iniciado (PID $($process.Id)): http://${LanHost}:$Port/tv"
