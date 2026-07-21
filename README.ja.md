<p align="center">
  <img src="docs/readme/sugarsubstitute-logo.svg" alt="SugarSubstitute：ComfyUI のネイティブ Qt フロントエンド" width="680">
</p>

<p align="center">
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/releases"><img src="https://img.shields.io/github/v/release/Artificial-Sweetener/SugarSubstitute?include_prereleases" alt="最新リリース"></a>
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/Artificial-Sweetener/SugarSubstitute/release.yml?branch=main&label=Tests" alt="テスト状況"></a>
  <a href="https://github.com/Artificial-Sweetener/SugarSubstitute/releases"><img src="https://img.shields.io/github/downloads/Artificial-Sweetener/SugarSubstitute/total" alt="リリースのダウンロード数"></a>
  <a href="https://www.gnu.org/licenses/gpl-3.0.html"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue" alt="GPL-3.0-or-later ライセンス"></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-Hans.md">简体中文</a> | <strong>日本語</strong> | <a href="README.ko.md">한국어</a>
</p>

**SugarSubstitute は [ComfyUI](https://github.com/Comfy-Org/ComfyUI) のための Qt フロントエンドです。グラフにできることは大好き。でも一日中その配線をほどいていたくはない——そんな人のために作りました。**

同じワークフローのまとまりを何度も作り、オンとオフを切り替え、場所を動かし、また配線し直す。そんなことを繰り返して、とうとう嫌になりました。そのまとまりが [**Cubes**](https://github.com/Artificial-Sweetener/SugarCubes) になり、それを囲むデスクトップアプリが SugarSubstitute になりました。

**SugarSubstitute は現在パブリックベータです。** Windows x64、Apple Silicon、Linux x64 それぞれに専用インストーラーがあります。

Windows x64、Apple Silicon、Linux x64 向けの**[最新ベータ版をダウンロード](#インストール)**できます。

次に作りたいものは[ロードマップ](ROADMAP.md)にまとめています。足りないものがあれば、ぜひ教えてください。

<p align="center">
  <img src="docs/readme/sugarsubstitute-workspace.png" alt="再利用可能な Cubes、プロンプト操作、生成結果を備えた SugarSubstitute ワークスペース" width="900">
  <br>
  <em>メインワークスペースには、Cube スタック、プロンプト、生成コントロール、最新の出力がひとつにまとまっています。</em>
</p>

## ひとことで言うと

- **積み上げるのは、ばらばらのノードではなくワークフローの部品。** Cubes の追加、並べ替え、ミュート、削除だけで、接続は SugarSubstitute が引き受けます。
- **WebUI の対応を待たない。** ComfyUI で動くモデルなら、Cube を使って SugarSubstitute に持ち込めます。ComfyUI のグラフを組めるなら、Cube も作れます。
- **すべてのワークフローを一度に更新。** アップスケールのやり方を変えるべきだと気づいた？ 新しいインペイント手法が出てきた？ 該当部分の Cube だけを更新すれば、Substitute の全ワークフローがまとめて追従します。
- **同じことを何度もしない。** シード、サンプラー、そのほか互換性のある設定は一度変えるだけ。ワークフロー中を探し回る必要はありません。
- **画像生成のために生まれたリッチなプロンプトエディター。** オートコンプリート、リッチ表示、LoRA、ワイルドカード、強調、シーン、ドラッグできるセグメントが、ひとつのエディターに揃っています。
- **モデルは目で選ぶ。** ファイル名の山を掘る代わりに、サムネイルとメタデータを検索できます。
- **画像のそばで作業する。** 読み込み、マスク、生成、比較、結果の開き直しまで、ツール間を行ったり来たりせずに済みます。
- **レシピを丸ごと共有。** レシピ PNG には、ワークフロー、プロンプト、設定に加え、不足しているモデルを安全に見つけ直すための情報まで入れられます。

## 動いている SugarSubstitute を見る

<p align="center">
  <a href="https://www.youtube.com/watch?v=wfamuJZCD2c">
    <img src="docs/readme/youtube-beta-preview.png" alt="YouTube で SugarSubstitute ベータ版の紹介を見る" width="720">
  </a>
  <br>
  <em>プレビューをクリックすると、YouTube で SugarSubstitute ベータ版の紹介を見られます。</em>
</p>

## ベータです。遠慮なくつついてください。

SugarSubstitute はパブリックベータです。私は実際の制作に使っていますが、まだ粗いところはあるはずです。セットアップに失敗した、クラッシュした、あるいは普通の操作なのに妙にやりづらい——そんなときは、何をしていたかと SugarSubstitute が出した診断情報を添えて、[issue を作成](https://github.com/Artificial-Sweetener/SugarSubstitute/issues)してください。

**ハードウェア対応について：** 私は NVIDIA ハードウェアで開発と推論を行っています。マネージドセットアップには、対応する AMD および Intel GPU、Apple MPS、Windows での CPU のみの推論向けの経路もありますが、それらの構成はまだ自分では試せていません。試した方は、正確なハードウェアと OS、セットアップが完了したか、生成できたかを教えてください。成功報告も大切です。報告がない状態と完璧に動いている状態は、こちらから見ると困ったことに同じです。

## インストール

セットアップでは、マネージド ComfyUI 環境を新しく作ることも、すでに使っている環境へ接続することもできます。マネージドセットアップは、チェックサムで検証された独立 Python 環境とプロセス内 libgit2 クライアントを使うため、システムの Python や Git は必要ありません。初回起動では必要なものをダウンロードするため、少し時間がかかることがあります。気長に見守ってください。

**すでにインストール済みですか？** いつもどおり SugarSubstitute を開いてください。起動時に、通常は一日一回、アプリの更新を確認し、新しいバージョンを自動的にインストールします。ふつうはインストーラーをもう一度ダウンロードする必要はありません。

### <img src="docs/release/platforms/windows.svg" width="22" height="22" alt=""> Windows x64

**[最新の Windows x64 インストーラーをダウンロード](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Windows-x64.exe)**

インストーラーを実行し、`C:\SugarSubstitute` のような、通常の書き込み可能なフォルダーを選んでください。Program Files は避けてください。Windows のアクセス権がセットアップや更新を妨げる場合があります。

マネージドセットアップは、NVIDIA では CUDA、対応する AMD RDNA ハードウェアでは ROCm、Intel GPU では XPU を利用し、CPU フォールバックも備えています。Windows での AMD アクセラレーションは、マネージドランタイムが対応する RDNA 3、RDNA 3.5、RDNA 4 ファミリーに限られます。それ以外の AMD ハードウェアでは、互換性のない環境に賭ける代わりに CPU へフォールバックします。

次へ：[SugarSubstitute で ComfyUI をどう使うか選ぶ](#comfyui-のセットアップ方法を選ぶ)。

### <img src="docs/release/platforms/apple.svg" width="22" height="22" alt=""> macOS Apple Silicon

**[最新の macOS Apple Silicon インストーラーをダウンロード](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-macOS-Apple-Silicon.dmg)**

DMG を開いて SugarSubstitute Setup を起動し、既定の `~/Applications/SugarSubstitute` フォルダーか、自分が所有する別のフォルダーを選びます。マネージドセットアップは Apple Silicon で Apple の MPS アクセラレーションを使います。Intel Mac はサポートしていません。

このプロジェクトは Apple の有料 Developer Program に参加していないため、SugarSubstitute はアドホック署名されていますが、公証はされていません。macOS は開発元を確認できないという警告を表示します。このリポジトリから DMG をダウンロードした場合は、macOS の「プライバシーとセキュリティ」設定から開くことを許可してください。

私が SugarSubstitute を直接テストしているのは Windows だけです。macOS パッケージは GitHub Actions により Apple Silicon 上でビルドされていますが、実機の Mac で使ってくれる方がまだまだ必要です。

次へ：[SugarSubstitute で ComfyUI をどう使うか選ぶ](#comfyui-のセットアップ方法を選ぶ)。

### <img src="docs/release/platforms/linux.svg" width="22" height="22" alt=""> Linux x64

お使いのシステムに合うパッケージを選んでください：

- **[最新の Linux x86_64 AppImage をダウンロード](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Linux-x86_64.AppImage)**：ポータブルインストーラーです。実行可能に設定してから起動してください。
- **[最新の Linux amd64 Debian パッケージをダウンロード](https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest/download/SugarSubstitute-Installer-Linux-amd64.deb)**：Debian、Ubuntu、および関連ディストリビューション向けです。パッケージをインストールしてから `sugarsubstitute-setup` を実行してください。

既定のインストールフォルダーは `~/.local/share/SugarSubstitute` です。マネージドセットアップは、NVIDIA では CUDA、AMD では ROCm、Intel GPU では XPU を利用します。現在、Linux 向けのマネージド CPU 専用環境はありません。

私が SugarSubstitute を直接テストしているのは Windows だけです。Linux パッケージは GitHub Actions により Linux 上でビルドされていますが、実際のディストリビューションやデスクトップ環境で使ってくれる方がまだまだ必要です。

次へ：[SugarSubstitute で ComfyUI をどう使うか選ぶ](#comfyui-のセットアップ方法を選ぶ)。

### Git クローンから実行

リポジトリから SugarSubstitute を直接実行し、変更も加えたい場合は、ソースをチェックアウトしてください。この方法には Git と Python 3.12 が必要です。

Windows では PowerShell を開き、次を実行します：

```powershell
git clone https://github.com/Artificial-Sweetener/SugarSubstitute.git
Set-Location SugarSubstitute
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest pytest-xdist ruff mypy pre-commit
.\.venv\Scripts\pre-commit.exe install
.\.venv\Scripts\python.exe main.py
```

macOS または Linux ではターミナルを開き、次を実行します：

```bash
git clone https://github.com/Artificial-Sweetener/SugarSubstitute.git
cd SugarSubstitute
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt pytest pytest-xdist ruff mypy pre-commit
.venv/bin/pre-commit install
.venv/bin/python main.py
```

ソースから初めて起動すると、パッケージ版と同じセットアップ画面が開きます。マネージド ComfyUI 環境を作るか、既存の環境へ接続してください。セットアップ後は、開発用チェックアウトを実行したいときに最後のコマンドをもう一度使います。

### ComfyUI のセットアップ方法を選ぶ

SugarSubstitute は初回起動時に ComfyUI の使い方を尋ねます。接続は後から「設定」で変更できます。

#### SugarSubstitute に ComfyUI をセットアップさせる

ほとんどの方には、こちらをおすすめします。SugarSubstitute が専用のローカル ComfyUI ワークスペースを作成し、ハードウェアに適した推論バックエンドを選び、ComfyUI Manager と必要なカスタムノードをインストールします。この ComfyUI はアプリと一緒に起動・終了します。マネージド環境は、すでに使っている ComfyUI 環境とは分けて保たれます。システムの Python と Git は不要です。

ComfyUI 環境全体を SugarSubstitute に任せ、いつでも使える状態に保ちたい方はこちらを選んでください。

#### 既存のローカル ComfyUI を使う

既存の ComfyUI `main.py` があるフォルダーを選びます。SugarSubstitute はリポジトリとモデルをその場所に保ったまま、Python 依存関係、ComfyUI Manager、必要なカスタムノードを含め、その ComfyUI 環境を SugarSubstitute 向けに準備します。その後、アプリの実行中は SugarSubstitute がこの ComfyUI を起動します。

ローカル ComfyUI をひとつにまとめたい方で、SugarSubstitute がその環境を準備・起動することに問題がなければ、こちらを選んでください。

#### リモート ComfyUI に接続する

リモート ComfyUI 対応はまだテストされていません。SugarSubstitute はリモートのホストとポートを保存しますが、リモートマシン上でインストールや修復はできません。信頼できる LAN または VPN 経由でサーバーへ接続し、ComfyUI を公開インターネットへ直接さらさないでください。

接続前に、リモート ComfyUI 環境へ次のカスタムノードと、それぞれが宣言している Python 依存関係をインストールしてください：

- [Substitute BackEnd](https://github.com/Artificial-Sweetener/Substitute-BackEnd)
- [SugarCubes](https://github.com/Artificial-Sweetener/SugarCubes)
- [ComfyUI Vectorscope CC](https://github.com/pamparamm/ComfyUI-vectorscope-cc)
- [ComfyUI SeedVR2 Video Upscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler)
- [SimpleSyrup](https://github.com/Artificial-Sweetener/SimpleSyrup)
- [ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control)

ノードをインストールしたらリモート ComfyUI サーバーを再起動し、SugarSubstitute のセットアップ画面でホストとポートを入力してください。

## Cubes。ケーブルスパゲッティではなく

Cube は、入力、出力、コントロールが明示された、バージョン付きの ComfyUI グラフ部品です。必要な Cubes を積み上げれば、SugarSubstitute が互換性のある端点を接続します。並べ替え、ミュート、削除をしても、接続は新しいスタックに合わせて収まります。小さなグラフ手術を始める必要はありません。

表に出すネイティブコントロールは Cube の作者が決めます。グローバルオーバーライドを使えば、複数の Cubes にある互換設定をひとつのツールバーコントロールへ集められます。必要になれば、より深いコントロールも表示できます。

Cube の作者はパックを GitHub で公開でき、ユーザーは変更を購読できます。Cube が変わったら、信頼するバージョンを固定することも、互換性のある値と接続を引き継いで更新することもできます。

## WebUI が追いつくのを待たない

SugarSubstitute は ComfyUI に馴染みのある WebUI 風インターフェースを与えながら、新しいモデル対応をフロントエンドのリリース待ちにしません。ComfyUI で動くものなら、SugarSubstitute は Cube を通じて表に出せます。既存の Cube を使っても、自分で作ってもかまいません。ComfyUI のグラフを組めるなら、Cube も作れます。モデル対応は UI の都合ではなく、ワークフローと一緒に届きます。

## プロンプトは生きていてほしい

プロンプトエディターは、表示している構造を理解しています。入力中の位置にオートコンプリートが現れ、その下では強調、LoRA、ワイルドカード、句読点、選択、取り消しの状態が崩れません。カンマで区切ったパーツは、折り返した行をまたいでドラッグしたり、キーボードで動かしたりすることもできます。

<p align="center">
  <img src="docs/readme/prompt-editor-showcase.gif" alt="リッチ表示、オートコンプリート、強調、ドラッグ可能なプロンプトセグメントを備えた SugarSubstitute プロンプトエディター" width="720" height="720">
  <br>
  <em>エスケープ規則を暗記させず、マウスから手を離さずにさっと直せるプロンプトエディターです。</em>
</p>

## 画像に覚えておいてもらう

SugarSubstitute のレシピ PNG には、読みやすい Sugar レシピと生の ComfyUI ワークフローの両方が入っています。開けば、Cube スタックとバージョン、公開値、グローバルオーバーライド、シードの挙動、プロンプト、同じ実行で作られた対応画像を復元できます。

……とはいえ、Comfy や WebUI を使ってきた方なら、このくらいの便利さには慣れているでしょう。なので、もう一歩進めます：

参照モデルが移動していたら、SugarSubstitute はローカルライブラリから同じ SHA-256 を探し、パスを修復します。完全に同じモデルがなく、そのハッシュを CivitAI が知っていれば、安全性を確認したダウンロードを提案できます。Substitute を使っている友人に結果を共有すれば、そのレシピを試すために必要なモデルを各自で取得できます。

## ファイル名ではなく、顔でモデルを選ぶ

互換性のある ComfyUI モデルフィールドは、検索可能なビジュアルピッカーになります。サムネイルとわかりやすい名前を眺め、ファイル名やフォルダーで検索し、モデルの読み込み状況を追い、対応する CivitAI ページを開き、LoRA メタデータからトリガーワードを直接プロンプトへ入れられます。

新しいモデルを適切な ComfyUI モデルフォルダーへ置けば、SugarSubstitute が自動的に検出します。ライブラリのお守りをしなくても、ピッカーへ自然に加わります。

<p align="center">
  <img src="docs/readme/model-picker.png" alt="検索可能な Anima 拡散モデルをサムネイル付きで表示する SugarSubstitute モデルピッカー" width="720">
  <br>
  <em>モデルピッカーは ComfyUI フォルダーを検索可能なビジュアルグリッドに変えます。画像のないモデルも、サムネイル付きの項目と並んで利用できます。</em>
</p>

サムネイルとオンラインメタデータは任意です。プロバイダーへのアクセス、API キー、コンテンツポリシーは自分で管理できます。

## 画像を手元に置く

ネイティブキャンバスは、ソース画像、マスク、プレビュー、最終出力にふさわしい作業場所を用意します。カーソル位置の細部へズームし、マスクを描くかスマート選択を使い、結果を比較し、使いやすい場所へキャンバスをドッキングしたりフローティングしたりできます。

Substitute のキャンバスは [QPane](https://github.com/Artificial-Sweetener/QPane) で作られ、すべて CPU 上で動きます。画像生成中の GPU には、もっと大事な仕事があることをお互い知っていますから。バックグラウンドで推論しているだけでキャンバスが引っかかることはありません。

<p align="center">
  <img src="docs/readme/canvas-compare.png" alt="SugarSubstitute キャンバスで Text to Image の結果と Face Detailer の結果を比較" width="680">
  <br>
  <em>分割表示では、左に元の Text to Image 結果、右に Face Detailer を通した結果を並べて比較しています。</em>
</p>

## 小さなところだって、気持ちよくていい

ベータ版にはほかにも、バッチ生成と連続生成、並べ替え可能なキュー、ライブプレビュー、出力グリッドと比較、再利用可能なコントロールとプロンプトのプリセット、複数のワークフロータブ、Photoshop への受け渡し、Danbooru タグツール、設定可能な出力先、Cube Pack 管理、ComfyUI 診断、ComfyUI ワークフロー JSON への書き戻しがあります。

長い一覧になったのは、小さな中断も積み重なるからです。頼まれる前に、アプリのほうから邪魔にならないでほしいと思っています。

## ライセンス

SugarSubstitute は**フリーかつオープンソースのソフトウェア（FOSS）**で、**[GNU General Public License v3.0 以降](https://www.gnu.org/licenses/gpl-3.0.html)**の下で配布されています。

## 謝辞

SugarSubstitute は、たくさんの人たちによる途方もない仕事の上に成り立っています。心から感謝しています。

- **ComfyUI：** [comfyanonymous](https://github.com/comfyanonymous)、[Comfy Org](https://github.com/Comfy-Org)、そして [ComfyUI](https://github.com/Comfy-Org/ComfyUI) に貢献するすべての方へ、最大限の感謝を伝えたいです。ComfyUI は SugarSubstitute を可能にするエンジンであり、開かれたワークフローエコシステムです。その柔軟性があるからこそ、人の創作を制限せずに、別の作業方法を作れます。
- **ComfyUI Prompt Control：** [asagi4](https://github.com/asagi4) と [ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control) の貢献者に感謝します。ComfyUI における高度なプロンプト編集と LoRA 制御という難しい仕事を成し遂げ、SugarSubstitute が自分のエディターへ持ち込める強力な挙動を与えてくれました。
- **PySide6-Fluent-Widgets と QFramelessWindow：** [zhiyiYo](https://github.com/zhiyiYo)、そして [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) と [QFramelessWindow](https://github.com/zhiyiYo/PyQt-Frameless-Window) の貢献者は、Qt アプリを各プラットフォームで上質に感じさせるため、長年にわたり丁寧な仕事を重ねてきました。その成果があったからこそ、SugarSubstitute は本物のデスクトップアプリらしく感じられます。
- **CivitAI：** モデルのエコシステムを、きちんと支える価値のあるものとして扱っている [CivitAI](https://civitai.com/) チームに感謝します。API は SugarSubstitute がモデルと、そのモデルを使うために必要な情報を結びつける助けになります。寛容なホスティングは作者が共有できる余地を生み、手頃なオンデマンド計算資源は、高価な GPU がなくてもより多くの人がものを作れるようにしてくれます。
- **Danbooru：** [Danbooru](https://danbooru.donmai.us/) のチームとコミュニティは、画像を説明するための、ひときわ思慮深い共通言語を築き上げました。API によってその知識を SugarSubstitute の中で活用できますが、本当の贈り物は、タグの整理、文書化、洗練へ今も注がれ続ける心配りです。
- **Qt：** 最後に、Qt と PySide6 を提供する [The Qt Company](https://www.qt.io/) に感謝します。私が欲しかった、応答性が高く、ネイティブで、クロスプラットフォームなクリエイティブアプリとして SugarSubstitute を作れるのは、この技術のおかげです。

## 開発者より 💖

ComfyUI の力を、心から「ここで作業していたい」と思える場所にしたくて、SugarSubstitute を作りました。配線の世話をする時間が少し減り、そのぶん妙で愛しいものを作る時間が増えますように。

- **コーヒーを一杯おごる：** [Ko-fi ページ](https://ko-fi.com/artificial_sweetener)から、こんなプロジェクトをもっと作るための燃料を送れます。
- **ウェブサイトと SNS：** 私のアート、詩、そのほかの開発情報は [artificialsweetener.ai](https://artificialsweetener.ai) で見られます。
- **このプロジェクトを気に入ったら、** GitHub でスターを付けてもらえると本当にうれしいです！！⭐
