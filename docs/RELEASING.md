# 译声发布流程

本流程使用 Git、GitHub Releases、Git Credential Manager、PowerShell 和项目现有构建工具，不需要付费 API 或代码签名证书。

## 1. 准备版本

1. 只修改 `APP/Yisheng/VERSION`，例如改为 `1.0.11`。
2. 更新 `RELEASE_NOTES.md`。
3. 完成功能修改并运行测试。
4. 运行 `build_offline_installer.ps1` 做本地完整构建验证。

构建脚本会自动生成：

- `YiSheng-Setup-1.0.11.exe`
- `YiSheng-Setup-1.0.11.exe.sha256`

## 2. 保存开发记录

```powershell
git add .
git commit -m "Release YiSheng 1.0.11"
git tag -a v1.0.11 -m "YiSheng 1.0.11"
git push origin main
git push origin v1.0.11
```

Tag 必须和 `VERSION` 一致。不要移动、覆盖或删除已经公开的 Tag。

## 3. 发布

确认 GitHub 登录和 Git Credential Manager 授权后运行：

```powershell
.\scripts\Publish-Release.ps1
```

脚本会拒绝覆盖已经存在的 Release，并自动执行：

1. 检查当前 Commit、Tag 和版本是否一致。
2. 构建单文件离线安装包。
3. 生成 SHA-256 文件和自动更新 `update.json`。
4. 创建同版本 GitHub Release。
5. 上传安装包、SHA-256 和 `update.json`。
6. 从公开地址反向验证最新版清单。

软件始终读取 `https://github.com/shuidebao/Yisheng-Releases/releases/latest/download/update.json`。发布脚本上传的新清单会沿用这个固定入口，因此旧版本仍可发现使用新命名规则的安装包。

## 为什么暂时不在 GitHub Actions 构建完整安装包

正式安装包包含约数百 MB 的 Python 运行环境和离线模型。这些第三方大文件不适合直接保存到普通 Git 仓库；强行在 GitHub Actions 中重新下载也会让构建依赖外部模型网站和临时网络状态。因此目前采用“GitHub Actions 免费运行源码测试，本机 PowerShell 完成可复现发布”的稳定方案。

以后如果建立了长期稳定、免费的模型镜像，可以再把完整构建迁移到单一 Release Workflow，不需要改变软件的自动更新地址。
