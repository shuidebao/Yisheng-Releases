param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Owner = "shuidebao"
$Repository = "Yisheng-Releases"
$VersionFile = Join-Path $Root "APP\Yisheng\VERSION"
$NotesFile = Join-Path $Root "RELEASE_NOTES.md"
$BuildScript = Join-Path $Root "build_offline_installer.ps1"
$ReleaseBuild = Join-Path $Root ".release-build"

function Invoke-GitHubJson {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [object]$Body
    )
    $parameters = @{
        Method = $Method
        Uri = $Uri
        Headers = $script:Headers
    }
    if ($null -ne $Body) {
        $parameters.ContentType = "application/json; charset=utf-8"
        $parameters.Body = $Body | ConvertTo-Json -Depth 8
    }
    Invoke-RestMethod @parameters
}

function Get-ReleaseByTag {
    param([Parameter(Mandatory = $true)][string]$Tag)
    try {
        Invoke-GitHubJson -Method Get -Uri "https://api.github.com/repos/$Owner/$Repository/releases/tags/$Tag"
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 404) { return $null }
        throw
    }
}

function Add-ReleaseAsset {
    param(
        [Parameter(Mandatory = $true)][object]$Release,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ContentType
    )
    $file = Get-Item -LiteralPath $Path
    $uploadBase = [string]$Release.upload_url
    $templateIndex = $uploadBase.IndexOf("{")
    if ($templateIndex -ge 0) { $uploadBase = $uploadBase.Substring(0, $templateIndex) }
    $encodedName = [uri]::EscapeDataString($file.Name)
    Write-Host "正在上传：$($file.Name) ($($file.Length) bytes)" -ForegroundColor Cyan
    Invoke-RestMethod -Method Post -Uri "${uploadBase}?name=${encodedName}" -Headers $script:Headers -ContentType $ContentType -InFile $file.FullName | Out-Null
}

if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) { throw "找不到 VERSION 文件。" }
$Version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "VERSION 必须是 1.0.11 这样的三段版本号。" }
$Tag = "v$Version"
$Installer = Join-Path $Root "YiSheng-Setup-$Version.exe"
$Checksum = "$Installer.sha256"
$Manifest = Join-Path $ReleaseBuild "update.json"

if (-not (Test-Path -LiteralPath $NotesFile -PathType Leaf)) { throw "找不到 RELEASE_NOTES.md。" }
$Notes = (Get-Content -LiteralPath $NotesFile -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($Notes) -or $Notes -match '在这里填写|下一版本发布说明') {
    throw "请先把 RELEASE_NOTES.md 修改为 $Version 的真实更新说明。"
}

Push-Location $Root
try {
    $status = @(git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw "当前目录不是可用的 Git 仓库。" }
    if ($status.Count -gt 0) { throw "工作区还有未提交修改。请先 Commit，再发布。" }

    $head = (git rev-parse HEAD).Trim()
    $tagCommit = (git rev-list -n 1 $Tag 2>$null).Trim()
    if ([string]::IsNullOrWhiteSpace($tagCommit)) { throw "本地不存在 Tag $Tag。" }
    if ($tagCommit -ne $head) { throw "Tag $Tag 不在当前 Commit，已停止发布。" }

    $remoteLines = @(git ls-remote --tags origin "refs/tags/$Tag" "refs/tags/$Tag^{}")
    if ($LASTEXITCODE -ne 0 -or $remoteLines.Count -eq 0) { throw "远程尚未 Push Tag $Tag。" }
    $remoteCommit = $null
    foreach ($line in $remoteLines) {
        if ($line -match '^([0-9a-f]{40})\s+refs/tags/.+\^\{\}$') { $remoteCommit = $matches[1] }
    }
    if (-not $remoteCommit -and $remoteLines[0] -match '^([0-9a-f]{40})\s+') { $remoteCommit = $matches[1] }
    if ($remoteCommit -ne $head) { throw "远程 Tag $Tag 与当前 Commit 不一致。" }

    if (-not $SkipBuild) { & $BuildScript }
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { throw "找不到构建产物：$Installer" }
    if (-not (Test-Path -LiteralPath $Checksum -PathType Leaf)) { throw "找不到校验文件：$Checksum" }

    $installerFile = Get-Item -LiteralPath $Installer
    $sha256 = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash
    $checksumText = (Get-Content -LiteralPath $Checksum -Raw).Trim()
    if ($checksumText -ne "$sha256  $($installerFile.Name)") { throw "SHA-256 文件与安装包不一致。" }

    New-Item -ItemType Directory -Path $ReleaseBuild -Force | Out-Null
    $manifestObject = [ordered]@{
        version = $Version
        url = "https://github.com/$Owner/$Repository/releases/download/$Tag/$($installerFile.Name)"
        filename = $installerFile.Name
        sha256 = $sha256
        size = [long]$installerFile.Length
        notes = $Notes
        mandatory = $false
    }
    $manifestJson = $manifestObject | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($Manifest, $manifestJson + "`n", (New-Object Text.UTF8Encoding($false)))

    $credentialInput = "protocol=https`nhost=github.com`nusername=$Owner`n`n"
    $credentialMap = @{}
    foreach ($line in ($credentialInput | git credential fill)) {
        if ($line -match '^([^=]+)=(.*)$') { $credentialMap[$matches[1]] = $matches[2] }
    }
    $token = $credentialMap["password"]
    if ([string]::IsNullOrWhiteSpace($token)) { throw "Git Credential Manager 尚未返回 GitHub 授权。" }
    $script:Headers = @{
        Authorization = "Bearer $token"
        Accept = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
        "User-Agent" = "YiSheng-Release-Publisher"
    }

    if ($null -ne (Get-ReleaseByTag -Tag $Tag)) {
        throw "GitHub Release $Tag 已存在。脚本不会覆盖、删除或重发已有版本。"
    }
    $release = Invoke-GitHubJson -Method Post -Uri "https://api.github.com/repos/$Owner/$Repository/releases" -Body @{
        tag_name = $Tag
        name = "译声 YiSheng $Version"
        body = $Notes
        draft = $false
        prerelease = $false
        make_latest = "true"
    }
    Add-ReleaseAsset -Release $release -Path $Installer -ContentType "application/octet-stream"
    Add-ReleaseAsset -Release $release -Path $Checksum -ContentType "text/plain"
    Add-ReleaseAsset -Release $release -Path $Manifest -ContentType "application/json"

    $published = Get-ReleaseByTag -Tag $Tag
    $assets = @($published.assets)
    foreach ($expected in @($installerFile.Name, (Split-Path -Leaf $Checksum), "update.json")) {
        if (@($assets | Where-Object name -eq $expected).Count -ne 1) { throw "发布后缺少文件：$expected" }
    }
    Write-Host "发布完成：$($published.html_url)" -ForegroundColor Green
}
finally {
    $token = $null
    if ($credentialMap) { $credentialMap.Clear() }
    $script:Headers = $null
    Pop-Location
}
