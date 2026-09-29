param([switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Create backend/.venv and install requirements first. See README.md.' }
if (!(Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\node_modules'))) { throw 'Run npm ci in frontend first.' }
$logDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 } catch { $health = $null }
if (!$health) {
    Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'backend.log') -RedirectStandardError (Join-Path $logDir 'backend-error.log')
} elseif ($health.project -ne 'KinematiX') { throw 'Port 8000 is occupied by another service.' }
try { $page = Invoke-WebRequest 'http://127.0.0.1:5173' -TimeoutSec 2 } catch { $page = $null }
if (!$page) {
    $nodePath = (Get-Command node.exe).Source
    Start-Process -FilePath $nodePath -ArgumentList 'node_modules/vite/bin/vite.js','--host','0.0.0.0','--port','5173','--strictPort' -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'frontend.log') -RedirectStandardError (Join-Path $logDir 'frontend-error.log')
}
Write-Host 'KinematiX: http://127.0.0.1:5173'
Write-Host 'Logs: .runtime/. Close the local server processes when finished.'
if (!$NoOpen) { Start-Process 'http://127.0.0.1:5173' -WindowStyle Hidden }
