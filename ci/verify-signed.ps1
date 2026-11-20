param(
    [Parameter(Mandatory)][string]$UnsignedDirectory,
    [Parameter(Mandatory)][string]$SignedDirectory,
    [string]$ReportPath = 'dist/reports/signature-verification.json'
)
$ErrorActionPreference = 'Stop'
$bftOriginal = (Resolve-Path -LiteralPath $UnsignedDirectory).Path.TrimEnd('\')
$bftSigned = (Resolve-Path -LiteralPath $SignedDirectory).Path.TrimEnd('\')
if ($bftOriginal -eq $bftSigned) { throw 'Input and signed output must be separate directories.' }
$bftOriginalFiles = @(Get-ChildItem -LiteralPath $bftOriginal -File -Recurse)
$bftSignedFiles = @(Get-ChildItem -LiteralPath $bftSigned -File -Recurse)
if ($bftOriginalFiles.Count -ne $bftSignedFiles.Count) { throw 'Signed output file count changed.' }
if (Get-ChildItem -LiteralPath $bftSigned -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
    throw 'Unexpected reparse point in signed output.'
}
foreach ($bftFile in $bftOriginalFiles) {
    $bftRelative = $bftFile.FullName.Substring($bftOriginal.Length + 1)
    $bftTarget = Join-Path $bftSigned $bftRelative
    if (-not (Test-Path -LiteralPath $bftTarget -PathType Leaf)) { throw "Signed output is missing $bftRelative" }
    if ($bftRelative -ne 'DopeWars-BFT.exe') {
        if ((Get-FileHash -LiteralPath $bftFile.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $bftTarget -Algorithm SHA256).Hash) {
            throw "SignPath modified a file outside the permitted executable: $bftRelative"
        }
    }
}
$bftExe = Join-Path $bftSigned 'DopeWars-BFT.exe'
$bftSignature = Get-AuthenticodeSignature -LiteralPath $bftExe
if ($bftSignature.Status -ne 'Valid') { throw "Public Authenticode validation failed: $($bftSignature.Status)" }
if ($bftSignature.SignerCertificate.Subject -notmatch '(^|,\s*)CN=SignPath Foundation(,|$)') {
    throw 'Unexpected signer: expected SignPath Foundation.'
}
if (-not $bftSignature.TimeStamperCertificate) { throw 'Missing trusted signing timestamp.' }
$bftBefore = (Get-Item -LiteralPath (Join-Path $bftOriginal 'DopeWars-BFT.exe')).VersionInfo
$bftAfter = (Get-Item -LiteralPath $bftExe).VersionInfo
foreach ($bftProperty in @('ProductName','ProductVersion','FileVersion','OriginalFilename')) {
    if ($bftBefore.$bftProperty -ne $bftAfter.$bftProperty) { throw "Signed executable metadata changed: $bftProperty" }
}
$bftReport = [ordered]@{
    passed = $true
    subject = $bftSignature.SignerCertificate.Subject
    thumbprint = $bftSignature.SignerCertificate.Thumbprint
    timestamped = $true
    unchangedOtherFiles = $bftOriginalFiles.Count - 1
    exeSha256 = (Get-FileHash -LiteralPath $bftExe -Algorithm SHA256).Hash
}
$bftReportDirectory = Split-Path -Parent $ReportPath
if ($bftReportDirectory) { New-Item -ItemType Directory -Path $bftReportDirectory -Force | Out-Null }
$bftReport | ConvertTo-Json | Set-Content -LiteralPath $ReportPath -Encoding UTF8
Write-Host 'Trusted SignPath signature verified; upstream binaries and other files are unchanged.'
