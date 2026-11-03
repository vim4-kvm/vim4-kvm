"""The dated identity reaches make unchanged, without rebuilding a kernel."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT/'packaging/kernel'
spec = importlib.util.spec_from_file_location('kernel_release', RECIPE/'release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class KernelReleaseTest(unittest.TestCase):
    def lock(self, number=1):
        lock = tomllib.loads((RECIPE/'sources.toml').read_text())
        lock['package'].update(date='20261103', build=number,
                              tag='v7.3.1-vim4-20261103'+('' if number==1 else '.'+str(number)))
        return lock

    def test_date_and_same_day_builds_define_release_and_tag(self):
        for number in (1, 2, 10):
            contract = release.build_contract(self.lock(number))
            suffix = '-vim4-20261103'+('' if number==1 else '.'+str(number))
            self.assertEqual(contract['localversion'], suffix)
            self.assertEqual(contract['release'], '7.3.1'+suffix)
            self.assertEqual(contract['tag'], 'v'+contract['release'])

    def test_invalid_package_date_number_or_tag_is_rejected(self):
        for fields in (dict(date='20260230'),dict(date='2026113'),dict(build=0),dict(tag='vwrong')):
            lock=self.lock();lock['package'].update(fields)
            with self.subTest(fields=fields),self.assertRaises(ValueError):release.build_contract(lock)

    def test_validate_only_passes_localversion_and_empty_config_suffix_to_make(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();source=root/'source';source.mkdir();bin_dir=root/'bin';bin_dir.mkdir()
            (source/'Makefile').write_text('# fake source; make below models only the release boundary\n')
            subprocess.run(['git','init','-q',str(source)],check=True)
            subprocess.run(['git','-C',str(source),'add','Makefile'],check=True)
            subprocess.run(['git','-C',str(source),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
            revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
            scripts={
                'uname':'#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo aarch64;; esac\n',
                'date':'#!/bin/sh\necho locked-build-time\n',
                'realpath':'#!/usr/bin/env python3\nimport os,sys\nprint(os.path.abspath(sys.argv[-1]))\n',
                'make':'''#!/usr/bin/env python3
import json,os,re,sys
from pathlib import Path
with open(os.environ['TASK_MAKE_LOG'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[-1]=='olddefconfig':exit()
if sys.argv[-1]!='kernelrelease':raise RuntimeError('compilation is forbidden in this test')
output=Path(next(a[2:] for a in sys.argv if a.startswith('O=')))
config=re.search(r'^CONFIG_LOCALVERSION="(.*)"$',(output/'.config').read_text(),re.M)[1]
local=next((a.split('=',1)[1] for a in sys.argv if a.startswith('LOCALVERSION=')),'+')
print('7.3.1'+config+local)
'''}
            for name,body in scripts.items():p=bin_dir/name;p.write_text(body);p.chmod(0o755)
            for number in (1,2):
                lock=self.lock(number);lock['kernel']['revision']=revision
                config=root/'lock.toml'
                lines=['[kernel]',f'revision="{revision}"','upstream_tag="v7.3.1"','[package]']
                lines += [key+' = '+json.dumps(value) for key,value in lock['package'].items()]
                config.write_text('\n'.join(lines)+'\n')
                output=root/('output-'+str(number));log=root/('make-'+str(number)+'.jsonl')
                result=subprocess.run(['bash',str(RECIPE/'build.sh'),str(source),str(output),str(RECIPE/'kernel.config'),
                                       '--candidate-lock',str(config),'--validate-only'],
                                      env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],TASK_MAKE_LOG=str(log)),
                                      text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                calls=[json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual([args[-1] for args in calls],['olddefconfig','kernelrelease'])
                self.assertEqual(hashlib.sha256((output/'.config').read_bytes()).hexdigest(),lock['package']['config_sha256'])
