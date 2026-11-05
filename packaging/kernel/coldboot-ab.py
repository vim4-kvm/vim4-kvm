#!/usr/bin/env python3
"""Offline by default; execute one reviewed 20-boot RAM A/B batch under a lease.

No queue acquisition, sample retries, kernel builds or deployment. The input
JSON pins both archives, baseline proof and video checker by SHA256. UART stays
open through automatic recovery, final normal boot and video verification.
"""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader('ab_window', str(ROOT/'tools/board-window'))
spec = importlib.util.spec_from_loader('ab_window', loader)
window = importlib.util.module_from_spec(spec)
loader.exec_module(window)


def schedule():
    return [(group, str(number)) for number in range(1, 11) for group in ('A', 'B')]


class SlotExpired(TimeoutError):
    pass


@contextlib.contextmanager
def slot_timeout(seconds, phase='sample'):
    def expired(signum, frame):
        raise SlotExpired(phase+' deadline expired; stop further actions')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def checked_file(item):
    path = Path(item['path']).resolve()
    if window.sha(path) != item['sha256']:
        raise ValueError('Pinned file changed: '+str(path))
    return path


def preflight(config):
    proof = json.loads(checked_file(config['baseline']).read_text())
    checked_file(config['video'])
    plans = {}
    for group in ('A', 'B'):
        archive = checked_file(config[group])
        plan = window.validate_bundle(archive, ram_baseline_control=group == 'A')
        if not plan.get('early_capture') or plan['baseline_files'] != proof['files']:
            raise ValueError('Both groups need early capture and the exact retained proof')
        if (plan['baseline_release'], plan['baseline_id']) != (proof['release'], proof['build_id']):
            raise ValueError('Bundle recovery identity differs')
        if (plan['release'], plan['build_id']) != (config[group]['release'], config[group]['build_id']):
            raise ValueError('Bundle identity differs from approved group')
        plans[group] = plan
    if plans['A']['build_id'] == plans['B']['build_id']:
        raise ValueError('A and B must be the two different approved packages')
    if plans['A']['files']['coldboot-collect.py'] != plans['B']['files']['coldboot-collect.py']:
        raise ValueError('A/B collectors differ')
    return proof, plans


