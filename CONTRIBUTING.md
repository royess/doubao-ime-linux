# Contributing

Please include Linux distribution, Fcitx/Wine versions, official installer
SHA-256, reproduction steps and expected versus actual behavior.
Do not attach Wine prefixes, dictionaries, credentials, recordings, official
binaries or unredacted engine logs.

Run the unit tests and build both Fcitx modules. Changes to the keyboard ABI
also need the isolated keyboard/GTK tests; document the exact official version.
Settings changes need merge/conflict tests and a private settings-window check.

Keep desktop installation opt-in and reversible. Tests must use a private
display, private D-Bus session and this checkout's exclusive Wine prefixes.
Publishing is restricted to version tags after the reusable CI workflow passes.
Do not add runtime downloads or cloud credentials to normal tests.

When adding distributable source files, update `RELEASE_FILES.txt` and run
`python3 scripts/package.py --check`. New third-party code requires an explicit
license and attribution review before it is included.
