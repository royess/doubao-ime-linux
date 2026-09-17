#!/usr/bin/env python3
"""Reproducible source archive from an explicit, reviewed file allowlist."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import re
import tarfile

ROOT=Path(__file__).resolve().parents[1]
TOP={'README.md','README.zh-CN.md','LICENSE','THIRD_PARTY.md','CHANGELOG.md','CONTRIBUTING.md',
     'VERSION','RELEASE_FILES.txt','.gitignore','CMakeLists.txt','config.example.json'}
DIRECTORIES={'bridge','fcitx5','scripts','tests','docs','.github'}
SUFFIXES={'.py','.c','.cs','.cpp','.h','.md','.conf','.yml','.yaml'}


def sources():
    names=(ROOT/'RELEASE_FILES.txt').read_text().splitlines()
    if not names or len(set(names))!=len(names):raise ValueError('Empty or duplicate release manifest')
    if not TOP.issubset(names):raise ValueError('Required release metadata is missing')
    result=[]
    for name in names:
        path=Path(name)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe release path: '+name)
        if name not in TOP and (path.parts[0] not in DIRECTORIES or path.suffix not in SUFFIXES):
            raise ValueError('Disallowed release file: '+name)
        source=ROOT/path
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise ValueError('Missing or linked source: '+name)
        data=source.read_bytes(); text=data.decode('utf-8')
        if len(data)>250000:raise ValueError('Unexpected large source: '+name)
        patterns=[r'/(?:home|Users)/[^\s/]+/',r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
                  'ba'+'ge', '\u53ed\u54e5']
        if any(re.search(pattern,text,re.I) for pattern in patterns):
            raise ValueError('Private path, unrelated project or credential marker: '+name)
        result.append((name,data))
    # New source files must be explicitly reviewed instead of silently omitted.
    candidates={p.relative_to(ROOT).as_posix() for directory in DIRECTORIES
                for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in SUFFIXES}
    if candidates-set(names):raise ValueError('Unlisted source files: '+', '.join(sorted(candidates-set(names))))
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    files=sources();version=(ROOT/'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-rc\.[0-9]+)?',version):raise ValueError('Invalid version')
    if args.check:print(f'PASS: {len(files)} reviewed source files');return
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    name='doubao-ime-linux-'+version
    target=output/(name+'.tar.gz')
    with target.open('wb') as stream, gzip.GzipFile(filename='',fileobj=stream,mode='wb',mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for path,data in sorted(files):
                entry=tarfile.TarInfo(name+'/'+path)
                entry.size=len(data);entry.mode=0o644;entry.mtime=0
                entry.uid=entry.gid=0;entry.uname=entry.gname=''
                archive.addfile(entry,io.BytesIO(data))
    checksum=hashlib.sha256(target.read_bytes()).hexdigest()
    (output/'SHA256SUMS').write_text(checksum+'  '+target.name+'\n')
    print(f'{target.name}: {len(files)} source files, {target.stat().st_size} bytes')
    print('SHA-256 '+checksum)


if __name__=='__main__':main()
