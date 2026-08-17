$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Root "launcher\YishengLauncher.cs"
$VersionFile = Join-Path $Root "VERSION"
$Icon = Join-Path $Root "static\yisheng.ico"
$Output = Join-Path $Root "Yisheng.exe"
$Temporary = Join-Path $Root "Yisheng.next.exe"
$BuildDirectory = Join-Path $Root ".build"
$VersionSource = Join-Path $BuildDirectory "YishengVersion.g.cs"
$PythonWindow = Join-Path $Root "runtime\python312\pythonw.exe"
$NamedBackend = Join-Path $Root "runtime\python312\YishengBackend.exe"

if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
    throw "VERSION file was not found: $VersionFile"
}
$Version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must use semantic version format such as 1.0.11."
}
$AssemblyVersion = "$Version.0"
New-Item -ItemType Directory -Path $BuildDirectory -Force | Out-Null
$VersionCode = @"
using System.Reflection;
[assembly: AssemblyVersion("$AssemblyVersion")]
[assembly: AssemblyFileVersion("$AssemblyVersion")]
"@
[IO.File]::WriteAllText($VersionSource, $VersionCode, (New-Object Text.UTF8Encoding($false)))

$Compiler = Get-ChildItem "$env:WINDIR\Microsoft.NET\Framework64" -Filter csc.exe -Recurse -ErrorAction SilentlyContinue |
    Select-Object -Last 1 -ExpandProperty FullName
if (-not $Compiler) { throw "The Windows .NET compiler was not found." }

$Arguments = @(
    "/nologo", "/target:winexe", "/platform:x64", "/optimize+", "/out:$Temporary",
    "/reference:System.dll", "/reference:System.Drawing.dll", "/reference:System.Windows.Forms.dll"
)
if (Test-Path -LiteralPath $Icon -PathType Leaf) { $Arguments += "/win32icon:$Icon" }
$Arguments += @($Source, $VersionSource)

& $Compiler $Arguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Temporary -PathType Leaf)) {
    throw "Desktop launcher compilation failed."
}
Move-Item -LiteralPath $Temporary -Destination $Output -Force
if (-not (Test-Path -LiteralPath $PythonWindow -PathType Leaf)) {
    throw "The embedded Python window runtime was not found."
}
Copy-Item -LiteralPath $PythonWindow -Destination $NamedBackend -Force
Write-Host "Desktop launcher $Version ready: $Output" -ForegroundColor Green
