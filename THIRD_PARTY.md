# Scope and attribution

The MIT license covers this repository's bridge, tools and documentation. It
does not license Doubao's proprietary engine, dictionaries, settings application,
trademarks, cloud services or independently installed dependencies.

This is an unofficial interoperability experiment. It is not affiliated with or
endorsed by ByteDance or Doubao. Users supply their own official installer.

| Dependency / reference | Use | Distribution in this source release |
|---|---|---|
| [Fcitx 5](https://github.com/fcitx/fcitx5) | Native input method and D-Bus module APIs | Not bundled; linked against the user's installation |
| [Wine](https://gitlab.winehq.org/wine/wine) | Runs the Windows keyboard engine | Not bundled |
| [Wine Mono](https://github.com/wine-mono/wine-mono/releases/tag/wine-mono-11.3.0) | Optional official settings UI | Not bundled |
| [Noto CJK](https://github.com/notofonts/noto-cjk) | Optional CJK font for settings | Not bundled; no Microsoft fonts included or required by setup |
| [MinGW-w64](https://www.mingw-w64.org/) | Builds the Windows RPC helper | Not bundled |
| [innoextract_win](https://github.com/UserUnknownFactor/innoextract_win/tree/e561d8cb6004776eecb3184c0d56b3534a0c7e15) | Extracts the Inno Setup 6.7 installer on Linux | Not bundled |
| [rime-winime](https://github.com/xdqi/rime-winime/tree/641ea31c2e8966bdd040fb459d2d2607005fd04c) | Architectural reference for Windows engine bridging | No source copied; this project uses Doubao RPC instead of IMM |
| [vinput-registry Doubao streaming adapter](https://github.com/xifan2333/vinput-registry/tree/38e203e328118e5575722d2d4dd74dd736b6c8d8/resources/providers/doubaoime/streaming) | Optional external ASR adapter | No adapter source, credentials or protocol implementation bundled |

The optional ASR adapter's separate redistribution permission has not been
confirmed. This release only includes our launcher for an adapter supplied by
the user; its code is not relicensed under MIT. The ASR protocol research and
adapter implementation belong to their upstream contributors.

Other runtime/build dependencies (Python, PyGObject, GTK, json-c, Xvfb, libopus,
PulseAudio client tools and system libraries) retain their respective licenses.
If producing binary packages, assess and preserve those dependencies' notices
separately; this repository currently distributes source only.