class Batch:
    def __init__(self, config, proof, plans, directory, host, device):
        self.config, self.proof, self.plans = config, proof, plans
        self.directory, self.host, self.device = directory, host, device
        self.created_firmware = []
        self.results = []

    def save(self):
        window.save(self.directory/'results.json', dict(samples=self.results,
                    unstarted=[g+n for g, n in schedule()][len(self.results):]))

    def baseline(self, name):
        actual = window.identity(self.host, list(self.proof['files']),
                                 dt_properties=self.proof.get('dt_properties', {}), baseline=True)
        window.save(self.directory/(name+'.json'), actual)
        window.verify_baseline(self.proof, actual)

    def video(self, name):
        with (self.directory/(name+'.log')).open('x') as log:
            subprocess.run([sys.executable, str(checked_file(self.config['video']))],
                           stdout=log, stderr=subprocess.STDOUT, timeout=100, check=True)

    def firmware(self, remove=False):
        # Only create absent release-specific copies. Never overwrite a file,
        # and remove only copies this batch created, after rechecking the hash.
        data = self.config['firmware']
        targets = self.created_firmware if remove else [
            '/lib/firmware/updates/'+self.plans[g]['release']+'/'+data['relative'] for g in ('A', 'B')]
        script = '''import hashlib,json,os
from pathlib import Path
source=Path(SOURCE)
digest=DIGEST
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)==digest
created=[]
for name in TARGETS:
 p=Path(name)
 if REMOVE:
  assert sha(p)==digest
  p.unlink()
 else:
  if p.exists():
   assert sha(p)==digest
  else:
   p.parent.mkdir(parents=True,exist_ok=True)
   with p.open('xb') as out: out.write(source.read_bytes())
   os.chmod(p,0o644)
   created.append(name)
   print(json.dumps(dict(created=name)),flush=True)
'''.replace('SOURCE', repr(data['source'])).replace('DIGEST', repr(data['sha256'])).replace(
            'TARGETS', repr(targets)).replace('REMOVE', repr(remove))
        # Keep ownership output even when the remote process fails halfway.
        def retain_ownership(output):
            if isinstance(output, bytes):
                output = output.decode()
            for line in (output or '').splitlines():
                self.created_firmware.append(json.loads(line)['created'])
            window.save(self.directory/'owned-firmware.json', self.created_firmware)
        try:
            result = subprocess.run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=5', self.host,
                                     'sudo -n python3 -'], input=script, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired as error:
            retain_ownership(error.stdout)
            raise
        retain_ownership(result.stdout)
        result.check_returncode()

    def snapshots(self, plan, label):
        prefix = str(window.once.candidate_prefix(plan))
        # The remote tar lives on tmpfs too; compare the transferred archive
        # before removing it. A cold reset may lose it: record that as missing.
        remote = prefix+'/capture/snapshot.tar'
        script = '''import hashlib,io,json,subprocess,tarfile
from pathlib import Path
directory=Path(DIRECTORY)
output=directory/'snapshot.tar'
with tarfile.open(output,'w') as archive:
 for status in sorted(directory.glob('*.status.json')):
  archive.add(status,arcname=status.name)
  snapshot=directory/(status.name.removesuffix('.status.json')+'.jsonl')
  if snapshot.exists(): archive.add(snapshot,arcname=snapshot.name)
 for label,argv in [('dmesg',['dmesg']),('journal',['journalctl','-b','--no-pager','-o','short-monotonic']),
                    ('services',['systemctl','--failed','--no-pager'])]:
  try:
   p=subprocess.run(argv,capture_output=True,timeout=1)
   data=p.stdout+p.stderr
  except subprocess.TimeoutExpired as error:
   data=(error.stdout or b'')+(error.stderr or b'')+b'\\nCOLLECTION TIMEOUT\\n'
  item=tarfile.TarInfo(label+'.txt');item.size=len(data);item.mode=0o600
  archive.addfile(item,io.BytesIO(data))
print(hashlib.sha256(output.read_bytes()).hexdigest())
'''.replace('DIRECTORY', repr(prefix+'/capture'))
        digest = window.ssh_python(self.host, script, timeout=10).strip()
        output = self.directory/(label+'.tar')
        with output.open('xb') as log:
            subprocess.run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=5', self.host,
                            'sudo -n cat '+shlex.quote(remote)], stdout=log, timeout=10, check=True)
        if window.sha(output) != digest:
            raise RuntimeError('Snapshot transfer hash mismatch')
        window.ssh(self.host, 'sudo -n rm -- '+shlex.quote(remote), timeout=5)
        window.save(output.with_suffix('.sha256.json'), dict(sha256=digest))

    def ready_runtime(self, label):
        """Independent SSH evidence even when the early collector has failed."""
        script = '''import json,subprocess,time
from pathlib import Path
module=Path('/sys/module/aml_vdec_drv')
result=dict(monotonic_ns=time.monotonic_ns(),module_present=module.exists(),parameters={})
for path in sorted((module/'parameters').glob('*')):
 try: result['parameters'][path.name]=dict(value=path.read_text())
 except OSError as error: result['parameters'][path.name]=dict(error=str(error))
for name in ('/proc/sys/kernel/random/boot_id','/proc/modules','/proc/uptime'):
 try: result[name]=dict(value=Path(name).read_text())
 except OSError as error: result[name]=dict(error=str(error))
try:
 p=subprocess.run(['/usr/sbin/lsmod'],capture_output=True,text=True,timeout=2)
 result['lsmod']=dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
except (OSError,subprocess.TimeoutExpired) as error: result['lsmod']=dict(error=str(error))
print(json.dumps(result))
'''
        window.save(self.directory/(label+'-ready-runtime.json'),
                    json.loads(window.ssh_python(self.host, script, timeout=10)))

    def automatic_recovery(self, stream):
        stream.recovery(self.proof['release'])
        end = min(time.monotonic()+60, stream.deadline-360)
        while time.monotonic() < end:
            stream.check()
            if stream.events.linux_started is not None:
                try:
                    window.ready(self.host, timeout=min(3, end-time.monotonic()),
                                 expected=self.proof['release'], deadline_bound=True)
                except TimeoutError:
                    continue
                self.baseline('automatic-recovery-'+str(len(self.results)))
                stream.check()
                return
            stream.read_since(len(stream.data), .1)
        raise TimeoutError('Automatic formal recovery deadline expired')

    def sample(self, group, number, stream):
        plan = self.plans[group]
        label = group+number
        stream.begin_sample(label)
        result = dict(label=label, status='invalid', started_monotonic_ns=time.monotonic_ns())
        self.results.append(result)
        self.save()
        try:
            window.boot(self.host, self.device, self.directory, plan, uart=stream)
            result['linux_started'] = stream.events.linux_started
            actual = window.identity(self.host, [])
            window.save(self.directory/(label+'-identity.json'), actual)
            if (actual['release'], actual['build_id']) != (plan['release'], plan['build_id']):
                raise RuntimeError('Selected runtime identity differs')
            window.verify_candidate_dt(self.host, plan, self.proof.get('dt_properties', {}),
                                       ram_baseline_control=group == 'A')
            if group == 'B':
                window.verify_ram_baseline_runtime(plan, window.ram_runtime(self.host, plan['release']))
            try:
                self.ready_runtime(label)
            except SlotExpired:
                raise
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                result['ready_runtime_missing'] = str(error)
            stream.check()
            end = result['linux_started']/1e9 + 60
            for phase in ('ready', 'end'):
                if phase == 'end':
                    while time.monotonic() < end+1.5:
                        stream.read_since(len(stream.data), min(.1, end+1.5-time.monotonic()))
                stream.check()
                try:
                    self.snapshots(plan, label+'-'+phase)
                except SlotExpired:
                    raise
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    result[phase+'_capture_missing'] = str(error)
                stream.check()
            result['status'] = 'observed'
        except Exception as error:
            if stream.cold_reset():
                started, reset = stream.events.linux_started, stream.events.reset_at
                result.update(status='cold-reset', linux_started=started, reset_at=reset, error=str(error))
                if started is None:
                    raise RuntimeError('Reset without a selected Linux start') from error
                if reset-started > 60*10**9:
                    result['status'] = 'post-observation-cold-reset'
                self.save()
                self.automatic_recovery(stream)
            else:
                result['error'] = str(error)
                raise
        finally:
            result['ended_monotonic_ns'] = time.monotonic_ns()
            self.save()

    def execute(self):
        queue, token = window.require_board()
        ticket = queue.read(token)
        remaining = ticket['started']+ticket['seconds']-time.time()
        if remaining < 49*60:
            raise RuntimeError('Batch requires a fresh approved 50 minute ticket')
        deadline = time.monotonic()+min(remaining, 50*60)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        window.save(self.directory/'baseline-proof.json', self.proof)
        queue.sampling(token, True)
        attempted = False
        try:
            with window.continuous_uart(self.device, self.directory, deadline=deadline) as stream:
                stream.observe_running(self.proof['release'])
                try:
                    self.baseline('entry')
                    stream.check()
                    # mountinfo fsroot comparison assumes /var/lib is on /.
                    check = "import os; assert os.stat('/').st_dev==os.stat('/var/lib').st_dev; print(open('/proc/self/mountinfo').read())"
                    (self.directory/'entry-mountinfo.txt').write_text(window.ssh_python(self.host, check, timeout=10))
                    self.video('entry-video')
                    stream.check()
                    self.firmware()
                    for group, plan in self.plans.items():
                        window.record_candidate(self.directory, plan, self.config[group]['sha256'])
                        window.stage_bundle(self.host, checked_file(self.config[group]),
                                            self.config[group]['sha256'], plan, self.proof,
                                            ram_baseline_control=group == 'A')
                        stream.check()
                    for group, number in schedule():
                        window.require_board()
                        attempted = True
                        with slot_timeout(120):
                            self.sample(group, number, stream)
                finally:
                    self.save()
                    try:
                        self.firmware(remove=True)
                    finally:
                        if attempted:
                            with slot_timeout(max(.001, min(360, deadline-time.monotonic())), 'final recovery'):
                                self.restore(stream)
        finally:
            queue.sampling(token, False)

    def restore(self, stream):
        stream.final_recovery(self.proof['release'])
        window.boot(self.host, self.device, self.directory,
                    baseline_release=self.proof['release'], uart=stream)
        self.baseline('returned-baseline')
        self.video('returned-video')
        stream.check()
        # Complete local archives already exist. Cleanup uses the staged helper
        # and exact recorded payload identities, only after successful recovery.
        for group, plan in self.plans.items():
            remote = '/tmp/board-window-'+plan['build_id']
            window.ssh_python(self.host, window.module_cleanup_script([plan], remote+'/display-once.py'))
            prefix = str(window.once.candidate_prefix(plan))
            window.ssh(self.host, 'sudo -n rm -rf -- '+shlex.quote(prefix)+' '+shlex.quote(remote))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--host', default='vim4')
    parser.add_argument('--device', default='/dev/cu.usbserial-100')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    proof, plans = preflight(config)
    if not args.execute:
        print(json.dumps(dict(schedule=[g+n for g,n in schedule()], validated=True)))
        return
    if args.output is None:
        parser.error('--execute requires a new --output directory')
    Batch(config, proof, plans, args.output, args.host, args.device).execute()


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    main()
