# 译声 YiSheng

译声 YiSheng 是一个面向 Windows 的本地实时语音识别与翻译软件，适用于 VRChat、游戏、视频、播客和麦克风语音等场景。

## 当前功能

- 识别中文、日语或英语，并翻译为这三种语言之一
- 显示识别原文和所选目标语言翻译
- 监听 Windows 系统声音、麦克风，或同时监听两者
- 提供透明、置顶、可缩放和可锁定的迷你字幕
- 支持调整原文与翻译字幕的字号和颜色
- Base 识别模型及中/日/英互译模型随正式安装包提供
- Tiny、Small、Medium 识别模型可按需下载
- 自动检查 GitHub Releases 上的新版本，并校验安装包 SHA-256
- 支持 Windows 10/11 64 位

软件不需要用户配置 OpenAI API，也不依赖付费 API。实时音频、识别和翻译在用户电脑本地处理；联网用于可选模型下载和软件更新。

## 开发者

- Developer: Huyuanhao
- Copyright © 2026 Huyuanhao
- Official repository: https://github.com/shuidebao/Yisheng-Releases

## 技术组成

- Python 3.12、FastAPI、Uvicorn
- Faster-Whisper / CTranslate2 本地语音识别
- 本地离线翻译模型
- pywebview、WebView2 和 Windows Forms 桌面界面
- PyAudioWPatch / WASAPI 系统声音捕获
- C# Windows 启动器与离线安装器

## 版本与构建

项目的唯一版本号保存在 [`APP/Yisheng/VERSION`](APP/Yisheng/VERSION)。正式安装包通过 PowerShell 构建：

仓库根目录的 `update.json` 是已经公开版本的更新清单快照，不是版本号输入；未来发布脚本会根据 `VERSION` 和实际安装包重新生成要上传的清单。

```powershell
.\build_offline_installer.ps1
```

构建结果使用统一名称：

```text
YiSheng-Setup-<版本>.exe
YiSheng-Setup-<版本>.exe.sha256
```

完整发布步骤见 [`docs/RELEASING.md`](docs/RELEASING.md)。

## 测试

```powershell
APP\Yisheng\runtime\python312\python.exe -m unittest discover -s APP\Yisheng\tests -v
```

GitHub Actions 也会在提交和 Tag 上运行不需要模型文件的基础测试。

## 下载

正式版本请从 [GitHub Releases](https://github.com/shuidebao/Yisheng-Releases/releases/latest) 下载。

## License

当前仓库尚未添加开源许可证。许可证和代码使用范围将在开发者作出决定后另行说明。
