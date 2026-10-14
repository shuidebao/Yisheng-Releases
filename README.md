# 译声 YiSheng

译声 YiSheng 是一个面向 Windows 的本地实时语音识别与翻译软件，适用于 VRChat、游戏、视频、播客和麦克风语音等场景。

## 项目状态

2026-10-14 起停止主动开发。1.0.25 是本项目的最后一次整理更新，保留现有源码和安装包供参考与使用，不承诺后续功能、问题修复或兼容性适配。

本版安装包名为 **`YiSheng-Setup-1.0.25-VR-Test.exe`**，包含此前的启动修复、电脑声音设备修复、可选 API 文字翻译，以及默认关闭的 VR 字幕实验功能。**VR 尚未完成真实头显或 VRChat 内验收，不能视为已确认兼容 Quest。** 现有桌面功能可在不启用 VR 的情况下使用。

## 当前功能

- 识别中文、日语、英语或韩语，并翻译为这四种语言之一
- 显示识别原文和所选目标语言翻译
- 监听 Windows 系统声音、麦克风，或同时监听两者
- 提供透明、置顶、可缩放和可锁定的迷你字幕
- 提供默认关闭的 SteamVR 当前句字幕实验功能（限 Windows PCVR，未完成头显验收）
- 支持调整原文与翻译字幕的字号和颜色
- Base 识别模型及中/日/英/韩互译模型随正式安装包提供
- Tiny、Small、Medium 识别模型可按需下载
- 自动检查 GitHub Releases 上的新版本，并校验安装包 SHA-256
- 支持 Windows 10/11 64 位

默认本地模式不需要配置 API，也不依赖付费 API；语音识别和翻译都在电脑上完成。联网用于可选模型下载和软件更新。

## 可选 API 翻译（随 1.0.25 公开）

运行设置新增“本地离线 / API 翻译”选择。本地语音识别保持不变，API 模式只将识别后的文字（包括同一句的续写内容）发给用户指定的服务，返回译文后仍显示在主界面和迷你字幕中。不上传音频，不自动切换服务或回退离线。

1. 停止同传，打开设置，选择 API 翻译。
2. 填写服务方提供的 Base URL、模型名和密钥；地址常见以 `/v1` 结尾，也接受完整 `/chat/completions` 地址。接口必须兼容 Chat Completions，不支持仅提供 Responses 或厂商专有协议的端点。
3. 确认文字发送和可能的费用，按需点击“测试连接”（只发送固定测试文字 `Hello.`，也可能计费），再应用设置。

API 地址、模型名和密钥只用于本次运行，不写入浏览器存储或配置文件。应用后密钥输入框会清空，密钥仅保存在本次后端进程内存中；每次重新启动后端默认本地模式，需重新配置。切回本地会清除本次 API 配置，更换地址或模型时不会把旧密钥自动带给新配置。

同传期间不能更改翻译设置；录音片段绑定开始同传时的设置版本，过期片段会被拒绝，不会因模式切换而发送到新的服务。

远程服务要求 HTTPS；本机兼容服务允许 `http://localhost`、`http://127.0.0.1` 和 `http://[::1]`。重定向会被拒绝，避免文字和密钥被转发到非预期地址。失败时保留原文并提示认证、额度、连接或响应问题；不自动重试。服务是否收费、数据保留、速度和译文质量由用户选择的服务决定，软件不承诺 API 一定更快或更准。

协议参考：[Chat Completions 消息与响应格式](https://developers.openai.com/api/docs/guides/migrate-to-responses)。正式可用功能仍以 GitHub Release 对应版本为准。

## VR 字幕实验功能

面向 Windows + SteamVR + PC 版 VRChat；Quest 有线或无线连接都要求游戏实际经过 SteamVR，不支持 Quest 一体机直接运行。只同步当前一句字幕，不写入 VRChat 聊天框或通过 OSC 发送给其他玩家；录屏、镜像和直播是否捕获叠层仍需自行验证。

安装与检查步骤见 [1.0.25 VR 测试说明](YiSheng-1.0.25-VR-测试说明.md)。头显显示、连接兼容性、私人性、长时间稳定性和游戏性能尚未验收，项目停止开发后不承诺完成这些验证。

## 韩语支持

1.0.21 新增韩语作为识别语言和翻译目标，支持韩英互译，以及经英语中转的韩中、韩日互译。仍为离线处理，按需加载模型，不改变现有中日英翻译参数。韩语长句保留词间空格，迷你字幕仍只显示当前一句。

正式版功能和下载文件以 GitHub Releases 为准。中转翻译、游戏术语、短音频自动识别仍有准确性限制。

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

本次 1.0.25 分发沿用已验收安装包的 `-VR-Test` 后缀，版本号仍为 1.0.25。发布时复用该包，不覆盖原始验收文件。

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
