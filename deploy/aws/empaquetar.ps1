# Arma el paquete de despliegue de CIMA en el computador (Windows, PowerShell 5+).
#
#   powershell -ExecutionPolicy Bypass -File deploy\aws\empaquetar.ps1
#
# Deja cima-despliegue.zip en el Escritorio, listo para subirlo a AWS CloudShell
# (Actions > Upload file). Contiene:
#   app/      la PWA compilada (ng build)
#   backend/  el codigo del backend y su Dockerfile (sin .env, entornos ni pruebas)
#   media/    los videos propios de backend/media (solo nombres validos)
#   deploy/   docker-compose, actualizar.sh y los scripts de CloudShell
#
# Nunca incluye secretos: los .env no se copian.
$ErrorActionPreference = 'Stop'

$raiz = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$trabajo = Join-Path $env:TEMP 'cima-paquete'
$compilado = Join-Path $env:TEMP 'cima-ngbuild'
$destino = Join-Path ([Environment]::GetFolderPath('Desktop')) 'cima-despliegue.zip'

if (Test-Path $trabajo) { Remove-Item $trabajo -Recurse -Force }
if (Test-Path $compilado) { Remove-Item $compilado -Recurse -Force }
New-Item -ItemType Directory -Path $trabajo | Out-Null

# 1. PWA (en una carpeta temporal para no interrumpir el ng serve local).
Write-Host '1/4 Compilando la PWA...'
Push-Location (Join-Path $raiz 'frontend')
try {
  & npx ng build --output-path $compilado
  if ($LASTEXITCODE -ne 0) { throw 'ng build fallo.' }
} finally { Pop-Location }
Copy-Item (Join-Path $compilado 'browser') (Join-Path $trabajo 'app') -Recurse

# 2. Backend: solo lo que necesita la imagen.
Write-Host '2/4 Copiando el backend...'
$back = Join-Path $raiz 'backend'
$backDestino = Join-Path $trabajo 'backend'
New-Item -ItemType Directory -Path $backDestino | Out-Null
foreach ($f in 'Dockerfile', '.dockerignore', 'pyproject.toml', 'alembic.ini') {
  Copy-Item (Join-Path $back $f) $backDestino
}
foreach ($d in 'app', 'alembic') {
  Copy-Item (Join-Path $back $d) (Join-Path $backDestino $d) -Recurse
}
Get-ChildItem $backDestino -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

# 3. Videos propios (misma allowlist de nombres que el backend).
Write-Host '3/4 Copiando los videos...'
$media = Join-Path $trabajo 'media'
New-Item -ItemType Directory -Path $media | Out-Null
Get-ChildItem (Join-Path $back 'media') -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -cmatch '^[a-z0-9][a-z0-9-]{0,62}\.mp4$' } |
  ForEach-Object { Copy-Item $_.FullName $media; Write-Host "    $($_.Name)" }

# 4. Scripts de despliegue, con saltos de linea de Linux (LF).
Write-Host '4/4 Copiando los scripts...'
$dep = Join-Path $trabajo 'deploy'
New-Item -ItemType Directory -Path $dep | Out-Null
Get-ChildItem $PSScriptRoot -File | Where-Object { $_.Extension -ne '.ps1' } |
  ForEach-Object { Copy-Item $_.FullName $dep }
$utf8 = New-Object System.Text.UTF8Encoding($false)
Get-ChildItem $trabajo -Recurse -File |
  Where-Object { $_.Name -eq 'Dockerfile' -or $_.Extension -in '.sh', '.py', '.js', '.yml', '.ini', '.toml' } |
  ForEach-Object {
    $texto = [IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n"
    [IO.File]::WriteAllText($_.FullName, $texto, $utf8)
  }

# Zip con rutas de Linux (tar.exe de Windows; Compress-Archive de PowerShell 5
# guarda las rutas con "\" y Linux no las entiende).
if (Test-Path $destino) { Remove-Item $destino -Force }
& tar.exe -a -c -f $destino -C $trabajo app backend media deploy
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el zip.' }
Remove-Item $trabajo -Recurse -Force
Remove-Item $compilado -Recurse -Force

$mb = [math]::Round((Get-Item $destino).Length / 1MB, 1)
Write-Host ''
Write-Host "Listo: $destino ($mb MB)"
Write-Host 'Subalo a CloudShell con Actions > Upload file.'
