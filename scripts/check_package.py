#!/usr/bin/env python3
"""Check archive fidelity and README links; optionally rebuild for reproducibility."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from urllib.parse import unquote, urlsplit
from package import ROOT, sources


def validate_archive(archive, expected, version):
    prefix = 'doubao-ime-linux-' + version + '/'
    seen = set()
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream:
            if not member.isfile() or not member.name.startswith(prefix):
                raise ValueError('Unexpected archive member: ' + member.name)
            name = member.name[len(prefix):]
            if name in seen or name not in expected:
                raise ValueError('Duplicate or unlisted archive member: ' + name)
            if member.size != len(expected[name]) or member.mode != 0o644:
                raise ValueError('Unexpected file metadata: ' + name)
            if member.mtime != 0 or member.uid != 0 or member.gid != 0:
                raise ValueError('Non-reproducible metadata: ' + name)
            if stream.extractfile(member).read() != expected[name]:
                raise ValueError('Archive differs from source: ' + name)
            seen.add(name)
    if seen != set(expected): raise ValueError('Archive is missing reviewed source files')


def readme_links():
    for name in ('README.md', 'README.zh-CN.md'):
        text = (ROOT/name).read_text()
        for target in re.findall(r'\]\(([^\s)]+)\)', text):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path: continue
            path = (ROOT/unquote(parsed.path)).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError(f'Broken local link in {name}: {target}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rebuild', action='store_true')
    args = parser.parse_args()
    version = (ROOT/'VERSION').read_text().strip()
    name = 'doubao-ime-linux-' + version + '.tar.gz'
    archive = ROOT/'dist'/name
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if (ROOT/'dist/SHA256SUMS').read_text() != digest+'  '+name+'\n':
        raise ValueError('Archive checksum mismatch')
    validate_archive(archive, dict(sources()), version)
    readme_links()
    if args.rebuild:
        subprocess.run([sys.executable, str(ROOT/'scripts/package.py')], check=True)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise ValueError('Rebuilding changed the source archive')
    print('PASS source archive, checksums and bilingual README links' +
          ('; reproducible rebuild' if args.rebuild else ''))


if __name__ == '__main__': main()
