<p align="center">
  <img src="docs/readme/sugarsubstitute-logo.svg" alt="SugarSubstitute: ComfyUI용 네이티브 Qt 프런트엔드" width="680">
</p>

<p align="center">
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/releases"><img src="https://img.shields.io/github/v/release/Artificial-Sweetener/SugarSubstitute?include_prereleases" alt="최신 릴리스"></a>
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/Artificial-Sweetener/SugarSubstitute/release.yml?branch=main&label=Tests" alt="테스트 상태"></a>
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/releases"><img src="https://img.shields.io/github/downloads/Artificial-Sweetener/SugarSubstitute/total" alt="릴리스 다운로드 수"></a>
  <a href="https://www.gnu.org/licenses/gpl-3.0.html"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue" alt="GPL-3.0-or-later 라이선스"></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-Hans.md">简体中文</a> | <a href="README.ja.md">日本語</a> | <strong>한국어</strong>
</p>

**SugarSubstitute는 그래프의 가능성은 좋아하지만 하루 종일 복잡한 선을 풀고 싶지는 않은 사람을 위해 만든 [ComfyUI](https://github.com/Comfy-Org/ComfyUI)용 Qt 프런트엔드입니다.**

저는 똑같은 워크플로 구간을 계속 만들고, 켰다 껐다 하고, 위치를 옮긴 뒤 다시 연결하곤 했습니다. 결국 지쳐 버렸죠. 그 구간들이 [**큐브**](https://github.com/Artificial-Sweetener/SugarCubes)가 되었고, 그 주위에 만든 데스크톱 앱이 SugarSubstitute가 되었습니다.

**SugarSubstitute는 공개 베타 버전입니다.** Windows x64, Apple Silicon 및 Linux x64 전용 설치 프로그램을 제공합니다.

Windows x64, Apple Silicon 또는 Linux x64용 **[최신 베타를 다운로드하세요](#설치하기)**.

앞으로 만들고 싶은 기능은 [로드맵](ROADMAP.md)에서 확인할 수 있습니다. 빠진 것이 있다면 알려 주세요.

<p align="center">
  <img src="docs/readme/sugarsubstitute-workspace.png" alt="재사용 가능한 큐브, 프롬프트 컨트롤 및 생성 결과가 있는 SugarSubstitute 작업 공간" width="900">
  <br>
  <em>기본 작업 공간 하나에서 큐브 스택, 프롬프트, 생성 컨트롤과 최신 결과를 모두 다룰 수 있습니다.</em>
</p>

## 한눈에 보기

- **흩어진 노드 대신 워크플로 조각을 쌓으세요.** 큐브를 추가하고, 순서를 바꾸고, 음소거하거나 제거하면 SugarSubstitute가 연결을 처리합니다.
- **WebUI 지원을 기다리지 마세요.** ComfyUI에서 실행할 수 있는 모델이라면 큐브를 통해 SugarSubstitute로 가져올 수 있습니다. ComfyUI 그래프를 만들 수 있다면 큐브도 만들 수 있습니다.
- **모든 워크플로를 한 번에 업데이트하세요.** 업스케일링 방식을 바꿔야 한다는 걸 깨달았거나 새로운 인페인팅 기법이 나왔나요? 해당 구간의 큐브만 업데이트하면 모든 Substitute 워크플로가 함께 바뀝니다.
- **같은 일을 반복하지 마세요.** 워크플로 곳곳을 뒤지는 대신 시드, 샘플러 및 호환되는 설정을 한 번만 변경하세요.
- **이미지 생성에 꼭 맞춘 풍부한 프롬프트 편집기.** 자동 완성, 서식 있는 표시, LoRA, 와일드카드, 강조, 장면과 드래그 가능한 구간을 한 편집기에서 모두 사용할 수 있습니다.
- **눈으로 모델을 찾으세요.** 파일 이름만 늘어선 목록을 파헤치는 대신 썸네일과 메타데이터를 검색하세요.
- **이미지 곁에서 작업하세요.** 도구 사이를 오갈 필요 없이 불러오기, 마스킹, 생성, 비교와 결과 다시 열기를 할 수 있습니다.
- **레시피 전체를 공유하세요.** 레시피 PNG 하나에 워크플로, 프롬프트, 설정과 누락된 모델을 안전하게 복구할 충분한 정보를 담을 수 있습니다.

## 움직이는 SugarSubstitute 보기

<p align="center">
  <a href="https://www.youtube.com/watch?v=wfamuJZCD2c">
    <img src="docs/readme/youtube-beta-preview.png" alt="YouTube에서 SugarSubstitute 베타 소개 영상 보기" width="720">
  </a>
  <br>
  <em>미리 보기를 클릭하면 YouTube에서 SugarSubstitute 베타 소개 영상을 볼 수 있습니다.</em>
</p>

## 베타입니다. 마음껏 시험해 주세요.

SugarSubstitute는 공개 베타 버전입니다. 실제 작업에 사용하고 있지만 아직 다듬을 부분이 있으리라 생각합니다. 설정이 실패하거나, 앱이 충돌하거나, 평범한 작업이 이상할 정도로 어렵다면 무엇을 하던 중이었는지와 SugarSubstitute가 제공한 진단 정보를 함께 적어 [이슈를 열어 주세요](https://github.com/Artificial-Sweetener/SugarSubstitute/issues).

**하드웨어 지원 범위:** 저는 NVIDIA 하드웨어로 개발하고 추론합니다. 관리형 설정은 지원되는 AMD 및 Intel GPU, Apple MPS와 Windows의 CPU 전용 추론 경로도 제공하지만 이 하드웨어 구성은 직접 테스트하지 못했습니다. 사용해 보셨다면 정확한 하드웨어와 운영 체제, 설정 완료 여부와 생성 성공 여부를 알려 주세요. 성공했다는 보고도 중요합니다. 아무 말이 없는 것과 완벽하게 작동하는 것은 여기서 보면 놀랄 만큼 비슷하니까요.

## 설치하기

설정 과정에서 관리형 ComfyUI 환경을 만들거나 이미 사용하는 환경에 연결할 수 있습니다. 관리형 설정은 체크섬으로 검증된 독립형 Python 환경과 프로세스 내 libgit2 클라이언트를 사용하므로 시스템 Python이나 Git이 필요하지 않습니다. 처음 실행할 때 필요한 구성 요소를 다운로드하느라 시간이 걸릴 수 있습니다. 느긋하게 기다려 주세요.

**이미 설치했나요?** 평소처럼 SugarSubstitute를 여세요. 시작할 때 보통 하루에 한 번 애플리케이션 업데이트를 확인하고 새 버전을 자동으로 설치합니다. 일반적으로 설치 프로그램을 다시 다운로드할 필요가 없습니다.

### <img src="docs/release/platforms/windows.svg" width="22" height="22" alt=""> Windows x64

**[최신 Windows x64 설치 프로그램 다운로드](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Windows-x64.exe)**

설치 프로그램을 실행하고 `C:\SugarSubstitute`처럼 쓰기 가능한 일반 폴더를 선택하세요. Windows 권한 때문에 설정과 업데이트가 방해받을 수 있으므로 Program Files는 피하세요.

관리형 설정은 CUDA를 통한 NVIDIA, ROCm을 통한 지원 AMD RDNA 하드웨어, XPU를 통한 Intel GPU와 CPU 대체 실행을 지원합니다. Windows의 AMD 가속은 관리형 런타임이 지원하는 RDNA 3, RDNA 3.5 및 RDNA 4 하드웨어 제품군으로 제한됩니다. 그 밖의 AMD 하드웨어에서는 호환되지 않는 환경을 무리하게 사용하는 대신 CPU로 실행됩니다.

다음 단계: [SugarSubstitute에서 ComfyUI를 사용할 방법을 선택하세요](#comfyui-설정-선택).

### <img src="docs/release/platforms/apple.svg" width="22" height="22" alt=""> macOS Apple Silicon

**[최신 macOS Apple Silicon 설치 프로그램 다운로드](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-macOS-Apple-Silicon.dmg)**

DMG를 열고 SugarSubstitute Setup을 실행한 다음 기본 `~/Applications/SugarSubstitute` 폴더 또는 본인이 소유한 다른 폴더를 사용하세요. 관리형 설정은 Apple Silicon에서 Apple의 MPS 가속을 사용합니다. Intel Mac은 지원하지 않습니다.

이 프로젝트는 Apple의 유료 Developer Program에 참여하지 않기 때문에 SugarSubstitute는 임시 서명되어 있지만 공증되지는 않았습니다. macOS에서 개발자를 확인할 수 없다는 경고가 표시됩니다. 이 저장소에서 DMG를 다운로드했다면 macOS 개인정보 보호 및 보안 설정에서 열기를 허용하세요.

저는 Windows에서만 SugarSubstitute를 직접 테스트했습니다. macOS 패키지는 GitHub Actions를 통해 Apple Silicon에서 빌드되지만 실제 Mac에서 사용해 줄 분들이 더 필요합니다.

다음 단계: [SugarSubstitute에서 ComfyUI를 사용할 방법을 선택하세요](#comfyui-설정-선택).

### <img src="docs/release/platforms/linux.svg" width="22" height="22" alt=""> Linux x64

시스템에 맞는 패키지를 선택하세요.

- 휴대용 설치 프로그램이 필요하면 **[최신 Linux x86_64 AppImage를 다운로드하세요](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Linux-x86_64.AppImage)**. 실행 가능 파일로 표시한 다음 실행하세요.
- Debian, Ubuntu 및 관련 배포판에서는 **[최신 Linux amd64 Debian 패키지를 다운로드하세요](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Linux-amd64.deb)**. 패키지를 설치한 다음 `sugarsubstitute-setup`을 실행하세요.

기본 설치 폴더는 `~/.local/share/SugarSubstitute`입니다. 관리형 설정은 CUDA를 통한 NVIDIA, ROCm을 통한 AMD와 XPU를 통한 Intel GPU를 지원합니다. 현재 Linux에서는 관리형 CPU 전용 환경을 사용할 수 없습니다.

저는 Windows에서만 SugarSubstitute를 직접 테스트했습니다. Linux 패키지는 GitHub Actions를 통해 Linux에서 빌드되지만 실제 배포판과 데스크톱 환경에서 사용해 줄 분들이 더 필요합니다.

다음 단계: [SugarSubstitute에서 ComfyUI를 사용할 방법을 선택하세요](#comfyui-설정-선택).

### Git 클론에서 실행

저장소에서 직접 SugarSubstitute를 실행하고 수정하려면 소스 체크아웃을 사용하세요. 이 방법에는 Git과 Python 3.12가 필요합니다.

Windows에서 PowerShell을 열고 다음 명령을 실행하세요.

```powershell
git clone https://github.com/Artificial-Sweetener/SugarSubstitute.git
Set-Location SugarSubstitute
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest pytest-xdist ruff mypy pre-commit
.\.venv\Scripts\pre-commit.exe install
.\.venv\Scripts\python.exe main.py
```

macOS 또는 Linux에서 터미널을 열고 다음 명령을 실행하세요.

```bash
git clone https://github.com/Artificial-Sweetener/SugarSubstitute.git
cd SugarSubstitute
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt pytest pytest-xdist ruff mypy pre-commit
.venv/bin/pre-commit install
.venv/bin/python main.py
```

소스에서 처음 실행하면 패키지 애플리케이션과 같은 설정 과정이 열립니다. 관리형 ComfyUI 환경을 만들거나 기존 환경에 연결하세요. 설정 후에는 개발 체크아웃을 실행할 때마다 마지막 명령을 다시 사용하면 됩니다.

### ComfyUI 설정 선택

SugarSubstitute를 처음 열면 ComfyUI를 사용할 방법을 묻습니다. 나중에 설정에서 연결을 변경할 수 있습니다.

#### SugarSubstitute에서 ComfyUI 설정

대부분의 사용자에게 권장하는 옵션입니다. SugarSubstitute가 별도의 로컬 ComfyUI 작업 공간을 만들고, 하드웨어에 맞는 추론 백엔드를 선택하고, ComfyUI Manager와 필요한 사용자 지정 노드를 설치한 뒤, 애플리케이션과 함께 이 설치를 시작하고 중지합니다. 이미 사용 중인 ComfyUI 설정과 관리형 환경은 서로 분리됩니다. 시스템 Python과 Git은 필요하지 않습니다.

SugarSubstitute가 전체 ComfyUI 환경을 관리하고 언제든 사용할 수 있게 유지하기를 원한다면 이 옵션을 선택하세요.

#### 기존 로컬 ComfyUI 사용

기존 ComfyUI의 `main.py`가 있는 폴더를 선택하세요. SugarSubstitute는 저장소와 모델을 그대로 유지하면서 Python 종속성, ComfyUI Manager 및 필요한 사용자 지정 노드를 포함해 해당 ComfyUI 환경을 준비합니다. 이후 애플리케이션이 실행되는 동안 이 설치를 시작합니다.

로컬 ComfyUI 설치 하나를 사용하고 SugarSubstitute에서 이를 준비하고 실행해도 괜찮다면 이 옵션을 선택하세요.

#### 원격 ComfyUI에 연결

원격 ComfyUI 지원은 아직 테스트되지 않았습니다. SugarSubstitute는 원격 호스트와 포트를 저장하지만 원격 컴퓨터에 어떤 것도 설치하거나 복구할 수 없습니다. 신뢰할 수 있는 LAN 또는 VPN을 통해 서버에 연결하고 ComfyUI를 공용 인터넷에 직접 노출하지 마세요.

연결하기 전에 원격 ComfyUI 환경에 다음 사용자 지정 노드와 이들이 선언한 Python 종속성을 설치하세요.

- [Substitute BackEnd](https://github.com/Artificial-Sweetener/Substitute-BackEnd)
- [SugarCubes](https://github.com/Artificial-Sweetener/SugarCubes)
- [ComfyUI Vectorscope CC](https://github.com/pamparamm/ComfyUI-vectorscope-cc)
- [ComfyUI SeedVR2 Video Upscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler)
- [SimpleSyrup](https://github.com/Artificial-Sweetener/SimpleSyrup)
- [ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control)

노드를 설치한 후 원격 ComfyUI 서버를 다시 시작하고 SugarSubstitute 설정에 호스트와 포트를 입력하세요.

## 케이블 스파게티 대신 큐브

큐브는 입력, 출력과 컨트롤이 선언된 ComfyUI 그래프의 버전 관리 단위입니다. 필요한 큐브를 쌓으면 SugarSubstitute가 호환되는 엔드포인트를 연결합니다. 큐브 하나의 순서를 바꾸거나, 음소거하거나, 제거해도 작은 그래프 연결을 일일이 손보지 않아도 새 스택에 맞춰 연결이 정리됩니다.

큐브 작성자는 화면에 표시할 네이티브 컨트롤을 결정합니다. 전역 재정의를 사용하면 여러 큐브의 호환되는 설정을 도구 모음 컨트롤 하나에 모을 수 있으며, 필요할 때 더 깊은 컨트롤을 다시 표시할 수도 있습니다.

큐브 작성자는 팩을 GitHub에 게시할 수 있고 사용자는 변경 사항을 구독할 수 있습니다. 큐브가 바뀌면 신뢰하는 버전을 고정하거나 호환되는 값과 연결을 유지한 채 업데이트하세요.

## WebUI가 따라오기를 기다리지 마세요

SugarSubstitute는 새로운 모델 지원이 프런트엔드 릴리스를 기다리지 않도록 ComfyUI에 익숙한 WebUI 방식의 인터페이스를 제공합니다. ComfyUI에서 실행할 수 있다면 SugarSubstitute에서 큐브를 통해 표시할 수 있습니다. 기존 큐브를 사용하거나 직접 만드세요. ComfyUI 그래프를 만들 수 있다면 큐브도 만들 수 있습니다. 모델 지원은 UI가 따라잡을 때가 아니라 워크플로와 함께 도착합니다.

## 살아 있는 듯한 프롬프트

프롬프트 편집기는 자신이 표시하는 구조를 이해합니다. 입력 중인 위치에 자동 완성이 나타나면서도 그 아래의 강조, LoRA, 와일드카드, 문장 부호, 선택 영역과 실행 취소 상태는 그대로 유지됩니다. 쉼표로 나눈 조각을 줄바꿈된 줄 사이로 끌거나 키보드로 옮길 수도 있습니다.

<p align="center">
  <img src="docs/readme/prompt-editor-showcase.gif" alt="서식 있는 표시, 자동 완성, 강조와 드래그 가능한 프롬프트 구간을 보여 주는 SugarSubstitute 프롬프트 편집기" width="720" height="720">
  <br>
  <em>이스케이프 규칙을 외우게 만들지 않고, 마우스에서 손을 떼지 않아도 빠르게 수정할 수 있는 프롬프트 편집기입니다.</em>
</p>

## 이미지가 기억하게 하세요

SugarSubstitute 레시피 PNG에는 사람이 읽을 수 있는 Sugar 레시피와 원본 ComfyUI 워크플로가 함께 담깁니다. 파일을 열면 큐브 스택과 버전, 노출된 값, 전역 재정의, 시드 동작, 프롬프트와 같은 실행에서 생성된 지원 형식의 관련 이미지를 복원합니다.

...하지만 Comfy나 WebUI를 사용해 왔다면 이 정도 편리함에는 익숙할 테니 한 단계 더 나아갑니다.

참조된 모델이 이동했다면 SugarSubstitute가 로컬 라이브러리에서 같은 SHA-256을 찾아 경로를 복구합니다. 정확한 모델이 없고 CivitAI에서 해시를 알고 있다면 SugarSubstitute가 안전성을 확인한 다운로드를 제안할 수 있습니다. Substitute를 사용하는 친구와 결과를 공유하면 친구도 직접 시험하는 데 필요한 모델을 내려받을 수 있습니다.

## 파일 이름 대신 얼굴로 보는 모델

호환되는 ComfyUI 모델 필드는 검색 가능한 시각적 선택기로 바뀝니다. 썸네일과 읽기 쉬운 이름을 둘러보고, 파일 이름이나 폴더로 검색하고, 모델 불러오기 진행 상황을 확인하고, 일치하는 CivitAI 페이지를 열고, LoRA 메타데이터의 트리거 단어를 프롬프트에 바로 넣을 수 있습니다.

새 모델을 적절한 ComfyUI 모델 폴더에 넣으면 SugarSubstitute가 자동으로 감지합니다. 라이브러리를 일일이 돌보지 않아도 선택기에 추가됩니다.

<p align="center">
  <img src="docs/readme/model-picker.png" alt="시각적 썸네일과 함께 검색 가능한 Anima 확산 모델을 보여 주는 SugarSubstitute 모델 선택기" width="720">
  <br>
  <em>모델 선택기는 ComfyUI 폴더를 검색 가능한 시각적 그리드로 바꾸며, 이미지가 없는 모델도 썸네일이 있는 항목과 함께 계속 사용할 수 있습니다.</em>
</p>

썸네일과 온라인 메타데이터는 선택 사항입니다. 제공자 접근, API 키와 콘텐츠 정책은 사용자가 직접 제어합니다.

## 이미지를 가까이 두세요

네이티브 캔버스는 원본 이미지, 마스크, 미리 보기와 최종 출력에 제대로 된 작업 공간을 제공합니다. 커서 아래의 세부 정보를 확대하고, 마스크를 칠하거나 스마트 선택을 사용하고, 결과를 비교하고, 유용한 위치에 캔버스를 도킹하거나 분리하세요.

Substitute의 캔버스는 [QPane](https://github.com/Artificial-Sweetener/QPane)으로 만들어졌으며 CPU에서만 실행됩니다. 이미지를 생성 중이라면 GPU에 훨씬 중요한 할 일이 있다는 걸 우리 둘 다 아니까요. 백그라운드에서 추론을 실행한다고 캔버스가 버벅이는 일은 없습니다.

<p align="center">
  <img src="docs/readme/canvas-compare.png" alt="SugarSubstitute 캔버스에서 Text to Image 결과와 Face Detailer 결과 비교" width="680">
  <br>
  <em>분할 보기에서 왼쪽의 원본 Text to Image 결과와 오른쪽의 Face Detailer 처리 결과를 비교합니다.</em>
</p>

## 작은 부분도 멋져도 됩니다

베타에는 배치 및 연속 생성, 순서를 바꿀 수 있는 대기열, 실시간 미리 보기, 출력 그리드와 비교, 재사용 가능한 컨트롤 및 프롬프트 프리셋, 여러 워크플로 탭, Photoshop 전달, Danbooru 태그 도구, 구성 가능한 출력 경로, 큐브 팩 관리, ComfyUI 진단과 ComfyUI 워크플로 JSON으로 다시 내보내는 기능도 있습니다.

작은 방해도 쌓이면 커지기 때문에 목록이 깁니다. 사용자가 요구하기도 전에 애플리케이션이 작업을 방해하지 않게 되기를 바랍니다.

## 라이선스

SugarSubstitute는 **자유 및 오픈 소스 소프트웨어(FOSS)**이며 **[GNU 일반 공중 사용 허가서 v3.0 이상](https://www.gnu.org/licenses/gpl-3.0.html)**에 따라 배포됩니다.

## 감사의 말

SugarSubstitute는 수많은 사람의 놀라운 작업 위에 서 있습니다. 모든 분께 진심으로 감사드립니다.

- **ComfyUI:** [comfyanonymous](https://github.com/comfyanonymous), [Comfy Org](https://github.com/Comfy-Org)와 [ComfyUI](https://github.com/Comfy-Org/ComfyUI)에 기여하는 모든 분께 깊이 감사드립니다. ComfyUI는 SugarSubstitute를 가능하게 하는 엔진이자 개방형 워크플로 생태계입니다. 그 유연성 덕분에 사람들이 만들 수 있는 것을 제한하지 않으면서도 새로운 작업 방식을 만들 수 있었습니다.
- **ComfyUI Prompt Control:** [asagi4](https://github.com/asagi4)와 [ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control) 기여자 여러분께 감사드립니다. ComfyUI의 고급 프롬프트 편집과 LoRA 제어라는 어려운 작업을 해 주신 덕분에 SugarSubstitute 편집기에도 강력한 기능을 담을 수 있었습니다.
- **PySide6-Fluent-Widgets 및 QFramelessWindow:** [zhiyiYo](https://github.com/zhiyiYo)와 [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets), [QFramelessWindow](https://github.com/zhiyiYo/PyQt-Frameless-Window) 기여자 여러분은 여러 플랫폼에서 Qt 애플리케이션을 완성도 높게 느껴지도록 오랜 시간 정성을 쏟았습니다. 그 작업을 바탕으로 만들 수 있었기에 SugarSubstitute가 진짜 데스크톱 애플리케이션처럼 느껴집니다.
- **CivitAI:** 모델 생태계를 지원할 가치가 있는 것으로 여겨 주는 [CivitAI](https://civitai.com/) 팀에 감사드립니다. API는 SugarSubstitute가 모델과 사용에 필요한 정보를 연결하도록 돕고, 관대한 호스팅은 제작자가 공유할 여지를 주며, 저렴한 주문형 컴퓨팅은 값비싼 GPU가 없어도 더 많은 사람이 무언가를 만들 수 있게 합니다.
- **Danbooru:** [Danbooru](https://danbooru.donmai.us/) 팀과 커뮤니티는 이미지를 설명하는 데 쓸 수 있는 놀라울 만큼 세심한 공용 언어를 만들었습니다. API 덕분에 SugarSubstitute 안에서 그 지식을 활용할 수 있지만, 진정한 선물은 태그를 정리하고 문서화하고 다듬는 데 사람들이 계속 쏟는 정성입니다.
- **Qt:** 마지막으로 Qt와 PySide6를 만든 [The Qt Company](https://www.qt.io/)에 감사드립니다. 덕분에 제가 바라던 반응이 빠르고 네이티브이며 여러 플랫폼에서 작동하는 창작 애플리케이션 SugarSubstitute를 만들 수 있습니다.

## 개발자로부터 💖

저는 ComfyUI의 강력함이 실제로 머물며 작업할 수 있는 공간처럼 느껴지기를 바라서 SugarSubstitute를 만들었습니다. 선을 돌보는 시간은 줄이고 낯설고 사랑스러운 무언가를 만드는 시간은 더 늘어나기를 바랍니다.

- **커피 한 잔 사 주기**: 제 [Ko-fi 페이지](https://ko-fi.com/artificial_sweetener)에서 이런 프로젝트를 더 만들 수 있도록 힘을 보태 주세요.
- **웹사이트 및 소셜**: [artificialsweetener.ai](https://artificialsweetener.ai)에서 제 작품, 시와 다른 개발 소식을 볼 수 있습니다.
- **이 프로젝트가 마음에 든다면** GitHub에서 별을 눌러 주시면 정말 큰 힘이 됩니다! ⭐
