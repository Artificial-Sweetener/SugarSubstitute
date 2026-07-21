<p align="center">
  <img src="docs/readme/sugarsubstitute-logo.svg" alt="SugarSubstitute：ComfyUI 原生 Qt 前端" width="680">
</p>

<p align="center">
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/releases"><img src="https://img.shields.io/github/v/release/Artificial-Sweetener/SugarSubstitute?include_prereleases" alt="最新版本"></a>
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/Artificial-Sweetener/SugarSubstitute/release.yml?branch=main&label=Tests" alt="测试状态"></a>
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/releases"><img src="https://img.shields.io/github/downloads/Artificial-Sweetener/SugarSubstitute/total" alt="版本下载量"></a>
  <a href="https://www.gnu.org/licenses/gpl-3.0.html"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue" alt="GPL-3.0-or-later 许可证"></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>简体中文</strong> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a>
</p>

**SugarSubstitute 是面向 [ComfyUI](https://github.com/Comfy-Org/ComfyUI) 的 Qt 前端，写给喜欢节点图的能力、却不想整天埋头理线的人。**

我总在搭建相同的工作流片段：开开关关、挪来挪去，然后再把线一根根接回去。终于有一天，我受够了。那些片段变成了 [**Cubes**](https://github.com/Artificial-Sweetener/SugarCubes)，围绕它们打造的桌面应用则成了 SugarSubstitute。

**SugarSubstitute 目前处于公开测试阶段。** Windows x64、Apple Silicon 和 Linux x64 均有专用安装程序。

**[下载最新测试版](#安装)**，支持 Windows x64、Apple Silicon 和 Linux x64。

看看[路线图](ROADMAP.md)，了解我接下来想做什么，也欢迎告诉我还漏了什么。

<p align="center">
  <img src="docs/readme/sugarsubstitute-workspace.png" alt="SugarSubstitute 工作区，包含可复用的 Cubes、提示词控件和生成结果" width="900">
  <br>
  <em>主工作区把 Cube 栈、提示词、生成控件和最新结果都放在一个地方。</em>
</p>

## 简单来说

- **堆叠工作流模块，而不是散落的节点。** 添加、排序、静音或移除 Cubes，连接交给 SugarSubstitute 处理。
- **别再等 WebUI 跟上。** 只要 ComfyUI 能运行某个模型，你就能用 Cube 把它带进 SugarSubstitute。会搭 ComfyUI 节点图，就会做 Cube。
- **一次更新全部工作流。** 发现超分该换一种做法，或者新的局部重绘技术出现了？只需更新包含那段流程的 Cube，所有 Substitute 工作流都会一起跟上。
- **别再重复劳动。** 种子、采样器和其他兼容设置只改一次，不必在工作流里到处翻找。
- **真正为图像生成而生的富文本提示词编辑器。** 自动补全、富文本渲染、LoRA、通配符、强调、场景和可拖动片段，全都在同一个编辑器里。
- **用眼睛挑模型。** 搜索缩略图和元数据，不必再钻进一堆文件名里寻宝。
- **在图片旁边工作。** 加载、蒙版、生成、对比、重新打开结果，不用在不同工具之间来回跳。
- **分享完整配方。** 一张配方 PNG 就能携带工作流、提示词、设置，以及安全找回缺失模型所需的足够信息。

## 看看 SugarSubstitute 跑起来的样子

<p align="center">
  <a href="https://www.youtube.com/watch?v=wfamuJZCD2c">
    <img src="docs/readme/youtube-beta-preview.png" alt="在 YouTube 上观看 SugarSubstitute 测试版展示" width="720">
  </a>
  <br>
  <em>点击预览图，在 YouTube 上观看 SugarSubstitute 测试版展示。</em>
</p>

## 它还是测试版。请尽管折腾。

SugarSubstitute 目前是公开测试版。我确实用它干活，但我也知道边边角角还会有毛刺。如果设置失败、程序崩溃，或者一个普通操作莫名其妙地别扭，请[提交 issue](https://github.com/Artificial-Sweetener/SugarSubstitute/issues)，说明你当时在做什么，并附上 SugarSubstitute 提供的诊断信息。

**硬件覆盖情况：** 我使用 NVIDIA 硬件进行开发和推理。托管设置也为受支持的 AMD 和 Intel GPU、Apple MPS，以及 Windows 上的纯 CPU 推理提供了路径，但这些硬件配置我还没有亲自测试过。如果你试了其中一种，请告诉我准确的硬件和操作系统、设置是否完成，以及能否正常生成。成功的反馈同样重要——没人出声和一切完美，从我这边看起来烦人地一模一样。

## 安装

设置程序可以创建一个由 SugarSubstitute 管理的 ComfyUI 环境，也可以连接你已经在用的环境。托管设置使用经过校验和验证的独立 Python 环境和进程内 libgit2 客户端，因此不需要系统 Python 或 Git。首次运行需要下载必要组件，可能会花一些时间。让它慢慢跑完就好。

**已经安装？** 像平常一样打开 SugarSubstitute。它会在启动时检查应用更新，通常每天一次，并自动安装较新的应用版本。一般不需要重新下载安装程序。

### <img src="docs/release/platforms/windows.svg" width="22" height="22" alt=""> Windows x64

**[下载最新 Windows x64 安装程序](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Windows-x64.exe)**

运行安装程序，选择一个普通的可写文件夹，例如 `C:\SugarSubstitute`。请避开 Program Files，因为 Windows 权限可能会干扰设置和更新。

托管设置支持通过 CUDA 使用 NVIDIA、通过 ROCm 使用受支持的 AMD RDNA 硬件、通过 XPU 使用 Intel GPU，并提供 CPU 回退。Windows 上的 AMD 加速仅限托管运行时所支持的 RDNA 3、RDNA 3.5 和 RDNA 4 硬件系列。其他 AMD 硬件会回退到 CPU，而不是拿不兼容的环境碰运气。

下一步：[选择 SugarSubstitute 使用 ComfyUI 的方式](#选择-comfyui-设置方式)。

### <img src="docs/release/platforms/apple.svg" width="22" height="22" alt=""> macOS Apple Silicon

**[下载最新 macOS Apple Silicon 安装程序](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-macOS-Apple-Silicon.dmg)**

打开 DMG，启动 SugarSubstitute Setup，然后使用默认的 `~/Applications/SugarSubstitute` 文件夹，或者选择另一个归你所有的文件夹。托管设置会在 Apple Silicon 上使用 Apple 的 MPS 加速。不支持 Intel Mac。

SugarSubstitute 采用临时签名，但没有经过公证，因为本项目没有加入 Apple 的付费 Developer Program。macOS 会警告无法验证开发者。如果 DMG 是从本仓库下载的，请在 macOS 的“隐私与安全性”设置中允许它打开。

我只在 Windows 上亲自测试过 SugarSubstitute。macOS 软件包通过 GitHub Actions 在 Apple Silicon 上构建，但仍然需要更多人在真实的 Mac 上使用和反馈。

下一步：[选择 SugarSubstitute 使用 ComfyUI 的方式](#选择-comfyui-设置方式)。

### <img src="docs/release/platforms/linux.svg" width="22" height="22" alt=""> Linux x64

选择适合你系统的软件包：

- **[下载最新 Linux x86_64 AppImage](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Linux-x86_64.AppImage)**，作为便携式安装程序使用。将它标记为可执行文件，然后运行。
- **[下载最新 Linux amd64 Debian 软件包](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Linux-amd64.deb)**，适用于 Debian、Ubuntu 及相关发行版。安装软件包，然后运行 `sugarsubstitute-setup`。

默认安装文件夹是 `~/.local/share/SugarSubstitute`。托管设置支持通过 CUDA 使用 NVIDIA、通过 ROCm 使用 AMD，以及通过 XPU 使用 Intel GPU。目前还没有可用的 Linux 托管纯 CPU 环境。

我只在 Windows 上亲自测试过 SugarSubstitute。Linux 软件包通过 GitHub Actions 在 Linux 上构建，但仍然需要更多人在真实的发行版和桌面环境中使用和反馈。

下一步：[选择 SugarSubstitute 使用 ComfyUI 的方式](#选择-comfyui-设置方式)。

### 从 Git 克隆运行

如果你想直接从仓库运行 SugarSubstitute 并参与修改，请使用源码检出。这种方式需要 Git 和 Python 3.12。

在 Windows 上，打开 PowerShell 并运行：

```powershell
git clone https://github.com/Artificial-Sweetener/SugarSubstitute.git
Set-Location SugarSubstitute
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest pytest-xdist ruff mypy pre-commit
.\.venv\Scripts\pre-commit.exe install
.\.venv\Scripts\python.exe main.py
```

在 macOS 或 Linux 上，打开终端并运行：

```bash
git clone https://github.com/Artificial-Sweetener/SugarSubstitute.git
cd SugarSubstitute
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt pytest pytest-xdist ruff mypy pre-commit
.venv/bin/pre-commit install
.venv/bin/python main.py
```

第一次从源码启动时，会打开与打包应用相同的设置流程。让它创建一个托管 ComfyUI 环境，或连接现有环境。设置完成后，每次想运行开发检出时，再执行最后一条命令即可。

### 选择 ComfyUI 设置方式

SugarSubstitute 第一次打开时会询问该如何使用 ComfyUI。之后可以在“设置”中更改连接。

#### 让 SugarSubstitute 设置 ComfyUI

这是大多数人的推荐选项。SugarSubstitute 会创建一个独立的本地 ComfyUI 工作区，为你的硬件选择合适的推理后端，安装 ComfyUI Manager 和必需的自定义节点，并随应用一起启动和停止这套 ComfyUI。托管环境会与你已经使用的任何 ComfyUI 设置保持独立。不需要系统 Python 或 Git。

如果你希望 SugarSubstitute 全权管理整个 ComfyUI 环境并让它随时可用，请选择此项。

#### 使用现有的本地 ComfyUI

选择包含现有 ComfyUI `main.py` 的文件夹。SugarSubstitute 会保留仓库和模型的原始位置，但会为 SugarSubstitute 准备该 ComfyUI 环境，包括 Python 依赖项、ComfyUI Manager 和必需的自定义节点。随后，SugarSubstitute 会在应用运行期间启动这套 ComfyUI。

如果你只想保留一套本地 ComfyUI，并且接受 SugarSubstitute 对其进行准备和启动，请选择此项。

#### 连接远程 ComfyUI

远程 ComfyUI 支持尚未经过测试。SugarSubstitute 会保存远程主机和端口，但无法在远程计算机上安装或修复任何内容。请确保服务器可通过受信任的局域网或 VPN 访问，不要将 ComfyUI 直接暴露在公共互联网上。

连接前，请在远程 ComfyUI 环境中安装以下自定义节点及其声明的 Python 依赖项：

- [Substitute BackEnd](https://github.com/Artificial-Sweetener/Substitute-BackEnd)
- [SugarCubes](https://github.com/Artificial-Sweetener/SugarCubes)
- [ComfyUI Vectorscope CC](https://github.com/pamparamm/ComfyUI-vectorscope-cc)
- [ComfyUI SeedVR2 Video Upscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler)
- [SimpleSyrup](https://github.com/Artificial-Sweetener/SimpleSyrup)
- [ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control)

安装节点后重启远程 ComfyUI 服务器，然后在 SugarSubstitute 设置中输入主机和端口。

## Cubes，不要一盘线团

Cube 是 ComfyUI 节点图中一段带版本的模块，拥有明确声明的输入、输出和控件。把需要的 Cubes 堆起来，SugarSubstitute 会连接兼容的端点。重新排序、静音或移除其中一个，连接会围绕新的堆栈自动调整，不必再做一场微型节点图外科手术。

Cube 作者决定哪些原生控件应该出现在表面。全局覆盖可以把多个 Cubes 中兼容的设置汇集到一个工具栏控件里，需要时仍然可以展开更深层的控件。

Cube 作者可以把自己的包发布到 GitHub，用户也可以订阅更新。Cube 发生变化时，你可以固定信任的版本，也可以更新它，同时把兼容的值和连接一并带到新版本。

## 别再等你的 WebUI 跟上

SugarSubstitute 为 ComfyUI 提供熟悉的 WebUI 式界面，同时不让新模型支持苦等前端版本发布。只要 ComfyUI 能运行，SugarSubstitute 就能通过 Cube 把它呈现出来。使用现有 Cube，或者自己做一个。会搭 ComfyUI 节点图，就会做 Cube。模型支持随工作流而来，而不是等 UI 终于追上。

## 提示词应该是活的

提示词编辑器理解自己显示的结构。自动补全会出现在你正在输入的位置，而底层的强调、LoRA、通配符、标点、选择和撤销状态依然完好。以逗号分隔的片段甚至可以跨折行拖动，也可以用键盘移动。

<p align="center">
  <img src="docs/readme/prompt-editor-showcase.gif" alt="SugarSubstitute 提示词编辑器，展示富文本渲染、自动补全、强调和可拖动的提示词片段" width="720" height="720">
  <br>
  <em>这个提示词编辑器不要求你背转义规则，也让你无需把手从鼠标上移开就能快速修改。</em>
</p>

## 让图片替你记住

SugarSubstitute 配方 PNG 同时携带易读的 Sugar 配方和原始 ComfyUI 工作流。打开一张配方图，就能恢复 Cube 栈及其版本、公开的值、全局覆盖、种子行为、提示词，以及同一次运行中受支持的同组图片。

……不过，如果你一直在用 Comfy 或 WebUI，这种方便大概已经见惯了。所以我们再多做一步：

如果引用的模型被移动了，SugarSubstitute 会在本地模型库中查找相同的 SHA-256 并修复路径。如果缺少完全一致的模型，而 CivitAI 又识别其哈希，SugarSubstitute 可以提供经过安全检查的下载。把结果分享给同样使用 Substitute 的朋友，他们就能下载测试配方所需的模型。

## 看图认模型，别再只认文件名

兼容的 ComfyUI 模型字段会变成可搜索的可视化选择器。浏览缩略图和易读名称，按文件名或文件夹搜索，跟踪模型加载进度，打开对应的 CivitAI 页面，还能用 LoRA 元数据把触发词直接放进提示词。

把新模型放进对应的 ComfyUI 模型文件夹，SugarSubstitute 会自动检测。它会自己加入选择器，不用你守着模型库操心。

<p align="center">
  <img src="docs/readme/model-picker.png" alt="SugarSubstitute 模型选择器，以可视缩略图展示可搜索的 Anima 扩散模型" width="720">
  <br>
  <em>模型选择器把 ComfyUI 文件夹变成可搜索的可视网格；没有图片的模型也会和带缩略图的条目一起保留。</em>
</p>

缩略图和在线元数据都是可选项。服务提供商访问权限、API 密钥和内容策略始终由你控制。

## 把图片留在手边

原生画布为源图、蒙版、预览和最终输出提供了真正的工作空间。以光标为中心放大细节，绘制蒙版或使用“智能选择”，对比结果，并把画布停靠或浮动到你觉得顺手的位置。

Substitute 的画布基于 [QPane](https://github.com/Artificial-Sweetener/QPane) 构建，并完全在 CPU 上运行——毕竟你我都知道，生成图像时 GPU 还有更重要的事要忙。画布绝不会仅仅因为后台正在推理就卡顿。

<p align="center">
  <img src="docs/readme/canvas-compare.png" alt="在 SugarSubstitute 画布中对比文生图结果与 Face Detailer 结果" width="680">
  <br>
  <em>分屏视图左侧显示原始文生图结果，右侧显示经过 Face Detailer 处理的结果。</em>
</p>

## 小地方也应该好用

测试版还包括批量和连续生成、可重新排序的队列、实时预览、输出网格和对比、可复用的控件与提示词预设、多个工作流标签页、Photoshop 交接、Danbooru 标签工具、可配置的输出路径、Cube Pack 管理、ComfyUI 诊断，以及导出回 ComfyUI 工作流 JSON。

这张清单很长，因为不起眼的打断积少成多。我希望应用能在你开口之前，就先让开挡路的位置。

## 许可证

SugarSubstitute 是**自由及开放源代码软件（FOSS）**，依据 **[GNU 通用公共许可证 v3.0 或更高版本](https://www.gnu.org/licenses/gpl-3.0.html)**发布。

## 致谢

SugarSubstitute 建立在无数人的杰出工作之上。我真心感谢他们每一位。

- **ComfyUI：** 我要向 [comfyanonymous](https://github.com/comfyanonymous)、[Comfy Org](https://github.com/Comfy-Org) 以及所有为 [ComfyUI](https://github.com/Comfy-Org/ComfyUI) 做出贡献的人致以深深的感谢。ComfyUI 是让 SugarSubstitute 成为可能的引擎和开放工作流生态。正因为它足够灵活，我才能打造一种不同的工作方式，又不限制任何人的创作边界。
- **ComfyUI Prompt Control：** 感谢 [asagi4](https://github.com/asagi4) 和 [ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control) 的贡献者。他们完成了 ComfyUI 高级提示词编辑和 LoRA 控制背后的艰苦工作，让 SugarSubstitute 能把这些强大能力带进自己的编辑器。
- **PySide6-Fluent-Widgets 和 QFramelessWindow：** [zhiyiYo](https://github.com/zhiyiYo) 以及 [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) 和 [QFramelessWindow](https://github.com/zhiyiYo/PyQt-Frameless-Window) 的贡献者，多年来一直用心打磨 Qt 应用在各个平台上的质感。SugarSubstitute 能更像一款真正的桌面应用，正是因为有他们的成果可供构建。
- **CivitAI：** 感谢 [CivitAI](https://civitai.com/) 团队认真对待这个值得好好支持的模型生态。他们的 API 帮助 SugarSubstitute 把模型与人们使用模型所需的信息连接起来；宽松的托管方式给了创作者自由分享的空间；价格亲民的按需算力，也让没有昂贵 GPU 的人能创造更多东西。
- **Danbooru：** [Danbooru](https://danbooru.donmai.us/) 团队和社区建立了一套异常用心的图像描述共享语言。他们的 API 让这些知识能在 SugarSubstitute 中发挥作用，但真正珍贵的，是人们至今仍不断投入到标签的整理、记录与完善之中。
- **Qt：** 最后，感谢 [The Qt Company](https://www.qt.io/) 带来 Qt 和 PySide6。它们让我能够打造自己一直想要的 SugarSubstitute：响应迅速、原生、跨平台的创作应用。

## 来自开发者 💖

我打造 SugarSubstitute，是因为我希望 ComfyUI 的强大能力也能变成一个真正待得住的地方。愿它让你少花点时间照看连线，多花点时间去创造那些奇怪又可爱的东西。

- **请我喝杯咖啡：** 你可以在我的 [Ko-fi 页面](https://ko-fi.com/artificial_sweetener)支持更多这样的项目。
- **我的网站与社交账号：** 在 [artificialsweetener.ai](https://artificialsweetener.ai) 看我的艺术、诗歌和其他开发动态。
- **如果你喜欢这个项目，** 能在 GitHub 上给我点一颗星，我会非常开心！！⭐
