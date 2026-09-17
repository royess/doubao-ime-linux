# doubao-ime-linux

[English](README.md) | **简体中文**

[![CI](https://github.com/royess/doubao-ime-linux/actions/workflows/ci.yml/badge.svg)](https://github.com/royess/doubao-ime-linux/actions/workflows/ci.yml)
[下载 Release](https://github.com/royess/doubao-ime-linux/releases)

官方豆包 Windows 键盘引擎的实验性 Fcitx 5 桥接，附带可选的官方设置窗口与语音输入。

**0.1.0-rc.1 · 源码预发布版 · 非官方项目 · Linux x86_64**

将豆包 Windows 输入法 **0.9.0.0** 的键盘引擎接入 Fcitx 5。候选词由官方引擎生成，
预编辑、候选框和文字提交由 Fcitx 处理。支持常用拼音、选词、分段转换、退格与取消；
官方设置窗口可用于配置已验证的全拼、双拼、五笔和繁简选项。

这是版本固定的兼容实验。**不能视为 Windows 豆包输入法的完整 Linux 移植。**
语音和外观页面、账号同步、部分官方快捷键尚未接通；详见 [设置边界](docs/settings.md)。

```text
按键 → Fcitx 原生插件 → 本地 socket → Wine RPC 宿主 → 官方豆包引擎
            ← 预编辑、候选词、提交 ←

可选语音：Linux 录音 → 外部 ASR 适配器 → 豆包语音服务
                                    → Fcitx 焦点校验 → 文字提交
```

## 依赖

核心需要 Fcitx 5 开发文件、json-c、CMake、C++17 编译器、Python 3.11+、
64 位 Wine、Xvfb 和 x86_64 MinGW-w64 C 编译器。设置额外需要 Wine Mono **11.3.0**
和 Noto Sans CJK SC 字体。桌面安装示例使用 systemd 用户服务。

发行版包名、提取工具和可替换路径见 [安装说明](docs/install.md)。
没有自动下载或执行第三方安装器的脚本；官方 EXE/DLL、字体、Wine 和账号数据均不在源码包中。

## 构建与准备

以下命令在源码目录执行。保留这个目录：启动入口会引用它。

```sh
cp config.example.json config.local.json
# 如依赖不在 PATH，编辑 config.local.json 填入对应工具的绝对路径。
cmake -S . -B build/fcitx
cmake --build build/fcitx -j2
python3 scripts/build_windows.py

python3 scripts/prepare.py extract --installer /path/to/DoubaoIME_Installer_0.9.0.0_release.exe
python3 scripts/prepare.py init
```

提取工具必须支持 Inno Setup 6.7；脚本校验官方安装包及 RPC DLL 的 SHA-256，
拒绝其他版本。`init` 使用自己的虚拟显示和全新 Wine prefix，不导入现有账号或词库。

需要官方设置窗口时，使用如下准备命令；它也会检查键盘运行环境：

```sh
python3 scripts/prepare.py init --settings \
  --mono-msi /path/to/wine-mono-11.3.0-x86.msi \
  --font /path/to/NotoSansCJK-Regular.ttc
```

## 安装到当前用户

```sh
# 不需要设置窗口时，去掉 --settings。
python3 scripts/install.py install --settings --dry-run
python3 scripts/install.py install --settings
systemctl --user daemon-reload
systemctl --user enable --now doubao-keyboard.service
```

重新启动 Fcitx 5，在 Fcitx 配置工具中添加「豆包 / Doubao」。安装脚本不自动重启
Fcitx，不更改默认输入法，不修改桌面快捷键，遇到已有同名文件会停止。

- 键盘：空格或数字选词，`-` 上一页、`=` 下一页，Esc 取消；中英文切换由 Fcitx 配置管理。
- 设置：安装时带上 `--settings`，切换到豆包后，可从 Waybar 等托盘中的 Fcitx 菜单点击「豆包设置」（需要 `gio`）。
- 设置：应用菜单打开「豆包输入法设置（官方）」或运行 `doubao-settings`；**关闭窗口后应用键盘变更**。
  原生设置仅部分适配：全拼、繁简、小鹤双拼、自然码和 86 五笔已有验证；翻页键、候选数量及排列由 Linux 桥接代码控制，Windows 外观和语音设置未映射。完整范围见[设置说明](docs/settings.md)。
- 语音：是可选组件，需单独配置外部适配器，见 [语音说明](docs/voice.md)。
  可在豆包语音附加组件中启用右 Alt 长按说话、松开提交，以及右 Alt + 空格持续录音。

如果桌面不支持 systemd 用户服务，可在自己的会话管理器中启动 `doubao-keyboard`。
设置窗口关闭后，非 systemd 管理的引擎需自行停止再应用配置；当前自动应用只支持项目的用户服务。

## 验证与卸载

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/doctor.py

# 需要已准备的运行环境；仅在此源码目录的键盘服务停止时执行。
python3 scripts/headless.py --prefix keyboard -- python3 tests/integration_keyboard.py
python3 scripts/headless.py --prefix keyboard -- \
  dbus-run-session -- python3 tests/integration_fcitx.py
```

普通单元测试不运行 Wine、不接触桌面、不录音或联网。集成测试使用独立显示和 D-Bus，
原始运行记录写入被忽略的 `work/`。已验证范围见 [验证记录](docs/validation.md)。

```sh
systemctl --user disable --now doubao-keyboard.service
# 若曾启用语音，也先停止并禁用 doubao-voice.service。
python3 scripts/install.py uninstall
systemctl --user daemon-reload
```

随后从 Fcitx 配置中移除豆包并重新启动 Fcitx。卸载只移除安装清单内未被另行修改的文件，
保留 `work/` 中的运行环境、设置和凭据。不要在服务运行时移动源码目录。

## 发布范围

本仓库仅发布桥接源码、构建工具、测试和文档。MIT 许可与第三方边界见
[LICENSE](LICENSE) 和 [THIRD_PARTY.md](THIRD_PARTY.md)。
官方引擎可能联网，语音识别会发送录音到云端；详见 [数据与运行边界](docs/privacy.md)。

接口记录：[keyboard-abi.md](docs/keyboard-abi.md)。
本地打包：`python3 scripts/package.py`；产物在 `dist/`，文件范围由 `RELEASE_FILES.txt` 明确列出。

## 自动测试与发布

每次向 `main` 推送、提交 Pull Request 或手动运行 Actions 时，CI 会自动进行：

- GCC 和 Clang 编译，带语音及仅键盘两种构建，以及 MinGW Windows 宿主编译。
- 单元测试、暂存安装/卸载与 systemd 单元语法检查。
- 私有 Xvfb + D-Bus 环境中的真实 Fcitx/GTK 输入和语音提交保护检查。
- 源码清单、双语 README 本地链接、源码包内容和可重复打包检查。

CI 使用固定响应的模拟键盘引擎，**不代表官方豆包引擎或云端 ASR 的在线兼容性测试**。
官方安装包、账号、凭据和录音不进入 CI。已有官方引擎实测记录见 [验证记录](docs/validation.md)。

推送与 `VERSION` 一致的 `v*` 标签，会先运行完整 CI，再自动生成 GitHub Release，
附上源码包和 `SHA256SUMS`。`-rc` 标签标记为预发布。维护步骤见 [发布说明](docs/release.md)。
