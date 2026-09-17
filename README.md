# doubao-ime-linux

**English** | [简体中文](README.zh-CN.md)

[![CI](https://github.com/royess/doubao-ime-linux/actions/workflows/ci.yml/badge.svg)](https://github.com/royess/doubao-ime-linux/actions/workflows/ci.yml)
[Download releases](https://github.com/royess/doubao-ime-linux/releases)

An experimental Fcitx 5 bridge for the official Doubao Windows keyboard engine,
with an optional official settings window and optional voice input.

**0.1.0-rc.1 · Source preview · Unofficial · Linux x86_64**

The official **DoubaoIME 0.9.0.0** engine generates candidates; Fcitx handles the
preedit, candidate UI and text delivery. The bridge supports common Pinyin input,
candidate selection, segmented conversion, backspace and cancellation. The
official settings window can configure verified full Pinyin, double Pinyin,
Wubi and simplified/traditional Chinese options.

This experiment targets a fixed engine version. **It is not a complete Linux
port of the Windows input method.** Windows voice and appearance settings,
account synchronization and some shortcuts are not connected. See the
[settings limitations](docs/settings.md) for details (Chinese).

```text
Keys → native Fcitx addon → local socket → Wine RPC host → official Doubao engine
              ← preedit, candidates and committed text ←

Optional voice: Linux recording → external ASR adapter → Doubao speech service
                                                     → Fcitx focus checks → text
```

## Requirements

The core requires Fcitx 5 development files, json-c, CMake, a C++17 compiler,
Python 3.11+, 64-bit Wine, Xvfb and an x86_64 MinGW-w64 C compiler. The optional
settings window requires **Wine Mono 11.3.0** and the Noto Sans CJK SC font.
The desktop installation examples use systemd user services.

See the [installation notes](docs/install.md) for distribution package names,
extractor details and configurable paths (Chinese). Third-party installers are
not downloaded or executed automatically. Official EXE/DLL files, fonts, Wine
and account data are not included in the source archive.

## Build and prepare

Run these commands from the source directory. Keep that directory in place:
installed launchers refer to it.

```sh
cp config.example.json config.local.json
# Set absolute tool paths in config.local.json if dependencies are not in PATH.
cmake -S . -B build/fcitx
cmake --build build/fcitx -j2
python3 scripts/build_windows.py

python3 scripts/prepare.py extract --installer /path/to/DoubaoIME_Installer_0.9.0.0_release.exe
python3 scripts/prepare.py init
```

The extractor must support Inno Setup 6.7. The preparation tool verifies the
installer and RPC DLL SHA-256 hashes and rejects unsupported versions. `init`
uses a private display and fresh Wine prefix; it does not import existing
accounts or dictionaries.

To prepare the official settings window as well:

```sh
python3 scripts/prepare.py init --settings \
  --mono-msi /path/to/wine-mono-11.3.0-x86.msi \
  --font /path/to/NotoSansCJK-Regular.ttc
```

## Install for the current user

```sh
# Omit --settings if you do not need the settings window.
python3 scripts/install.py install --settings --dry-run
python3 scripts/install.py install --settings
systemctl --user daemon-reload
systemctl --user enable --now doubao-keyboard.service
```

Restart Fcitx 5 and add **Doubao / 豆包** in its configuration tool. The installer
does not restart Fcitx, change your default input method or assign desktop
shortcuts. It refuses to overwrite existing files with the same names.

- **Settings:** when installed with `--settings`, select Doubao and open “豆包设置” from the Fcitx tray menu in Waybar or another panel (requires `gio`).
- **Keyboard:** select with Space or a number, use `-` for the previous page and `=` for the next page, and
  cancel with Escape. Configure Chinese/English switching in Fcitx.
- **Settings:** run `doubao-settings` or open the Doubao settings application
  menu entry. **Keyboard changes apply when the window closes.**
  Only part of the native settings UI is supported: full pinyin, simplified/traditional
  output, Xiaohe and Ziranma double pinyin, and Wubi 86 have been verified. Paging
  keys, page size, and candidate layout are controlled by the Linux bridge;
  Windows appearance and voice settings are not mapped. See the
  [settings support notes](docs/settings.md) (Chinese) for details.
- **Voice:** optional; configure an external adapter as described in the
  [voice notes](docs/voice.md) (Chinese). You can also use an independent Fcitx
  voice addon alongside this keyboard bridge.
  Optional Right Alt shortcuts support hold-to-talk and Right Alt+Space for
  hands-free recording; enable them in the Doubao dictation addon configuration.

Without systemd user services, start `doubao-keyboard` using your own session
manager. Stop a manually managed engine before applying settings, then restart
it yourself; automatic stop/restart only manages this installation's user service.

## Verify and uninstall

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/doctor.py

# Requires a prepared runtime and this checkout's keyboard service to be stopped.
python3 scripts/headless.py --prefix keyboard -- python3 tests/integration_keyboard.py
python3 scripts/headless.py --prefix keyboard -- \
  dbus-run-session -- python3 tests/integration_fcitx.py
```

Unit tests do not launch Wine, use the desktop, record audio or access the
network. Integration tests use a private display and D-Bus session. Their logs
go to the ignored `work/` directory. See the [validation record](docs/validation.md).

```sh
systemctl --user disable --now doubao-keyboard.service
# Also stop and disable doubao-voice.service if you enabled it.
python3 scripts/install.py uninstall
systemctl --user daemon-reload
```

Remove Doubao from the Fcitx configuration and restart Fcitx. Uninstallation
removes only unchanged files recorded in the installation manifest; it retains
the runtime, settings and credentials in `work/`. Do not move the source
directory while its services are running.

## Automated tests and releases

Pushes to `main`, pull requests and manual workflow runs automatically check:

- GCC and Clang native builds, with voice enabled and keyboard-only builds,
  plus the MinGW Windows helpers.
- Unit tests, staged installation/removal and systemd unit syntax.
- Real Fcitx/GTK input and voice-delivery protections under private Xvfb/D-Bus.
- The source allowlist, local links in both READMEs, archive contents and
  reproducible packaging.

CI uses a deterministic mock keyboard engine. **It does not verify the official
Doubao engine or live cloud ASR compatibility.** CI needs no official installer,
account, credentials or recording. Separate official-engine checks are recorded
in the [validation notes](docs/validation.md).

Pushing a `v*` tag matching `VERSION` runs the complete CI suite before creating
a GitHub Release with the source archive and `SHA256SUMS`. Release-candidate tags
are marked as prereleases. See the [release procedure](docs/release.md).

## Scope and licensing

This repository distributes bridge source, build tools, tests and documentation.
See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md) for the MIT license,
attribution and the boundary with separately supplied components.

The official engine may access the network. Optional speech recognition sends
recordings to a cloud service. Wine prefixes are not security sandboxes. See
the [data and runtime notes](docs/privacy.md) for details (Chinese).

The verified interface is documented in [keyboard-abi.md](docs/keyboard-abi.md).
Run `python3 scripts/package.py` to produce a source archive in `dist/`;
`RELEASE_FILES.txt` explicitly lists every included file.
