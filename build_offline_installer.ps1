param(
    [string]$Source = ".\APP\Yisheng"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$SourcePath = (Resolve-Path -LiteralPath $Source).Path
$VersionFile = Join-Path $SourcePath "VERSION"
if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
    throw "VERSION file was not found: $VersionFile"
}
$Version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must use semantic version format such as 1.0.11."
}
$AssemblyVersion = "$Version.0"
$BuildPath = Join-Path $Root ".offline-installer-build"
$PayloadPath = Join-Path $BuildPath "payload.zip"
$StubPath = Join-Path $BuildPath "YishengInstallerStub.exe"
$OutputPath = Join-Path $Root ("YiSheng-Setup-{0}.exe" -f $Version)
$ChecksumPath = "$OutputPath.sha256"
$InstallerSource = Join-Path $Root "installer\OfflineInstaller.cs"
$InstallerVersionSource = Join-Path $BuildPath "InstallerVersion.g.cs"
$Icon = Join-Path $SourcePath "static\yisheng.ico"

if (Test-Path -LiteralPath $BuildPath) {
    $resolvedBuild = (Resolve-Path -LiteralPath $BuildPath).Path
    if (-not $resolvedBuild.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clear a build directory outside the workspace."
    }
    Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
}
New-Item -ItemType Directory -Path $BuildPath | Out-Null
$VersionCode = @"
using System.Reflection;
[assembly: AssemblyVersion("$AssemblyVersion")]
[assembly: AssemblyFileVersion("$AssemblyVersion")]
internal static class BuildInfo
{
    internal const string Version = "$Version";
}
"@
[IO.File]::WriteAllText($InstallerVersionSource, $VersionCode, (New-Object Text.UTF8Encoding($false)))

Write-Host ("[1/5] Rebuilding the {0} desktop launcher..." -f $Version) -ForegroundColor Cyan
& (Join-Path $SourcePath "build_desktop.ps1")
if ($LASTEXITCODE -ne 0) { throw "Desktop launcher build failed." }

Write-Host "[2/5] Checking the offline Base, English and Japanese models..." -ForegroundColor Cyan
$Required = @(
    "VERSION",
    "Yisheng.exe",
    "runtime\python312\YishengBackend.exe",
    "runtime\python312\pythonw.exe",
    "runtime\python312\Lib\site-packages\faster_whisper\__init__.py",
    ".models\whisper\local\base\model.bin",
    ".models\argos\translate-en_zh-1_9\model\model.bin",
    ".models\translations\ja_en\model.bin",
    "app\main.py",
    "static\index.html"
)
foreach ($Relative in $Required) {
    $Path = Join-Path $SourcePath $Relative
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Offline payload is missing: $Relative" }
}

Write-Host "[3/5] Compressing the ready-to-run offline application..." -ForegroundColor Cyan
$TarArguments = @(
    "-a", "-c", "-f", $PayloadPath,
    "--exclude=.models/whisper/local/medium",
    "--exclude=.models/whisper/local/tiny",
    "--exclude=.models/whisper/local/small",
    "--exclude=.models/webview-profile",
    "--exclude=.models/webview-test-profile",
    "--exclude=.models/webview-probe-profile",
    "--exclude=.models/overlay-style.json",
    "--exclude=logs",
    "--exclude=__pycache__",
    "--exclude=*.pyc",
    "--exclude=setup.ps1",
    "--exclude=setup.cmd",
    "--exclude=安装译声.cmd",
    "--exclude=build_*.ps1",
    "--exclude=build_*.cmd",
    "--exclude=package_release.cmd",
    "--exclude=runtime/get-pip.py",
    "--exclude=model-packages",
    "--exclude=model-sources",
    "--exclude=build-tools",
    "--exclude=tests",
    "--exclude=.models/translations/ja_zh",
    "--exclude=.models/translations/ja_zh_int8",
    "--exclude=.models/translations/en_zh",
    "--exclude=.models/argos/ja_en",
    "--exclude=runtime/python312/Lib/site-packages/torch",
    "--exclude=runtime/python312/Lib/site-packages/torch-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/stanza",
    "--exclude=runtime/python312/Lib/site-packages/stanza-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/argostranslate",
    "--exclude=runtime/python312/Lib/site-packages/argostranslate-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/spacy",
    "--exclude=runtime/python312/Lib/site-packages/spacy-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/sympy",
    "--exclude=runtime/python312/Lib/site-packages/sympy-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/networkx",
    "--exclude=runtime/python312/Lib/site-packages/networkx-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/torchgen",
    "--exclude=runtime/python312/Lib/site-packages/mpmath",
    "--exclude=runtime/python312/Lib/site-packages/mpmath-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/blis",
    "--exclude=runtime/python312/Lib/site-packages/blis-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/thinc",
    "--exclude=runtime/python312/Lib/site-packages/thinc-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/srsly",
    "--exclude=runtime/python312/Lib/site-packages/srsly-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/emoji",
    "--exclude=runtime/python312/Lib/site-packages/emoji-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/sacremoses",
    "--exclude=runtime/python312/Lib/site-packages/sacremoses-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/hf_xet",
    "--exclude=runtime/python312/Lib/site-packages/hf_xet-*.dist-info",
    "--exclude=runtime/python312/Lib/site-packages/pip",
    "--exclude=runtime/python312/Lib/site-packages/pip-*.dist-info",
    "-C", $SourcePath, "."
)
& tar.exe $TarArguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $PayloadPath -PathType Leaf)) { throw "Offline payload compression failed." }

