import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from check_package import validate_archive


class SourceArchive(unittest.TestCase):
    def make(self, root, members):
        archive = root/'source.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            for name, data, kind in members:
                entry = tarfile.TarInfo('doubao-ime-linux-0.1.0-rc.1/'+name)
                entry.mode = 0o644
                entry.type = kind
                entry.size = len(data)
                stream.addfile(entry, io.BytesIO(data))
        return archive

    def test_exact_source_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=self.make(Path(temp), [('README.md',b'hello',tarfile.REGTYPE)])
            validate_archive(archive, {'README.md':b'hello'}, '0.1.0-rc.1')

    def test_extra_missing_duplicate_and_modified_members_are_rejected(self):
        cases = [
            [('README.md',b'hello',tarfile.REGTYPE),('private.json',b'{}',tarfile.REGTYPE)],
            [],
            [('README.md',b'hello',tarfile.REGTYPE)]*2,
            [('README.md',b'other',tarfile.REGTYPE)],
            [('../README.md',b'hello',tarfile.REGTYPE)],
            [('README.md',b'',tarfile.SYMTYPE)],
        ]
        with tempfile.TemporaryDirectory() as temp:
            for case in cases:
                with self.subTest(members=case), self.assertRaises(ValueError):
                    validate_archive(self.make(Path(temp),case), {'README.md':b'hello'}, '0.1.0-rc.1')


if __name__=='__main__':unittest.main()
