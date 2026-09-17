"""Stage all entry points under a temporary prefix; never start services."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
with tempfile.TemporaryDirectory(prefix='doubao-install-') as temporary:
    area=Path(temporary)
    files=installer.plan(area/'prefix with spaces',area/'units',voice=True,settings=True)
    manifest=area/'manifest.json'
    installer.apply(files,manifest)
    for path,(data,mode) in files.items():
        assert path.read_bytes()==data
        assert path.stat().st_mode&0o777==mode
    units=[str(path) for path in files if path.suffix=='.service']
    subprocess.run(['systemd-analyze','--user','verify',*units],check=True)
    unrelated=area/'retained-state';unrelated.write_text('retain')
    installer.remove(manifest)
    assert not any(path.exists() for path in files)
    assert unrelated.read_text()=='retain'
    from runtime import STATE
    STATE.mkdir(parents=True,exist_ok=True)
    (STATE/'install-stage.json').write_text(json.dumps({'passed':True,'file_count':len(files),
        'spaces_in_prefix':True,'unit_validation':True,'uninstall_retained_state':True},indent=2)+'\n')
    print('PASS staged installation, service unit syntax and removal:',len(files),'files')