Write-Host "[4/5] Compiling the graphical installer..." -ForegroundColor Cyan
$Compiler = Get-ChildItem "$env:WINDIR\Microsoft.NET\Framework64" -Filter csc.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -Last 1 -ExpandProperty FullName
if (-not $Compiler) { throw "The Windows .NET compiler was not found." }
$CompilerArguments = @(
    "/nologo", "/target:winexe", "/platform:x64", "/optimize+", "/out:$StubPath",
    "/reference:System.dll", "/reference:System.Drawing.dll", "/reference:System.Windows.Forms.dll",
    "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll"
)
if (Test-Path -LiteralPath $Icon) { $CompilerArguments += "/win32icon:$Icon" }
$CompilerArguments += @($InstallerSource, $InstallerVersionSource)
& $Compiler $CompilerArguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $StubPath -PathType Leaf)) { throw "Installer compilation failed." }

Write-Host "[5/5] Appending and signing the offline payload checksum..." -ForegroundColor Cyan
$PayloadHash = [Security.Cryptography.SHA256]::Create()
$PayloadStream = [IO.File]::OpenRead($PayloadPath)
try { $HashBytes = $PayloadHash.ComputeHash($PayloadStream) }
finally { $PayloadStream.Dispose(); $PayloadHash.Dispose() }

$Output = [IO.File]::Open($OutputPath, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $Stub = [IO.File]::OpenRead($StubPath)
    try { $Stub.CopyTo($Output); $PayloadOffset = $Stub.Length }
    finally { $Stub.Dispose() }
    $Payload = [IO.File]::OpenRead($PayloadPath)
    try { $Payload.CopyTo($Output); $PayloadLength = $Payload.Length }
    finally { $Payload.Dispose() }
    $Writer = New-Object IO.BinaryWriter($Output, [Text.Encoding]::UTF8, $true)
    try {
        $Writer.Write([Text.Encoding]::ASCII.GetBytes("YSHZIP01"))
        $Writer.Write([Int64]$PayloadOffset)
        $Writer.Write([Int64]$PayloadLength)
        $Writer.Write($HashBytes)
        $Writer.Flush()
    }
    finally { $Writer.Dispose() }
}
finally { $Output.Dispose() }

$File = Get-Item -LiteralPath $OutputPath
$Digest = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash
$ChecksumLine = "$Digest  $($File.Name)`r`n"
[IO.File]::WriteAllText($ChecksumPath, $ChecksumLine, (New-Object Text.UTF8Encoding($false)))
Write-Host ("Offline installer ready: {0}" -f $File.FullName) -ForegroundColor Green
Write-Host ("Size: {0:N1} MB" -f ($File.Length / 1MB))
Write-Host ("SHA256: {0}" -f $Digest)
Write-Host ("Checksum file: {0}" -f $ChecksumPath)
