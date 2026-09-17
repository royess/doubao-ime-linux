# 安装依赖与路径配置

支持目标是 Linux x86_64 + Fcitx 5。首先确认 Fcitx 本身能在应用内输入文字。
其他输入法框架、ARM 和完整跨发行版支持不属于本次验证范围。

## 发行版依赖

Arch Linux 对应包通常为 `fcitx5`、`json-c`、`cmake`、`base-devel`、`python`、
`wine`、`xorg-server-xvfb`、`mingw-w64-gcc`。语音需要 `python-gobject`、
`libpulse` 客户端工具、`opus`，以及可用的 PulseAudio 或 PipeWire-Pulse 会话。
设置字体包为 `noto-fonts-cjk`。

Debian/Ubuntu 可参考 `libfcitx5core-dev`、`libfcitx5utils-dev`、`fcitx5-modules-dev`、`libjson-c-dev`、
`cmake`、`g++`、`python3`、`wine`、`xvfb`、`gcc-mingw-w64-x86-64`；
可选 `python3-gi`、`pulseaudio-utils`、`libopus0`、`fonts-noto-cjk`。
这些包名仅供定位依赖，未宣称在所有发行版版本上完成安装测试。
模块开发包可参考 [Ubuntu 包目录](https://packages.ubuntu.com/noble/fcitx5-modules-dev)。

## 提取官方安装包

固定的安装包名：`DoubaoIME_Installer_0.9.0.0_release.exe`。
SHA-256：`610b8bf696835b5c4bad654b87de8695dfa808bc57aa900bcc7603e06f427f7f`。
请通过官方渠道自行获取；仓库不托管该文件。

旧版 innoextract 可能无法解包 Inno Setup 6.7。已使用并核对的实现是
[innoextract_win](https://github.com/UserUnknownFactor/innoextract_win/tree/e561d8cb6004776eecb3184c0d56b3534a0c7e15)：

```sh
git clone https://github.com/UserUnknownFactor/innoextract_win.git /path/to/innoextract-src
git -C /path/to/innoextract-src checkout e561d8cb6004776eecb3184c0d56b3534a0c7e15
cmake -S /path/to/innoextract-src -B /path/to/innoextract-build
cmake --build /path/to/innoextract-build -j2
```

该工具的 Boost、liblzma 等依赖以其上游构建说明为准。将生成的 `innoextract`
绝对路径写入 `config.local.json` 的 `innoextract` 字段。

## 可配置项

`config.local.json` 是本机配置，不进入 Git 和源码包。默认值见 `config.example.json`。

| 字段 | 默认行为 |
|---|---|
| `wine` / `wineserver` | 从 PATH 查找；两者须属于同一 Wine 安装 |
| `xvfb` | 从 PATH 查找 Xvfb |
| `mingw_cc` | `x86_64-w64-mingw32-gcc`；也可指定兼容的 LLVM MinGW 编译器 |
| `innoextract` | 从 PATH 查找 |
| `state_dir` | 当前源码目录下 `work/`，必须是本项目独占的目录 |
| `wine_user` | 从独立 prefix 自动发现；只有存在多个用户目录时才需要指定 |
| `asr_entry` / `asr_no_proxy` | 可选语音适配器与直连域名列表 |

工具路径可由 `DOUBAO_WINE`、`DOUBAO_WINESERVER`、`DOUBAO_XVFB`、`DOUBAO_MINGW_CC`
覆盖。`DOUBAO_STATE_DIR` 覆盖状态目录。自定义状态目录也不要加入 Git。

设置使用 [Wine Mono 11.3.0 官方 MSI](https://github.com/wine-mono/wine-mono/releases/tag/wine-mono-11.3.0)，
SHA-256 `df2dfc1665c2511882e7cabd56eafd0c0a3d94e5a7e86f969277f6c189d418d3`。
只需 Noto Sans CJK SC，准备脚本不会复制系统 Windows 字体。

## 安装文件

默认写入 `~/.local/bin`、`~/.local/lib/fcitx5`、`~/.local/share/fcitx5`、
可选应用菜单入口和 `~/.config/systemd/user`。可用 `--prefix` 与 `--unit-dir` 做暂存安装。
安装清单位于状态目录 `install-manifest.json`。暂存安装也使用独立状态目录，
以免与正式安装的清单混用。

不需要语音提交插件时，可以 `cmake -DDOUBAO_BUILD_VOICE=OFF ...`。
官方键盘完全不依赖语音适配器、录音工具或语音服务。
