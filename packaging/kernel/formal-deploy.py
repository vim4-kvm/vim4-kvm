#!/usr/bin/env python3
"""Formal package deployment. plan/publish are offline; execute reboots under an existing board ticket.

Only selected limited gates run. Failed installation recovers once if SSH is reachable.
"""
import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time

import copy
import re
import sys
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[2]
KERNEL = ROOT / 'packaging/kernel'
OUT = KERNEL / 'formal'
REMOTE = '/var/tmp/vim4-formal-deploy'
HOST = 'vim4'
UART = '/dev/cu.usbserial-1100'
RECEIVER_IP = '192.168.50.239'
PLAYWRIGHT = os.environ.get('PLAYWRIGHT_MODULE', 'playwright')

def load(path):
    loader = importlib.machinery.SourceFileLoader('direct_board_window', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    value = importlib.util.module_from_spec(spec)
    loader.exec_module(value)
    return value

bw = load(ROOT / 'tools/board-window')

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def save(name, value):
    (LOG / name).write_text(json.dumps(value, indent=2) + '\n')

def run(argv, name, timeout=90, text=None, env=None):
    bw.require_board()
    with (LOG / name).open('w') as log:
        result = subprocess.run(argv, input=text, text=True, stdout=log, stderr=subprocess.STDOUT,
                                timeout=timeout, env=env, cwd=ROOT)
    result.check_returncode()
    return (LOG / name).read_text()

def ssh(script, name, timeout=120):
    return run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=5', HOST, 'sudo -n python3 -'], name, timeout, script)

def upload(source, target):
    run(['scp', '-q', str(source), HOST + ':' + target], 'upload-' + source.name + '.log', 180)
    result = ssh('import hashlib;from pathlib import Path\np=Path(' + repr(target) + ')\nprint(hashlib.file_digest(p.open("rb"),"sha256").hexdigest())', 'hash-' + source.name + '.log')
    assert result.strip() == sha(source)

def wait_natural(old_boot, label):
    end = time.monotonic() + 420
    while time.monotonic() < end:
        try:
            text = bw.ssh(HOST, 'cat /proc/sys/kernel/random/boot_id', timeout=min(5, end-time.monotonic()))
            if text.strip() != old_boot:
                bw.ready(HOST, timeout=max(.01, end-time.monotonic()), old_boot=old_boot, deadline_bound=True)
                save(label + '-ready.json', dict(boot_id=text.strip(), ready_at=time.time()))
                return
        except (subprocess.SubprocessError, OSError):
            pass
        time.sleep(1)
    raise TimeoutError('420 seconds without natural SSH recovery; no extra reboot')

def reboot(old_boot, label):
    try:
        run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=5', HOST, 'sudo -n systemctl reboot'], label + '-reboot.log', 15)
    except subprocess.CalledProcessError as error:
        if error.returncode != 255:
            raise
    wait_natural(old_boot, label)

SNAPSHOT = '''import gzip,hashlib,json,pathlib,platform,struct,subprocess
P=pathlib.Path
def sha(p):
 with P(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
release=platform.release();root=P('/boot/kernels')/release
m=json.loads((root/'manifest.json').read_text())
assert m['release']==release
data=P('/sys/kernel/notes').read_bytes();offset=0;ids=[]
while offset+12<=len(data):
 n,d,k=struct.unpack_from('<III',data,offset);offset+=12;start=offset+((n+3)&~3)
 if data[offset:offset+n]==b'GNU\\0' and k==3:ids.append(data[start:start+d].hex())
 offset=start+((d+3)&~3)
assert ids==[m['kernel_build_id']]
module_root=P('/lib/modules')/release
files={str(p.relative_to(module_root)):sha(p) for p in module_root.rglob('*') if p.is_file()}
assert files==m['modules']
assert hashlib.sha256(gzip.decompress(P('/proc/config.gz').read_bytes())).hexdigest()==m['config_sha256']
for name in ('Image','vim4.dtb','panfrost.dtb','config','Module.symvers','vmlinux.btf'):
 assert sha(root/name)==m['files'][name],name
for name,value in m['files'].items():
 if name.startswith('runtime/usr/'):assert sha('/'+name.removeprefix('runtime/'))==value,name
names={P(n).name.split('.ko')[0].replace('-','_'):v for n,v in m['module_build_ids'].items()}
loaded={}
for p in P('/sys/module').glob('*/notes/.note.gnu.build-id'):
 name=p.parents[1].name
 if name in names:
  data=p.read_bytes();assert struct.unpack_from('<III',data)==(4,20,3)
  loaded[name]=data[16:36].hex();assert loaded[name]==names[name]
  assert (P('/sys/kernel/btf')/name).is_file()
import sys
sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4boot
text=vim4boot.CONFIG.read_text();entries=vim4boot.boot_entries(text)
assert vim4boot.default_label(text)=='Mainline'
assert entries['Mainline']['LINUX']=='/kernels/'+release+'/Image'
assert entries['Mainline']['FDT']=='/kernels/'+release+'/vim4.dtb'
assert not P('/sys/module/fusb302').exists()
assert all(P('/dev/hidg'+str(i)).is_char_device() for i in range(3))
print(json.dumps(dict(release=release,source=m['source'],build_id=ids[0],kernel_build_id=ids[0],
 default='Mainline',cmdline=P('/proc/cmdline').read_text().strip(),entries=entries,
 manifest_sha256=sha(root/'manifest.json'),kernels_sha256=sha(vim4boot.MANIFEST),
 module_count=len(names),module_files=len(files),loaded_module_build_ids=loaded,
 boot_sha256={p.name:sha(p) for p in root.iterdir() if p.is_file()},
 boot_id=P('/proc/sys/kernel/random/boot_id').read_text().strip(),uptime=P('/proc/uptime').read_text(),
 fusb302_loaded=False,lsmod=subprocess.check_output(['lsmod'],text=True),
 kernel_log=subprocess.check_output(['journalctl','-k','-b','--no-pager','-o','short-monotonic'],text=True))))
'''

def video(label, attempts=4):
    # A fresh boot may revoke and relock the HDMI link before frames arrive.
    for attempt in range(attempts):
        try:
            return receive(label + ('' if attempt == 0 else '-retry' + str(attempt)))
        except (AssertionError, subprocess.SubprocessError, json.JSONDecodeError):
            if attempt == attempts - 1:
                raise
            time.sleep(45)

def receive(label):
    row = next(row for row in (ROOT/'docs/hardware.md').read_text().splitlines() if row.startswith('| admin |'))
    env = dict(os.environ, MANAGER_PASSWORD=row.split('|')[2].strip().strip('`'),
               PLAYWRIGHT_MODULE=PLAYWRIGHT,
               VIM4_TEST_CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    with (LOG/(label+'-tunnel.log')).open('w') as log:
        tunnel = subprocess.Popen(['ssh','-N','-oBatchMode=yes','-oExitOnForwardFailure=yes',
                                   '-L','18088:127.0.0.1:8081',HOST], stdout=log, stderr=log)
        try:
            time.sleep(.5);assert tunnel.poll() is None
            value = json.loads(run(['node',str(ROOT/'tools/board-window-receiver.mjs'),
                                    'http://127.0.0.1:18088','5','--local-ip='+RECEIVER_IP],
                                   label+'-video.json',100,env=env))
            assert value['fps']>0 and value['samples'][-1]['framesDecoded']>value['samples'][0]['framesDecoded']
            return dict(fps=value['fps'],frames=value['samples'][-1]['framesDecoded']-value['samples'][0]['framesDecoded'])
        finally:
            tunnel.terminate()
            try:tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait()

def recover(backups):
    # The same task directory contains the helpers; it is not under /tmp.
    for source,target in [(ROOT/'packaging/kernel/register-runtime.py','packaging/kernel/register-runtime.py'),
                          (ROOT/'board/vim4boot.py','board/vim4boot.py')]:
        upload(source, REMOTE+'/'+target)
    upload(ROLLBACK, REMOTE+'/rollback.tar.gz')
    script='''import hashlib,importlib.util,json,os,sys,tarfile,tempfile
from pathlib import Path
sys.path.insert(0,REMOTE+'/board');import vim4boot
spec=importlib.util.spec_from_file_location('registration',REMOTE+'/packaging/kernel/register-runtime.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
with tempfile.TemporaryDirectory(prefix='vdec-followups-return-') as temporary:
 archive=Path(REMOTE)/'rollback.tar.gz'
 assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==ROLLBACK_SHA
 with tarfile.open(archive) as source:source.extractall(temporary,filter='data')
 root=Path(temporary)
 for name,expected in json.loads((root/'runtime-files.json').read_text()).items():
  if name.startswith('usr/'):
   source=root/'runtime'/name;assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
   source.chmod(0o755);r.atomic_copy(source,Path('/')/name)
 for path,data in BACKUPS.items():vim4boot.atomic_write(Path(path),bytes.fromhex(data))
 os.sync()
 print(Path('/proc/sys/kernel/random/boot_id').read_text().strip())
'''.replace('REMOTE',repr(REMOTE)).replace('ROLLBACK_SHA',repr(ROLLBACK_SHA)).replace('BACKUPS',repr(backups))
    old_boot=ssh(script,'rollback-registration.log',120).strip()
    reboot(old_boot,'rollback')
    expected=json.loads((LOG/'baseline-proof.json').read_text())
    actual=bw.identity(HOST,list(expected['files']),baseline=True)
    bw.verify_baseline(expected,actual);save('returned-proof.json',actual)
    save('returned-video-summary.json',video('returned'))

def execute():
    queue,ticket=bw.require_board()
    LOG.mkdir(parents=True,exist_ok=False)
    configure_baseline_identity()
    assert queue.read(ticket)['seconds']>=1200
    queue.sampling(ticket,True)
    installed=False;backups=None
    try:
        lease=queue.read(ticket)
        with bw.continuous_uart(UART,LOG,deadline=time.monotonic()+lease['started']+lease['seconds']-time.time()-10) as uart:
            cursor,drained=uart.read_since(0,1)
            save('entry-uart-drain.json',dict(bytes=len(drained),sha256=hashlib.sha256(drained).hexdigest()))
            expected = baseline_overlay(json.loads(BASELINE.read_text()), OVERLAY)
            baseline=bw.identity(HOST,list(expected['files']),baseline=True)
            bw.verify_baseline(expected,baseline);save('baseline-proof.json',baseline)
            ssh("import json;from pathlib import Path;p=Path('/etc/default/vim4-kvm-fan');print(json.dumps(p.read_bytes().hex() if p.exists() else None))", 'fan-before.json')
            save('plan.json', PLAN)
            backups=json.loads(ssh('''import json,shutil;from pathlib import Path
paths=['/boot/extlinux/extlinux.conf','/etc/vim4-kvm/kernels.json','/etc/vim4-kvm/runtime-build.json']
print(json.dumps(dict(originals={p:Path(p).read_bytes().hex() for p in paths},boot_free=shutil.disk_usage('/boot').free,root_free=shutil.disk_usage('/').free,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())))''','entry.json'))
            for path,data in backups['originals'].items():(LOG/Path(path).name).write_bytes(bytes.fromhex(data))
            if RETIRED:
                ssh('''import json,shutil,sys,os
from pathlib import Path
sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4boot
root=Path('/boot/kernels')/RETIRED
assert root.is_dir() and not root.is_symlink()
assert RETIRED not in vim4boot.CONFIG.read_text() and RETIRED not in vim4boot.MANIFEST.read_text()
shutil.rmtree(root);os.sync()
'''.replace('RETIRED',repr(RETIRED)), 'retire-boot.log')
            space=json.loads(ssh("import shutil,json;print(json.dumps(dict(boot=shutil.disk_usage('/boot').free,root=shutil.disk_usage('/').free)))",'space.json'))
            assert space['boot'] >= PLAN['boot_bytes'], 'Insufficient /boot space'
            assert space['root'] >= PLAN['root_bytes'], 'Insufficient root space'
            original_extlinux=bytes.fromhex(backups['originals']['/boot/extlinux/extlinux.conf']).decode()
            save('local-package.json',dict(sha256=sha(ARCHIVE),bytes=ARCHIVE.stat().st_size))
            assert sha(ARCHIVE)==PACKAGE_SHA
            run(['ssh','-oBatchMode=yes',HOST,'mkdir -p '+REMOTE+'/packaging/kernel '+REMOTE+'/board'], 'stage-root.log')
            for source,target in [(ROOT/'packaging/kernel/register-runtime.py','packaging/kernel/register-runtime.py'),
                                  (ROOT/'board/vim4boot.py','board/vim4boot.py'),(ARCHIVE,'kernel.tar.gz')]:
                upload(source,REMOTE+'/'+target)
            installed=True
            run(['ssh','-oBatchMode=yes',HOST,'sudo -n timeout --kill-after=5 240 python3 '+REMOTE+'/packaging/kernel/register-runtime.py install '+REMOTE+'/kernel.tar.gz'], 'install.log',250)
            change=json.loads(ssh('''import json,sys
sys.path.insert(0,REMOTE+'/board');import vim4boot
print(json.dumps(dict(extlinux_hex=vim4boot.CONFIG.read_bytes().hex(),kernels=json.loads(vim4boot.MANIFEST.read_text()))))
'''.replace('REMOTE',repr(REMOTE)), 'registered.json'))
            check_registration(original_extlinux, bytes.fromhex(change['extlinux_hex']).decode(),
                               json.loads(bytes.fromhex(backups['originals']['/etc/vim4-kvm/kernels.json'])),
                               change['kernels'], RELEASE)
            uart.mark('requested-natural-reboot',release=RELEASE)
            reboot(backups['boot_id'],'installed')
            report=json.loads(ssh(SNAPSHOT,'installed-proof.json',150))
            assert (report['release'],report['source'],report['build_id'])==(RELEASE,SOURCE,ID)
            assert report['manifest_sha256']==MANIFEST_SHA
            assert report['entries']['Mainline']['APPEND']==boot.boot_entries(original_extlinux)['Mainline']['APPEND']
            save('passive-video-summary.json',video('installed'))
            run_gates()
            bw.ready(HOST,timeout=120)
            save('after-gates-video-summary.json',video('after-gates'))
            receipt='''import hashlib,json,os,time
from pathlib import Path
import sys
sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4boot
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
root=Path('/boot/kernels')/RELEASE;m=json.loads((root/'manifest.json').read_text())
p=Path('/etc/vim4-kvm/runtime-build.json');record=json.loads(p.read_text())
record.update(running=RELEASE,default='Mainline',kernel_source=m['source'],kernel_build_id=m['kernel_build_id'],module_archive_sha256=m['files']['modules.tar.gz'],config_sha256=m['config_sha256'],observed_at=time.time(),record=RECORD,verification_logs=LOG_PATH,acceptance_scope=GATE_SCOPE)
record['deployed_components']['kernel']=m['source']
record['sha256']={n:sha(n) for n in record['sha256'] if Path(n).is_file() and not n.startswith('/boot/kernels/')}
record['sha256'].update({str(p):sha(p) for p in root.iterdir() if p.is_file()})
for name in record['loaded_module_build_ids']:
 note=Path('/sys/module',name,'notes/.note.gnu.build-id')
 if note.exists():record['loaded_module_build_ids'][name]=note.read_bytes()[16:36].hex()
vim4boot.atomic_write(p,(json.dumps(record,indent=2)+'\\n').encode());os.sync()
sys.stdout.write(p.read_text())
'''.replace('RELEASE',repr(RELEASE)).replace('RECORD',repr(RECORD)).replace('LOG_PATH',repr(str(LOG))).replace('GATE_SCOPE',repr(','.join(PLAN['gates'])))
            ssh(receipt,'runtime-build.json')
            # Capture the new full baseline without using the still-old local lock.
            paths=list(baseline['files'])
            paths=[n for n in paths if not n.startswith(('/boot/kernels/'+OLD+'/', '/lib/modules/'+OLD+'/'))]
            manifest=json.loads(MANIFEST.read_text())
            paths += ['/boot/kernels/'+RELEASE+'/'+n for n in ('Image','vim4.dtb','panfrost.dtb','config','Module.symvers','vmlinux.btf','manifest.json')]
            paths += ['/lib/modules/'+RELEASE+'/'+n for n in manifest['modules']]
            capture='''import hashlib,json
from pathlib import Path
expected=BASE
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for path,value in expected['files'].items():
 if path.startswith(('/boot/kernels/'+OLD+'/', '/lib/modules/'+OLD+'/')):assert sha(path)==value,path
report=dict(expected,release=RELEASE,build_id=BUILD_ID,cmdline=Path('/proc/cmdline').read_text().strip(),files={p:sha(p) for p in PATHS})
report['loaded_modules']={name:Path('/sys/module',name,'notes/.note.gnu.build-id').read_bytes()[16:36].hex() for name in expected['loaded_modules']}
print(json.dumps(report,indent=2))
'''.replace('BASE',repr(baseline)).replace('OLD',repr(OLD)).replace('RELEASE',repr(RELEASE)).replace('BUILD_ID',repr(ID)).replace('PATHS',repr(paths))
            fresh=json.loads(ssh(capture,'new-baseline.json',150))
            report['baseline_proof_sha256']=sha(LOG/'new-baseline.json')
            report['evidence']=RECORD
            save('installed-proof.json',report)
            # Remove only this upload directory; installed releases and old packages stay.
            ssh('import shutil;shutil.rmtree('+repr(REMOTE)+')','cleanup-upload.log')
            save('result.json',dict(installed=True,retained_default=True,release=RELEASE,build_id=ID,source=SOURCE,
                                   package_sha256=PACKAGE_SHA,gates=PLAN['gates']))
    except BaseException as error:
        result=dict(installed=False,error=repr(error),installation_attempted=installed)
        if installed:
            try:
                # An unreachable board cannot have its registration restored over SSH.
                # Stop there; never turn a passive recovery failure into reboot loops.
                bw.ssh(HOST,'true',timeout=5)
                recovery_log=LOG/'recovery';recovery_log.mkdir()
                with bw.continuous_uart(UART,recovery_log,deadline=time.monotonic()+420):
                    recover(backups['originals'])
                result['restored']=True
            except BaseException as recovery:result['recovery_error']=repr(recovery)
        save('result.json',result)
        raise
    finally:queue.sampling(ticket,False)

boot = load(ROOT / 'board/vim4boot.py')
GATES = ('hdmi-modes', 'h264', 'h265', '4k60', 'audio', 'hid', 'media', 'gpu',
         'manager', 'fan-persistence', 'decode-smoke', 'pd', 'cleanup')


def gates_list(value):
    names = value.split(',')
    if not value or any(n not in GATES for n in names) or len(set(names)) != len(names):
        raise argparse.ArgumentTypeError('gates must be unique comma-separated names: ' + ','.join(GATES))
    return names


def checked(path, expected):
    if sha(path) != expected:
        raise ValueError('SHA256 mismatch: ' + str(path))
    return Path(path).resolve()


def baseline_overlay(baseline, overlay):
    result = copy.deepcopy(baseline)
    for path, digest in overlay.items():
        if path not in result['files'] or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Overlay must replace an existing protected file with a SHA256: ' + path)
        result['files'][path] = digest
    return result


def configure_baseline_identity():
    # board-window historically uses tested_build for the retained identity.
    # During an upgrade these differ; derive its capture lock from the sealed
    # retained proof rather than comparing the old board against new modules.
    proof = baseline_overlay(json.loads(BASELINE.read_text()), OVERLAY)
    boot_prefix = '/boot/kernels/'+OLD+'/'
    module_prefix = '/lib/modules/'+OLD+'/'
    manifest = dict(files={p.removeprefix(boot_prefix):v for p,v in proof['files'].items() if p.startswith(boot_prefix)},
                    modules={p.removeprefix(module_prefix):v for p,v in proof['files'].items() if p.startswith(module_prefix)})
    (LOG/'baseline-identity-manifest.json').write_text(json.dumps(manifest))
    built = dict(manifest_path='baseline-identity-manifest.json',
                 manifest_sha256=proof['files'][boot_prefix+'manifest.json'])
    retained = dict(release=OLD,build_id=proof['build_id'])
    text = '[retained_runtime]\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in retained.items())
    text += '[tested_build]\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in built.items())
    text += '[tested_build.module_build_ids]\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in proof['loaded_modules'].items())
    path = LOG/'baseline-identity.toml'
    path.write_text(text)
    bw.once.SOURCES = path


def check_registration(before, after, old_records, new_records, release):
    old, new = boot.boot_entries(before), boot.boot_entries(after)
    if boot.default_label(before) != 'Mainline' or boot.default_label(after) != 'Mainline':
        raise ValueError('Default label changed')
    expected = copy.deepcopy(old)
    expected['Mainline'].update(LINUX='/kernels/'+release+'/Image', FDT='/kernels/'+release+'/vim4.dtb')
    if new != expected:
        raise ValueError('Registration changed APPEND or another boot entry')
    if [r for r in old_records if r['label'] != 'Mainline'] != [r for r in new_records if r['label'] != 'Mainline']:
        raise ValueError('Registration changed other kernels.json records')


def prepare_plan(args):
    lock_path = Path(args.sources).resolve()
    kernel = lock_path.parent
    lock = tomllib.loads(lock_path.read_text())
    new, old = lock['tested_build'], lock['retained_runtime']
    if new['release'] == old['release']:
        raise ValueError('tested_build and retained_runtime name the same release; same-release reinstall is unsupported. Supply a distinct candidate source lock and the retained release rollback package.')
    package = checked(args.package, new['package_sha256'])
    rollback = checked(args.rollback, old['package_sha256'])
    manifest_path = checked(kernel/new['manifest_path'], new['manifest_sha256'])
    baseline_path = checked(kernel/old['baseline_proof_path'], old['baseline_proof_sha256'])
    manifest = json.loads(manifest_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    if (manifest['release'], manifest['kernel_build_id'], manifest['source']) != (
            new['release'], new['build_id'], new['image_source_revision']):
        raise ValueError('tested_build identity differs from manifest')
    if (baseline['release'], baseline['build_id']) != (old['release'], old['build_id']):
        raise ValueError('retained_runtime identity differs from baseline')
    if args.retire and (args.retire in (new['release'], old['release']) or not re.fullmatch('[A-Za-z0-9_.+-]+', args.retire)):
        raise ValueError('retire must name an unregistered older release')
    overlay = json.loads(Path(args.baseline_overlay).read_text()) if args.baseline_overlay else {}
    baseline_overlay(baseline, overlay)
    with tarfile.open(package) as archive:
        members = archive.getmembers()
        entry = next(m for m in members if m.name.removeprefix('./') == 'manifest.json')
        if hashlib.sha256(archive.extractfile(entry).read()).hexdigest() != new['manifest_sha256']:
            raise ValueError('Package manifest differs from source lock')
        boot_bytes = sum(m.size for m in members if m.name.removeprefix('./') in
                         ('Image','vim4.dtb','panfrost.dtb','config','Module.symvers','vmlinux.btf','manifest.json'))
        # register-runtime performs the full filesystem-aware space preflight too.
        root_bytes = sum(m.size for m in members) * 3
    directory = Path(args.output).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    assets = prepare_assets(args.gates, directory, args)
    files = {str(p): sha(p) for p in (package, rollback, manifest_path, baseline_path, lock_path)}
    for folder in (OUT,):
        files.update({str(p):sha(p) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    for p in (Path(__file__).resolve(), KERNEL/'formal-gates.py', KERNEL/'register-runtime.py',
              ROOT/'board/vim4boot.py', ROOT/'tools/board-window', ROOT/'tools/board-queue',
              ROOT/'tools/board-window-receiver.mjs', KERNEL/'final-manager-check.mjs',
              ROOT/'tools/board_uart.py', ROOT/'packaging/kbase/run.py',
              KERNEL/'final-manager-pd.mjs', KERNEL/'pd-b-state.json', ROOT/'tools/manager-login.mjs'):
        files[str(p)] = sha(p)
    files.update(assets)
    plan = dict(release=new['release'], old_release=old['release'], build_id=new['build_id'],
                source=new['image_source_revision'], package=str(package), rollback=str(rollback),
                package_sha256=new['package_sha256'], rollback_sha256=old['package_sha256'],
                manifest=str(manifest_path), manifest_sha256=new['manifest_sha256'],
                baseline=str(baseline_path), overlay=overlay, sources=str(lock_path),
                gates=args.gates, retire=args.retire, record=args.record, logs=str(Path(args.logs).resolve()),
                host=args.host, uart=args.uart, receiver_ip=args.receiver_ip, playwright=args.playwright,
                assets=str(directory/'assets'), files=files, boot_bytes=boot_bytes, root_bytes=root_bytes)
    destination = directory/'plan.json'
    destination.write_text(json.dumps(plan, indent=2)+'\n')
    return destination


def prepare_assets(gates, directory, args):
    assets = directory/'assets'
    assets.mkdir()
    files = {}
    fixture = load(KERNEL/'hdmi-mode-fixture.py')
    edid = json.loads((OUT/'1080p60-edid.json').read_text())
    data = fixture.single_mode_edid(fixture.BASELINE.read_bytes(), edid['mode'])
    if hashlib.sha256(data).hexdigest() != edid['sha256']:
        raise ValueError('Generated 1080p60 EDID differs from reviewed fixture')
    (assets/'1080p60.bin').write_bytes(data)
    for source in (KERNEL/'hdmi-mode-fixture.py', fixture.BASELINE):
        files[str(source)] = sha(source)
    if set(gates) & {'hid','media','hdmi-modes','4k60'}:
        (assets/'m6').mkdir()
        for name in ('input-target','hdmi-source-mode','latency-source','input-source'):
            source = OUT/'m6/input-source.swift' if name == 'input-source' else ROOT/'tools'/(name+'.swift')
            target = assets/'m6'/name
            subprocess.run(['swiftc','-O',str(source),'-o',str(target)],check=True,timeout=180)
            files[str(source)] = sha(source)
        for name in ('client.py','host.py'):
            shutil.copyfile(OUT/'m6'/name, assets/'m6'/name)
    if 'gpu' in gates:
        source = ROOT/'packaging/gpu/gpu-probe.c'
        subprocess.run(shlex.split(args.gpu_cc)+['-O2',str(source),'-o',str(assets/'gpu-probe'),
                                               '-lEGL','-lGLESv2','-lgbm'],check=True,timeout=120)
        files[str(source)] = sha(source)
    if 'media' in gates:
        # Fixed FAT metadata and marker, no user disk or mounted filesystem.
        prepare_media(assets/'usb-edge-transfer.img')
    if 'decode-smoke' in gates:
        if not args.decode_assets or not args.decode_assets_sha256:
            raise ValueError('decode-smoke needs --decode-assets TAR and --decode-assets-sha256 from its build receipt')
        source = checked(args.decode_assets, args.decode_assets_sha256)
        checked(source, json.loads((OUT/'decode-smoke.json').read_text())['archive_sha256'])
        shutil.copyfile(source, assets/'decode-assets.tar')
    files.update({str(p):sha(p) for p in assets.rglob('*') if p.is_file()})
    return files


def prepare_media(path):
    # A small deterministic FAT16 superfloppy, matching the M6 host fixture contract.
    import struct
    image = bytearray(32*1024*1024)
    image[:3] = b'\xeb\x3c\x90'
    image[3:11] = b'MSDOS5.0'
    struct.pack_into('<HBHBHHBHHHII', image, 11, 512, 4, 1, 2, 512, 0, 0xf8, 64, 32, 64, 0, 65536)
    image[36:39] = b'\x80\x00\x29'
    struct.pack_into('<I', image, 39, 0x45444745)
    image[43:54] = b'EDGEUSB21  '
    image[54:62] = b'FAT16   '
    image[510:512] = b'\x55\xaa'
    for offset in (512, 65*512):
        struct.pack_into('<HHH', image, offset, 0xfff8, 0xffff, 0xffff)
    root = 129*512
    image[root:root+11] = b'EDGEUSB21  '
    image[root+11] = 8
    entry = root+32
    image[entry:entry+11] = b'MARKER  TXT'
    image[entry+11] = 0x20
    struct.pack_into('<H', image, entry+24, 0x21)
    struct.pack_into('<H', image, entry+26, 2)
    marker = b'VIM4 edge USB transfer validation\n'
    struct.pack_into('<I', image, entry+28, len(marker))
    image[161*512:161*512+len(marker)] = marker
    path.write_bytes(image)


def configure(plan):
    global PLAN, LOG, OLD, RELEASE, ID, SOURCE, ARCHIVE, PACKAGE_SHA, MANIFEST_SHA
    global ROLLBACK, ROLLBACK_SHA, MANIFEST, BASELINE, OVERLAY, RETIRED, RECORD
    global HOST, UART, RECEIVER_IP, PLAYWRIGHT
    PLAN = plan
    for path, digest in plan['files'].items():
        checked(path, digest)
    LOG=Path(plan['logs']);OLD=plan['old_release'];RELEASE=plan['release']
    ID=plan['build_id'];SOURCE=plan['source'];ARCHIVE=Path(plan['package'])
    PACKAGE_SHA=plan['package_sha256'];MANIFEST_SHA=plan['manifest_sha256']
    ROLLBACK=Path(plan['rollback']);ROLLBACK_SHA=plan['rollback_sha256']
    MANIFEST=Path(plan['manifest']);BASELINE=Path(plan['baseline']);OVERLAY=plan['overlay']
    RETIRED=plan['retire'];RECORD=plan['record'];HOST=plan['host'];UART=plan['uart']
    RECEIVER_IP=plan['receiver_ip'];PLAYWRIGHT=plan['playwright']


def run_gates():
    row = next(row for row in (ROOT/'docs/hardware.md').read_text().splitlines() if row.startswith('| admin |'))
    env = dict(os.environ, MANAGER_PASSWORD=row.split('|')[2].strip().strip('`'),
               PLAYWRIGHT_MODULE=PLAYWRIGHT, VIM4_TEST_CHROME=os.environ.get('VIM4_TEST_CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
               VIM4_FINAL_LOGS=str(LOG), VIM4_FORMAL_ASSETS=PLAN['assets'],
               VIM4_RECEIVER_IP=RECEIVER_IP, VIM4_HOST=HOST,
               VIM4_EXPECTED_RELEASE=RELEASE, MANAGER_URL='http://127.0.0.1:18080',
               VIM4_FORMAL_TUNNEL='1')
    tunnel = subprocess.Popen(['ssh','-N','-oBatchMode=yes','-oExitOnForwardFailure=yes',
                               '-L','18088:127.0.0.1:8081','-L','18080:127.0.0.1:80',HOST],
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    bridge = session = None
    try:
        time.sleep(.5)
        assert tunnel.poll() is None, 'Gate tunnel failed'
        if set(PLAN['gates']) & {'hid','media','hdmi-modes','4k60'}:
            bridge = subprocess.Popen([sys.executable,str(OUT/'m6-bridge.py')],env=env,
                                      stdout=(LOG/'bridge.log').open('w'),stderr=subprocess.STDOUT)
            gates = load(KERNEL/'formal-gates.py')
            gates.LOGS=LOG;gates.HOST=HOST;gates.RECEIVER_IP=RECEIVER_IP
            # The reviewed bootstrap intentionally requires the operator's scene replies.
            session = load(OUT/'m6-session.py').Session(PLAN,gates,bw,LOG)
            original_env = dict(os.environ)
            os.environ.update(env)
            try:
                session.m6_scene()
                session.m6_bootstrap()
            finally:
                os.environ.clear();os.environ.update(original_env)
        for gate in PLAN['gates']:
            run([sys.executable,str(KERNEL/'formal-gates.py'),gate,'--logs',str(LOG),
                 '--plan',str(PLAN_PATH)],'gate-'+gate+'.log',900,env=env)
    finally:
        try:
            if (LOG/'video-saved.json').exists():
                run([sys.executable,str(KERNEL/'formal-gates.py'),'cleanup','--logs',str(LOG),
                     '--plan',str(PLAN_PATH)],'gate-final-cleanup.log',120,env=env)
            if session:
                session.close_m6_tools()
        finally:
            for process in (bridge,tunnel):
                if process:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: process.kill();process.wait()


def publish(plan, logs, kernel=KERNEL):
    new = tomllib.loads((kernel/'sources.toml').read_text())['tested_build']
    result = json.loads((logs/'result.json').read_text())
    proof = json.loads((logs/'installed-proof.json').read_text())
    baseline = json.loads((logs/'new-baseline.json').read_text())
    runtime = json.loads((logs/'runtime-build.json').read_text())
    if not result.get('retained_default') or result['release'] != plan['release'] or new['release'] != plan['release']:
        raise ValueError('No successful retained deployment for tested_build')
    if result['gates'] != plan['gates'] or result['package_sha256'] != new['package_sha256']:
        raise ValueError('Result gates/package differ from plan/lock')
    for value in (proof, baseline):
        if value['release'] != new['release'] or value.get('build_id') != new['build_id']:
            raise ValueError('Proof identity differs from tested_build')
    if proof['manifest_sha256'] != new['manifest_sha256'] or proof['baseline_proof_sha256'] != sha(logs/'new-baseline.json'):
        raise ValueError('Proof digest mismatch')
    if proof.get('source') != new['image_source_revision']:
        raise ValueError('Proof source differs from tested_build')
    if runtime['running'] != new['release']:
        raise ValueError('Runtime receipt differs from installed release')
    if sha(logs/'runtime-build.json') != baseline['files']['/etc/vim4-kvm/runtime-build.json']:
        raise ValueError('Runtime receipt hash differs from installed baseline')
    target = kernel/'releases'/new['release']
    target.mkdir(parents=True,exist_ok=True)
    for source,destination in (('installed-proof.json','installed-proof.json'),
                               ('new-baseline.json','baseline.json'),('runtime-build.json','runtime-build.json')):
        shutil.copyfile(logs/source,target/destination)
    values = dict(release=new['release'],revision=new['image_source_revision'],build_id=new['build_id'],
                  image_sha256=new['image_sha256'],board_dtb_sha256=new['board_dtb_sha256'],
                  manifest_sha256=new['manifest_sha256'],package_sha256=new['package_sha256'],
                  module_count=new['module_count'],default_boot='Mainline',evidence=plan['record'],
                  installed_proof_path='releases/'+new['release']+'/installed-proof.json',
                  live_proof_sha256=sha(target/'installed-proof.json'),
                  kernels_manifest_sha256=proof['kernels_sha256'],
                  baseline_proof_path='releases/'+new['release']+'/baseline.json',
                  baseline_proof_sha256=sha(target/'baseline.json'))
    path = kernel/'sources.toml'
    text = path.read_text()
    section = '[retained_runtime]\n' + ''.join(k+' = '+json.dumps(v)+'\n' for k,v in values.items())+'\n'
    text = re.sub(r'\[retained_runtime\]\n.*?(?=\n\[|\Z)',lambda _:section,text,flags=re.S)
    path.write_text(text)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command',required=True)
    plan = commands.add_parser('plan',help='Offline: verify source lock and prepare reproducible inputs')
    plan.add_argument('--sources',default=str(KERNEL/'sources.toml'))
    plan.add_argument('--package',required=True)
    plan.add_argument('--rollback',required=True)
    plan.add_argument('--gates',type=gates_list,default=['decode-smoke'])
    plan.add_argument('--retire')
    plan.add_argument('--baseline-overlay',help='JSON object mapping existing protected paths to replacement SHA256')
    plan.add_argument('--record',required=True)
    plan.add_argument('--logs',required=True)
    plan.add_argument('--output',default=str(ROOT/'build/formal-deploy'))
    plan.add_argument('--host',default=HOST)
    plan.add_argument('--uart',default=UART)
    plan.add_argument('--receiver-ip',default=RECEIVER_IP)
    plan.add_argument('--playwright',default=PLAYWRIGHT)
    plan.add_argument('--gpu-cc',default='aarch64-linux-gnu-gcc',help='Local ARM64 compiler with EGL/GLES/GBM sysroot')
    plan.add_argument('--decode-assets')
    plan.add_argument('--decode-assets-sha256')
    for command in ('execute','publish'):
        child = commands.add_parser(command)
        child.add_argument('--plan',required=True,type=Path)
    return p


def main():
    global PLAN_PATH
    arguments = sys.argv[1:]
    if not arguments or arguments[0].startswith('--'):
        arguments.insert(0,'plan')
    args = parser().parse_args(arguments)
    if args.command == 'plan':
        print(prepare_plan(args))
    else:
        PLAN_PATH=args.plan.resolve()
        plan=json.loads(PLAN_PATH.read_text())
        if args.command == 'publish':
            publish(plan,Path(plan['logs']),Path(plan['sources']).parent)
        else:
            configure(plan)
            execute()


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error))

