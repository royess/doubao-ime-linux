import sys
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import json
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
spec = importlib.util.spec_from_file_location('settings',Path(__file__).resolve().parents[1]/'bridge/settings.py')
settings=importlib.util.module_from_spec(spec);spec.loader.exec_module(settings)

class SettingsMergeTest(unittest.TestCase):
    def setUp(self):
        self.before={'keyboard':{'keyboardType_v3':'pinyin','defaultTraditional':False},
                     'voice':{'voiceShortcutMode':'right_alt_space'},'unknown':{'keep':1}}

    def test_merge_retains_external_edits_and_non_keyboard_state(self):
        after=copy.deepcopy(self.before);after['keyboard']['keyboardType_v3']='shuangpin'
        after['voice']['voiceShortcutMode']='custom'
        current=copy.deepcopy(self.before);current['keyboard']['defaultTraditional']=True
        merged,changes=settings.merge_keyboard(self.before,after,current)
        self.assertEqual(changes,{'keyboardType_v3':'shuangpin'})
        self.assertTrue(merged['keyboard']['defaultTraditional'])
        self.assertEqual(merged['voice'],self.before['voice'])
        self.assertEqual(merged['unknown'],{'keep':1})

    def test_conflicting_keyboard_change_is_rejected(self):
        after=copy.deepcopy(self.before);after['keyboard']['keyboardType_v3']='shuangpin'
        current=copy.deepcopy(self.before);current['keyboard']['keyboardType_v3']='wubi'
        with self.assertRaises(ValueError):settings.merge_keyboard(self.before,after,current)

    def test_wrong_type_is_rejected(self):
        after=copy.deepcopy(self.before);after['keyboard']['defaultTraditional']='true'
        with self.assertRaises(ValueError):settings.merge_keyboard(self.before,after,self.before)

    def test_unknown_new_option_does_not_replace_existing_schema(self):
        after=copy.deepcopy(self.before);after['keyboard']['futureOption']=True
        self.assertEqual(settings.merge_keyboard(self.before,after,self.before)[1],{})

    def test_atomic_file_is_private_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'config.json';settings.write_config(p,self.before)
            self.assertEqual(settings.read_config(p),self.before)
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertEqual(len(list(Path(tmp).iterdir())),1)

    def test_uninstalled_checkout_cannot_manage_existing_service(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings,'STATE',Path(tmp)):
            self.assertFalse(settings.owns_service())

    def test_only_matching_installed_unit_is_owned(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings,'STATE',Path(tmp)):
            root=Path(tmp);unit=root/'doubao-keyboard.service';unit.write_text('test service')
            record={'root':str(settings.ROOT),'files':{str(unit):hashlib.sha256(unit.read_bytes()).hexdigest()}}
            (root/'install-manifest.json').write_text(json.dumps(record))
            with patch.object(settings.subprocess,'run',return_value=SimpleNamespace(stdout=str(unit)+'\n')):
                self.assertTrue(settings.owns_service())
                unit.write_text('different installation')
                self.assertFalse(settings.owns_service())

if __name__=='__main__':unittest.main()
