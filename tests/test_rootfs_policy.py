import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('rootfs_policy', Path(__file__).resolve().parents[1] / 'tools/rootfs-policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class RootfsPolicyTests(unittest.TestCase):
    def test_default_policy_preserves_stock_and_is_idempotent(self):
        fstab = '# keep\nUUID=root / ext4 defaults,commit=600,errors=remount-ro 0 1\nUUID=boot /boot ext4 defaults,commit=600 0 1\n'
        stock = 'LABEL Stock\n  APPEND ${bootargs} ${boot_user_args}\n'
        boot = 'LABEL Default\n  APPEND ${bootargs} ${boot_user_args}\n' + stock
        fs, cfg = policy.transform(fstab, boot)
        self.assertNotIn('commit=600', fs)
        self.assertEqual(fs.count('commit=5'), 2)
        self.assertIn('${boot_user_args} rootflags=data=ordered', cfg)
        self.assertTrue(cfg.endswith(stock))
        self.assertEqual(policy.transform(fs, cfg), (fs, cfg))

    def test_unknown_boot_layout_or_mount_policy_is_rejected(self):
        fs = 'UUID=root / ext4 defaults 0 1\n'
        for boot in ('LABEL Custom\n APPEND root=/dev/test\n', 'LABEL Default\n APPEND rootflags=noload\n'):
            with self.assertRaises(ValueError):
                policy.transform(fs, boot)
        with self.assertRaises(ValueError):
            policy.transform(fs.replace('defaults', 'data=journal'), 'LABEL Default\n APPEND root=/dev/test\n')
