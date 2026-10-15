param(
    [switch]$SkipBuild,
    [string]$InstallerFileName = "",
    [long]$ResumeDraftId = 0
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
    $existingAssets = @($Release.assets | Where-Object name -eq $file.Name)
    if ($existingAssets.Count -gt 0) {
        $expectedDigest = "sha256:" + (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existingAssets.Count -ne 1 -or $existingAssets[0].state -ne "uploaded" -or $existingAssets[0].size -ne $file.Length -or $existingAssets[0].digest -ne $expectedDigest) {
            throw "草稿中已有不匹配的同名资产，不会覆盖或删除：$($file.Name)"
        }
        Write-Host "已校验并保留：$($file.Name)" -ForegroundColor Cyan
        return
    }
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
if ($ResumeDraftId -lt 0 -or ($ResumeDraftId -gt 0 -and -not $SkipBuild)) {
    throw "续传必须使用正数草稿 ID 和 -SkipBuild，保留原验收安装包。"
}
if ([string]::IsNullOrEmpty($InstallerFileName)) {
    $InstallerFileName = "YiSheng-Setup-$Version.exe"
}
else {
    $namePattern = '^YiSheng-Setup-' + [regex]::Escape($Version) + '(?:-[A-Za-z0-9]+)*\.exe$'
    if ([IO.Path]::GetFileName($InstallerFileName) -ne $InstallerFileName -or $InstallerFileName -cnotmatch $namePattern) {
        throw "安装包名称必须是当前版本的文件名，不能包含路径。"
    }
    if (-not $SkipBuild) { throw "指定安装包文件名时必须使用 -SkipBuild，并先完成该包的构建与验收。" }
}
$Installer = Join-Path $Root $InstallerFileName
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
    if ($tagCommit -ne $head) {
        if (-not $ResumeDraftId) { throw "Tag $Tag 不在当前 Commit，已停止发布。" }
        git merge-base --is-ancestor $tagCommit $head
        if ($LASTEXITCODE -ne 0) { throw "续传 Tag 不是当前 Commit 的祖先。" }
        $changesSinceTag = @(git diff --name-only $tagCommit $head)
        if ($LASTEXITCODE -ne 0 -or @($changesSinceTag | Where-Object { $_ -notin @('scripts/Publish-Release.ps1', 'docs/RELEASING.md') }).Count -gt 0) {
            throw "Tag 之后包含应用或发布内容变化，不能续传旧包。"
        }
    }

    $remoteLines = @(git ls-remote --tags origin "refs/tags/$Tag" "refs/tags/$Tag^{}")
    if ($LASTEXITCODE -ne 0 -or $remoteLines.Count -eq 0) { throw "远程尚未 Push Tag $Tag。" }
    $remoteCommit = $null
    foreach ($line in $remoteLines) {
        if ($line -match '^([0-9a-f]{40})\s+refs/tags/.+\^\{\}$') { $remoteCommit = $matches[1] }
    }
    if (-not $remoteCommit -and $remoteLines[0] -match '^([0-9a-f]{40})\s+') { $remoteCommit = $matches[1] }
    if ($remoteCommit -ne $tagCommit) { throw "远程 Tag $Tag 与本地 Tag Commit 不一致。" }

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

    if ($ResumeDraftId) {
        $release = Invoke-GitHubJson -Method Get -Uri "https://api.github.com/repos/$Owner/$Repository/releases/$ResumeDraftId"
        if ($release.id -ne $ResumeDraftId -or $release.draft -ne $true -or $release.prerelease -ne $false -or $release.tag_name -cne $Tag -or $release.name -cne "译声 YiSheng $Version" -or $release.body -cne $Notes) {
            throw "草稿 ID、版本、说明或发布状态不匹配；未更改远程内容。"
        }
        $expectedNames = @($installerFile.Name, (Split-Path -Leaf $Checksum), 'update.json')
        if (@($release.assets | Where-Object { $_.name -notin $expectedNames }).Count -gt 0) {
            throw "草稿包含非本次预期资产，已停止续传。"
        }
        Write-Host "继续已确认草稿：$ResumeDraftId" -ForegroundColor Cyan
    }
    else {
        if ($null -ne (Get-ReleaseByTag -Tag $Tag)) {
            throw "GitHub Release $Tag 已存在。脚本不会覆盖、删除或重发已有版本。"
        }
        $releasePage = 1
        do {
            $knownReleases = Invoke-GitHubJson -Method Get -Uri "https://api.github.com/repos/$Owner/$Repository/releases?per_page=100&page=$releasePage"
            if (@($knownReleases | Where-Object { $_.tag_name -ceq $Tag }).Count -gt 0) {
                throw "同版本 Release 或草稿已存在；请核对后使用准确草稿 ID 续传，不会重复创建。"
            }
            $releasePage++
        } while ($knownReleases.Count -eq 100)
        $release = Invoke-GitHubJson -Method Post -Uri "https://api.github.com/repos/$Owner/$Repository/releases" -Body @{
            tag_name = $Tag
            name = "译声 YiSheng $Version"
            body = $Notes
            draft = $true
            prerelease = $false
        }
        Write-Host "已创建发布草稿：$($release.id)" -ForegroundColor Cyan
    }
    Add-ReleaseAsset -Release $release -Path $Installer -ContentType "application/octet-stream"
    Add-ReleaseAsset -Release $release -Path $Checksum -ContentType "text/plain"
    Add-ReleaseAsset -Release $release -Path $Manifest -ContentType "application/json"

    $prepared = Invoke-GitHubJson -Method Get -Uri "https://api.github.com/repos/$Owner/$Repository/releases/$($release.id)"
    $assets = @($prepared.assets)
    foreach ($expected in @($installerFile.Name, (Split-Path -Leaf $Checksum), "update.json")) {
        if (@($assets | Where-Object name -eq $expected).Count -ne 1) { throw "发布后缺少文件：$expected" }
    }
    foreach ($localPath in @($Installer, $Checksum, $Manifest)) {
        $localFile = Get-Item -LiteralPath $localPath
        $remoteAsset = @($assets | Where-Object name -eq $localFile.Name)[0]
        $expectedDigest = "sha256:" + (Get-FileHash -LiteralPath $localPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($remoteAsset.state -ne "uploaded" -or $remoteAsset.size -ne $localFile.Length -or $remoteAsset.digest -ne $expectedDigest) {
            throw "草稿资产校验失败，未切换公开更新入口：$($localFile.Name)"
        }
    }
    $published = Invoke-GitHubJson -Method Patch -Uri "https://api.github.com/repos/$Owner/$Repository/releases/$($release.id)" -Body @{
        draft = $false
        make_latest = "true"
    }
    Write-Host "发布完成：$($published.html_url)" -ForegroundColor Green
}
finally {
    $token = $null
    if ($credentialMap) { $credentialMap.Clear() }
    $script:Headers = $null
    Pop-Location
}
