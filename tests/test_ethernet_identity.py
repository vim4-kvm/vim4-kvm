import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
generator=load('ethernet_generator','board/vim4-ethernet-generator.py')
runtime=load('ethernet_runtime','packaging/kernel-edge/register-runtime.py')


class EthernetIdentityTests(unittest.TestCase):
    def test_generator_entry_completes_link_before_consumers_with_systemd_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cmdline=root/'cmdline';network=root/'network'
            cmdline.write_text('vim4.full_kvm=1 vim4.eth_mac=00:12:34:56:78:9a')
            # Exercise the actual generator entry point with systemd's three
            # output-directory arguments; redirect only its filesystem inputs.
            source=(ROOT/'board/vim4-ethernet-generator.py').read_text()
            source=source.replace("Path('/proc/cmdline')",'Path('+repr(str(cmdline))+')')
            source=source.replace("Path('/run/systemd/network')",'Path('+repr(str(network))+')')
            executable=root/'generator.py';executable.write_text(source)
            subprocess.run([sys.executable,str(executable),str(root/'normal'),
                            str(root/'early'),str(root/'late')],check=True)
            # The caller may now load/start udev and NM. No asynchronous work
            # is needed to make the network configuration visible to them.
            self.assertIn('MACAddress=00:12:34:56:78:9a\n',
                          (network/'10-vim4-ethernet.link').read_text())

    def test_distinct_factory_addresses_are_used_before_network_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for mac in ('00:12:34:56:78:9a','10:ab:cd:ef:01:23'):
                generator.generate('root=test vim4.full_kvm=1 vim4.eth_mac='+mac,root)
                link=(root/'10-vim4-ethernet.link').read_text()
                self.assertIn('MACAddress='+mac+'\n',link)
                self.assertIn('Path=platform-fdc00000.ethernet\n',link)
                self.assertIn('MACAddressPolicy=none\n',link)
                self.assertNotIn('Address=',link.replace('MACAddress=',''))

    def test_missing_invalid_or_duplicate_identity_does_not_write_a_link(self):
        for value in ('','vim4.eth_mac=','vim4.eth_mac=${eth_mac}','vim4.eth_mac=00:00:00:00:00:00',
                      'vim4.eth_mac=01:23:45:67:89:ab',
                      'vim4.eth_mac=00:12:34:56:78:9a vim4.eth_mac=10:ab:cd:ef:01:23'):
            with self.subTest(value=value),tempfile.TemporaryDirectory() as temp:
                target=Path(temp)/'network'
                with self.assertRaises(ValueError):generator.generate('vim4.full_kvm=1 '+value,target)
                self.assertFalse(target.exists())

    def test_vendor_boot_is_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'network'
            generator.generate('root=test mac=00:12:34:56:78:9a',target)
            self.assertFalse(target.exists())

    def test_boot_profile_uses_dynamic_efuse_variable_and_preserves_other_labels(self):
        full=runtime.boot_profile({'APPEND':'root=test'},framebuffer_console=True)
        self.assertIn('vim4.eth_mac=${eth_mac}',full['APPEND'].split())
        old={**full,'APPEND':full['APPEND'].replace(' vim4.eth_mac=${eth_mac}','')}
        text='default FullKvm\nLABEL Default\n APPEND vendor=keep\nLABEL FullKvm\n APPEND '+old['APPEND']+'\n'
        upgraded=runtime.update_boot_entry(text,old,None,full)
        self.assertIn('default FullKvm\n',upgraded)
        self.assertIn('LABEL Default\n APPEND vendor=keep\n',upgraded)
        self.assertIn('vim4.eth_mac=${eth_mac}',upgraded)
        self.assertEqual(runtime.update_boot_entry(upgraded,full,None,full),upgraded)
