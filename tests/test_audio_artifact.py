"""Old/silently misordered HDMI units must not pass package/image validation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audio_check', ROOT / 'packaging/ubuntu/check-audio-startup.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class AudioArtifactTests(unittest.TestCase):
    def test_current_unit_and_missing_or_late_route(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            units = root / 'usr/lib/systemd/system'
            units.mkdir(parents=True)
            wrapper = root / 'usr/libexec/vim4-board-runtime'
            wrapper.parent.mkdir(parents=True)
            wrapper.write_bytes((ROOT / 'board/vim4-board-runtime').read_bytes())
            wrapper.chmod(0o755)
            hdmi = (ROOT / 'board/vim4-kvm-hdmi.service').read_text()
            (units / 'nanokvm.service').write_text('[Unit]\nAfter=vim4-kvm-hdmi.service\n')
            path = units / 'vim4-kvm-hdmi.service'
            path.write_text(hdmi)
            checker.check(root)
            for bad in (
                '\n'.join(line for line in hdmi.splitlines() if not line.startswith('ExecStartPre=')),
                hdmi.replace('ExecStartPre=', 'ExecStartPost='),
                hdmi.replace(' alsa-restore.service', ''),
                hdmi.replace('audio-route', 'wrong-route'),
                hdmi.replace('Type=notify', 'Type=simple'),
            ):
                with self.subTest(unit=bad):
                    path.write_text(bad)
                    with self.assertRaises(ValueError):
                        checker.check(root)


if __name__ == '__main__':
    unittest.main()
