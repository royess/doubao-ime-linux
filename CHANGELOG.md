# Changelog

## Unreleased

- Distinct blue-and-white 豆 tray icon and matching settings launcher icon.

## 0.1.0-rc.1

First source preview for the official DoubaoIME 0.9.0.0 keyboard engine on Fcitx 5.

- Native candidate/preedit UI, selection, segmented conversion and focus reset.
- Configurable Wine/Xvfb/MinGW paths and verified installer extraction.
- Separate official settings runtime with keyboard-only configuration merging.
- Optional Linux dictation coordinator and independent Fcitx delivery endpoint.
- User-level installation manifest, collision checks, rollback and removal.
- Private-display integration checks and an explicit source-package file list.
- Separate English and Chinese READMEs.
- GCC/Clang CI with mock-engine Fcitx/GTK tests and reproducible archive checks.
- Tagged GitHub Releases gated by the complete CI workflow.

Experimental release: fixed upstream ABI, incomplete Windows settings parity,
external ASR adapter required for voice, and no bundled official components.
