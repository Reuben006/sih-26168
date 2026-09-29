param(
    [string]$SdkPath = "$env:LOCALAPPDATA\Android\Sdk",
    [string]$JavaPath,
    [string]$GradlePath
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (!$JavaPath) {
    $jdk = Get-ChildItem (Join-Path $projectRoot '.runtime\toolchain') -Directory -Filter 'jdk-17*' | Select-Object -First 1
    if (!$jdk) { throw 'Supply -JavaPath pointing to JDK 17.' }
    $JavaPath = $jdk.FullName
}
if (!$GradlePath) { $GradlePath = Join-Path $projectRoot '.runtime\toolchain\gradle-8.5\bin\gradle.bat' }
if (!(Test-Path "$SdkPath\platforms\android-34\android.jar")) { throw 'Install Android SDK Platform 34 in Android Studio SDK Manager.' }
if (!(Test-Path "$JavaPath\bin\java.exe")) { throw 'JDK not found.' }
if (!(Test-Path $GradlePath)) { throw 'Supply -GradlePath pointing to Gradle 8.5 gradle.bat.' }
$env:JAVA_HOME = $JavaPath
$env:ANDROID_HOME = $SdkPath
$env:GRADLE_USER_HOME = Join-Path $projectRoot '.runtime\gradle-cache'
Push-Location (Join-Path $projectRoot 'frontend')
try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } } finally { Pop-Location }
$assets = Join-Path $projectRoot 'android\app\src\main\assets'
# Clean only the verified generated-assets directory to avoid stale JS bundles.
$expectedAssets = [IO.Path]::GetFullPath((Join-Path $projectRoot 'android\app\src\main\assets'))
if ([IO.Path]::GetFullPath($assets) -ne $expectedAssets -or !$expectedAssets.StartsWith($projectRoot + '\')) { throw 'Unsafe asset destination.' }
if (Test-Path -LiteralPath $assets) {
    $assetDirectory = Get-Item -LiteralPath $assets
    if ($assetDirectory.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Asset directory cannot be a symlink or junction.' }
    Remove-Item -LiteralPath $expectedAssets -Recurse -Force
}
New-Item -ItemType Directory -Force $assets | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'frontend\dist\*') -Destination $assets -Recurse -Force
Push-Location (Join-Path $projectRoot 'android')
try { & $GradlePath --no-daemon assembleDebug lintDebug; if ($LASTEXITCODE -ne 0) { throw 'Android build or lint failed.' } } finally { Pop-Location }
$output = Join-Path $projectRoot 'android\app\build\outputs\apk\debug\KinematiX.apk'
Copy-Item (Join-Path $projectRoot 'android\app\build\outputs\apk\debug\app-debug.apk') $output -Force
Write-Output "APK: $output"
Get-FileHash $output -Algorithm SHA256