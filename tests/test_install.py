import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1]/'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Installation(unittest.TestCase):
    def test_existing_file_aborts_without_partial_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); old=root/'existing'; old.write_text('keep')
            files={root/'new':(b'new',0o644),old:(b'replace',0o644)}
            with self.assertRaises(RuntimeError): installer.apply(files,root/'manifest')
            self.assertEqual(old.read_text(),'keep');self.assertFalse((root/'new').exists())

    def test_modified_file_prevents_entire_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'manifest';a=root/'a';b=root/'b'
            installer.apply({a:(b'one',0o755),b:(b'two',0o644)},manifest)
            b.write_text('user edit')
            with self.assertRaises(RuntimeError):installer.remove(manifest)
            self.assertTrue(a.exists());self.assertEqual(b.read_text(),'user edit')
            b.write_text('two');installer.remove(manifest)
            self.assertFalse(a.exists());self.assertFalse(b.exists());self.assertFalse(manifest.exists())

    def test_failed_write_rolls_back_only_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'manifest';existing=root/'unrelated';existing.write_text('keep')
            real=installer.atomic
            def failing(path,data,mode):
                if path.name=='b':raise OSError('disk error')
                real(path,data,mode)
            with patch.object(installer,'atomic',side_effect=failing):
                with self.assertRaises(OSError):
                    installer.apply({root/'a':(b'a',0o644),root/'b':(b'b',0o644)},manifest)
            self.assertEqual(list(root.iterdir()),[existing])


if __name__=='__main__':unittest.main()
