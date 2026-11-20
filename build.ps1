param([string]$PythonExe = '', [switch]$SkipDependencyInstall)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonExe) {
    if (-not (Test-Path -LiteralPath '.build-env/Scripts/python.exe')) {
        & python -m venv .build-env
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 x64 first.' }
    }
    $PythonExe = Join-Path $PSScriptRoot '.build-env/Scripts/python.exe'
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
& $PythonExe -c 'import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize("P") == 8, "Python 3.12 x64 required"'
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python version/architecture.' }
if (-not $SkipDependencyInstall) {
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$env:QT_QPA_PLATFORM = 'offscreen'
& $PythonExe ci/generate_brand.py
if ($LASTEXITCODE -ne 0) { throw 'BFT artwork generation failed.' }
& $PythonExe app.py --release-self-test dist/reports/source-tests.json
if ($LASTEXITCODE -ne 0) { throw 'Source acceptance tests failed.' }
& $PythonExe -m PyInstaller --noconfirm --clean --onedir --windowed --name DopeWars-BFT --icon bft.ico --version-file version_info.txt --add-data 'logo.png;.' app.py
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
foreach ($bftCheck in @('release-self-test', 'self-test')) {
    $bftReport = Join-Path $PSScriptRoot ('dist/reports/packaged-' + $bftCheck + '.json')
    $bftExe = Join-Path $PSScriptRoot 'dist/DopeWars-BFT/DopeWars-BFT.exe'
    $bftProcess = Start-Process -FilePath $bftExe -ArgumentList @('--' + $bftCheck, ('"' + $bftReport + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($bftProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $bftReport)) { throw "Packaged $bftCheck failed." }
    $bftResult = Get-Content -LiteralPath $bftReport -Raw | ConvertFrom-Json
    if (-not $bftResult.passed) { throw "Packaged $bftCheck did not pass." }
}
& $PythonExe ci/package_portable.py stage
if ($LASTEXITCODE -ne 0) { throw 'Distribution staging failed.' }
& $PythonExe ci/package_portable.py archive --input dist/DopeWars-BFT --label unsigned
if ($LASTEXITCODE -ne 0) { throw 'Unsigned preview packaging failed.' }
Write-Host 'Unsigned candidate built and tested. Public signing requires SignPath approval.'
