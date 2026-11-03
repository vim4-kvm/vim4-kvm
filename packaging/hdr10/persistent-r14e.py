#!/usr/bin/env python3
"""Install the sealed r14e userspace as a user-test candidate on installed uhd6.

Private regular files and a kernel-specific launcher replace RAM binds. Vendor
programs, user settings, the /lib symlink, kernel files and optional Panfrost DT
are retained. The installer does not select a kernel or reboot.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tarfile
import tempfile
import time

PREFIX = '/opt/vim4-kvm/hdr10-r14e'
RELEASE = '7.3.0-vim4kvm-uhd6+'
BOOT_DIR = Path('/boot/kernels') / RELEASE
KERNEL_SHA = '7e68dc27e46bb270d561f4307bba1cd947152ee3813a0a926f817f11f8e9dfc6'
USER_SHA = '9069fc083a8afe1a139e6d3e5eb725c608afafb4245ec3b155f873fd3f4a5b90'
UNITS = ['one-kvm.service', 'nanokvm.service', 'vim4-kvm.service', 'vim4-pikvm.service']
WRAPPER = '/usr/libexec/vim4-kvm-run'
RECEIPT = '/etc/vim4-kvm/hdr10-r14e.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()


def read_archive(path, expected):
    if file_sha(path) != expected:
        raise ValueError('Archive hash differs: '+str(path))
    files = {}
    with tarfile.open(path) as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if member.isdir(): continue
            if not member.isfile() or Path(name).is_absolute() or '..' in Path(name).parts or name in files:
                raise ValueError('Unsafe or duplicate archive member: '+name)
            files[name] = archive.extractfile(member).read()
    return files


def launcher(original):
    text = original.decode()
    marker = 'run_app() {\n'
    assert text.count(marker) == 1
    text = text.replace(marker, 'if [ "$(uname -r)" = '+repr(RELEASE)+' ]; then\n'
                        '    export GST_PLUGIN_PATH='+PREFIX+'/gstreamer-1.0\nfi\n'+marker)
    for app, previous, binary in (
            ('nanokvm', '/opt/vim4-nanokvm/NanoKVM-Server', 'nanokvm'),
            ('jetkvm', '/opt/vim4-jetkvm/jetkvm', 'jetkvm'),
            ('pikvm', '/usr/libexec/vim4-pikvm-run', 'pikvm-run')):
        old = f'    {app}) run_app {previous} ;;'
        assert text.count(old) == 1
        text = text.replace(old, f'    {app})\n'
            f'        if [ "$(uname -r)" = {RELEASE!r} ]; then run_app {PREFIX}/{binary}; fi\n'
            f'        run_app {previous} ;;')
    old = 'binary=/opt/vim4-onekvm-edge/one-kvm'
    assert text.count(old) == 1
    return text.replace(old, 'binary='+PREFIX+'/one-kvm').encode()


def prepare(args):
    kernel = read_archive(args.kernel, KERNEL_SHA)
    candidate = json.loads(kernel['candidate.json'])
    for name, expected in candidate['sha256'].items():
        if sha(kernel[name]) != expected: raise ValueError('Kernel package inventory differs: '+name)
    report = json.loads(kernel['manifest.json'])
    assert report['release'] == RELEASE and report['source'] == 'f951e2d24d32d5df0e701e7c355b3db4c91eaf74'
    module_files = {}
    with tarfile.open(fileobj=io.BytesIO(kernel['modules.tar.gz'])) as archive:
        for member in archive:
            if member.isdir(): continue
            assert member.isfile() and member.name.startswith(RELEASE+'/')
            name = member.name[len(RELEASE)+1:]
            assert name not in module_files
            module_files[name] = sha(archive.extractfile(member).read())
    assert module_files == report['modules']
    assert sum('.ko' in n for n in module_files) == 2341
    files = read_archive(args.userspace, USER_SHA)
    user = json.loads(files.pop('manifest.json'))
    assert {n:sha(b) for n,b in files.items()} == user['sha256']
    assert user['sources']['gst-vfmcap'] == '5de382e36350fc37b43d9ff11f693fa3f2bb0323'
    inputs = {n:base64.b64decode(b) for n,b in json.loads(args.inputs.read_text()).items()}
    helper = inputs['/usr/libexec/vim4-pikvm-run'].decode()
    assert helper.count("'/opt/vim4-pikvm/python/bin/kvmd', '--run'") == 1
    helper = helper.replace("'/opt/vim4-pikvm/python/bin/kvmd', '--run'",
        "'/opt/vim4-pikvm/python/bin/kvmd', '--main-config', '"+PREFIX+"/pikvm-main.yaml', '--run'")
    assert helper.count('--plugins-folder=/usr/lib/ustreamer/janus') == 1
    files['pikvm-run'] = helper.replace('--plugins-folder=/usr/lib/ustreamer/janus',
                                       '--plugins-folder='+PREFIX+'/janus').encode()
    yaml = inputs['/usr/lib/kvmd/main.yaml']
    assert yaml.count(b'- /usr/bin/ustreamer\n') == 1
    files['pikvm-main.yaml'] = yaml.replace(b'- /usr/bin/ustreamer\n', ('- '+PREFIX+'/ustreamer\n').encode())
    files['janus/libjanus_ustreamer.so'] = files.pop('libjanus_ustreamer.so')
    original = kernel['runtime/usr/libexec/vim4-kvm-run']
    files['installed-launcher'] = launcher(original)
    files['check-phase2-plugins.py'] = Path(__file__).with_name('check-phase2-plugins.py').read_bytes()
    base_files = {WRAPPER:sha(original), **{n:sha(b) for n,b in inputs.items()}}
    base_files.update({'/'+n.removeprefix('runtime/'):sha(b) for n,b in kernel.items()
                      if n.startswith('runtime/usr/')})
    boot_files = ('Image','vim4.dtb','panfrost.dtb','config','Module.symvers','vmlinux.btf','manifest.json')
    proof = dict(name='hdr10-r14e-user-test', hardware_validated=False, default_gpu='kbase',
        kernel_archive_sha256=KERNEL_SHA, userspace_archive_sha256=USER_SHA,
        release=RELEASE, kernel_source=report['source'], kernel_build_id=report['kernel_build_id'],
        modules=module_files, module_count=2341, sources=user['sources'],
        boot_files={str(BOOT_DIR/n):sha(kernel[n]) for n in boot_files}, base_files=base_files,
        files={n:sha(b) for n,b in files.items()},
        pending=['Pi finite-pool/JPEG/roundtrip/CMA', 'kbase HDR path', 'UU native HDR rendering',
                 'nonzero metadata, HLG and dynamic HDR without real source'])
    with tarfile.open(args.output,'x:gz') as archive:
        for name, data in {**files,'manifest.json':json.dumps(proof,indent=2).encode()}.items():
            member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o755
            archive.addfile(member,io.BytesIO(data))
    args.output.with_suffix('.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(dict(archive=str(args.output),sha256=file_sha(args.output),files=len(files))))


def check_kernel(proof):
    if not Path('/lib').is_symlink(): raise ValueError('/lib must remain a symlink')
    for name, expected in proof['boot_files'].items():
        if sha(Path(name).read_bytes()) != expected: raise ValueError('Installed kernel differs: '+name)
    root=Path('/lib/modules')/RELEASE
    actual={str(p.relative_to(root)):file_sha(p)
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
    if actual != proof['modules']: raise ValueError('Complete installed module set differs')


def install(args):
    if os.geteuid()!=0:raise ValueError('root required')
    files=read_archive(args.archive,args.sha256);proof=json.loads(files.pop('manifest.json'))
    if {n:sha(b) for n,b in files.items()}!=proof['files']:raise ValueError('Overlay inventory differs')
    check_kernel(proof)
    for name,expected in proof['base_files'].items():
        if sha(Path(name).read_bytes())!=expected:raise ValueError('Installed runtime changed: '+name)
    for lun in Path('/sys/kernel/config/usb_gadget').glob('*/functions/mass_storage.*/lun.*/file'):
        if lun.read_text().strip():raise ValueError('Mounted virtual media; eject before reboot')
    prefix=Path(PREFIX)
    if prefix.exists():raise ValueError('Private installation prefix already exists')
    backup=Path('/var/lib/vim4-kvm')/('before-hdr10-r14e-'+str(time.time_ns()))
    backup.mkdir(parents=True)
    protected=(WRAPPER,'/etc/vim4-kvm/runtime-build.json',RECEIPT)
    saved={p:base64.b64encode(Path(p).read_bytes()).decode() if Path(p).exists() else None for p in protected}
    (backup/'files.json').write_text(json.dumps(saved))
    (backup/'extlinux.conf').write_bytes(Path('/boot/extlinux/extlinux.conf').read_bytes())
    sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4boot
    active=[u for u in UNITS if subprocess.run(['systemctl','is-active','--quiet',u]).returncode==0]
    subprocess.run(['systemctl','stop',*UNITS],check=True,timeout=45)
    try:
        prefix.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=prefix.parent,prefix='.r14e-') as temporary:
            stage=Path(temporary)/'files';stage.mkdir()
            for name,data in files.items():
                target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data);target.chmod(0o755)
            (stage/'manifest.json').write_text(json.dumps(proof,indent=2)+'\n')
            stage.rename(prefix)
        vim4boot.atomic_write(Path(WRAPPER),files['installed-launcher']);Path(WRAPPER).chmod(0o755)
        record=json.loads(Path('/etc/vim4-kvm/runtime-build.json').read_text())
        record.update(manual_test_candidate='hdr10-r14e',kernel_source=proof['kernel_source'],
            kernel_build_id=proof['kernel_build_id'],module_count=2341,
            deployed_components={**record.get('deployed_components',{}),
                'kernel':proof['kernel_source'],'capture':proof['sources']['gst-vfmcap'],
                'encoder':proof['sources']['gst-venc'],'onekvm':proof['sources']['One-KVM'],
                'nanokvm':proof['sources']['NanoKVM'],'jetkvm':proof['sources']['kvm'],
                'ustreamer':proof['sources']['ustreamer']},
            hdr10_r14e=dict(archive_sha256=args.sha256,userspace_sha256=USER_SHA,prefix=PREFIX,
                           hardware_validated=False,pending=proof['pending']))
        vim4boot.atomic_write(Path('/etc/vim4-kvm/runtime-build.json'),json.dumps(record,indent=2).encode())
        receipt=dict(proof,installed=True,acceptance='user-manual-test-candidate',backup=str(backup),
                     installation_archive_sha256=args.sha256,installed_at=time.time())
        vim4boot.atomic_write(Path(RECEIPT),json.dumps(receipt,indent=2).encode())
        subprocess.run(['sh','-n',WRAPPER],check=True)
        assert Path('/lib').is_symlink()
        assert all(sha((prefix/n).read_bytes())==v for n,v in proof['files'].items())
        os.sync()
    except BaseException:
        for name,value in saved.items():
            if value is None:Path(name).unlink(missing_ok=True)
            else:vim4boot.atomic_write(Path(name),base64.b64decode(value))
        Path(WRAPPER).chmod(0o755)
        subprocess.run(['systemctl','start',*active],check=True,timeout=45)
        raise
    subprocess.run(['systemctl','start',*active],check=True,timeout=45)
    print(json.dumps(dict(installed=True,prefix=PREFIX,backup=str(backup),default_changed=False)))


def note_id(data):
    offset=0
    while offset+12<=len(data):
        n,d,kind=struct.unpack_from('<III',data,offset);offset+=12
        start=offset+((n+3)&~3)
        if data[offset:offset+n]==b'GNU\0' and kind==3:return data[start:start+d].hex()
        offset=start+((d+3)&~3)
    raise ValueError('GNU build ID missing')


def one_kvm_pid(group,proc_root=Path('/proc')):
    # kbase's graphics wrapper remains the systemd MainPID. Locate only the
    # actual program inside this service, excluding the wrapper and ttyd.
    matches=[int(pid) for pid in (group/'cgroup.procs').read_text().split()
             if (proc_root/pid/'exe').resolve()==Path(PREFIX).resolve()/'one-kvm']
    if len(matches)!=1:raise ValueError('Expected one r14e One-KVM process in service cgroup')
    return matches[0]


def verify(args):
    proof=json.loads(Path(RECEIPT).read_text());prefix=Path(PREFIX)
    assert platform.release()==RELEASE
    assert 'init=' not in Path('/proc/cmdline').read_text(),'Expected normal persistent boot'
    assert note_id(Path('/sys/kernel/notes').read_bytes())==proof['kernel_build_id']
    sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4boot
    assert vim4boot.default_label(vim4boot.CONFIG.read_text())=='Mainline'
    assert Path('/lib').is_symlink()
    for name,expected in proof['files'].items():
        assert file_sha(prefix/name)==expected,name
    assert file_sha(Path(WRAPPER))==proof['files']['installed-launcher']
    for name,expected in proof['boot_files'].items():assert file_sha(Path(name))==expected,name
    manifest=json.loads((BOOT_DIR/'manifest.json').read_text())
    by_name={Path(n).name.split('.ko')[0].replace('-','_'):n for n in manifest['module_build_ids']}
    modules={}
    for name in ('mali_kbase','vim4_kbase_heaps','governor_vim4','wave5','t7_hdmirx',
                 't7_vdin_test','t7_jpeg','crg_udc','dwmac_meson8b'):
        actual=note_id((Path('/sys/module')/name/'notes/.note.gnu.build-id').read_bytes())
        relative=by_name[name]
        assert actual==manifest['module_build_ids'][relative],name
        disk=Path('/lib/modules')/RELEASE/relative
        assert file_sha(disk)==proof['modules'][relative],name
        modules[name]=dict(build_id=actual,sha256=file_sha(disk))
    assert Path('/sys/bus/platform/devices/fe400000.gpu/driver').resolve().name=='mali'
    units=['one-kvm','vim4-manager','vim4-kvm-hdmi','vim4-kvm-gadget']
    for name in units:subprocess.run(['systemctl','is-active','--quiet',name],check=True)
    assert any(p.read_text().strip()=='configured' for p in Path('/sys/class/udc').glob('*/state'))
    for unit in UNITS:
        assert subprocess.check_output(['systemctl','show','-p','LoadState','--value',unit],text=True).strip()=='loaded',unit
    group=subprocess.check_output(['systemctl','show','-p','ControlGroup','--value','one-kvm'],text=True).strip()
    pid=one_kvm_pid(Path('/sys/fs/cgroup')/group.lstrip('/'))
    assert file_sha(Path('/proc')/str(pid)/'exe')==proof['files']['one-kvm']
    mapped={line.split()[-1] for line in (Path('/proc')/str(pid)/'maps').read_text().splitlines()
            if PREFIX+'/gstreamer-1.0/' in line}
    plugin_hashes={p:file_sha(Path(p)) for p in mapped}
    plugins=json.loads(subprocess.check_output(['runuser','-u','khadas','--','python3',
        str(prefix/'check-phase2-plugins.py'),str(prefix/'gstreamer-1.0'),'--device-factories'],text=True,timeout=60))
    status=dict(release=platform.release(),kernel_build_id=proof['kernel_build_id'],default='Mainline',
        module_count=2341,loaded_modules=modules,one_kvm_sha256=file_sha(Path('/proc')/str(pid)/'exe'),
        loaded_application_plugins=plugin_hashes,plugin_factories=plugins,apps_available=UNITS,
        tainted=int(Path('/proc/sys/kernel/tainted').read_text()),hardware_validated=False,
        acceptance='installation-sanity-only-user-manual-test',pending=proof['pending'])
    assert status['tainted']==4096,'Unexpected taint (kbase out-of-tree bit expected)'
    record=json.loads(Path('/etc/vim4-kvm/runtime-build.json').read_text())
    record.update(running=RELEASE,default='Mainline',loaded_module_build_ids={n:v['build_id'] for n,v in modules.items()},
                  module_archive_sha256=manifest['files']['modules.tar.gz'],
                  config_sha256=proof['boot_files'][str(BOOT_DIR/'config')],
                  tainted=status['tainted'],services={n:'active' for n in units},observed_at=time.time())
    record.setdefault('sha256',{}).update({PREFIX+'/'+n:h for n,h in proof['files'].items()})
    record['sha256'].update(proof['boot_files']);record['sha256'][WRAPPER]=file_sha(Path(WRAPPER))
    vim4boot.atomic_write(Path('/etc/vim4-kvm/runtime-build.json'),json.dumps(record,indent=2).encode())
    vim4boot.atomic_write(Path('/var/lib/vim4-kvm/hdr10-r14e-sanity.json'),json.dumps(status,indent=2).encode())
    print(json.dumps(status))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    build=s.add_parser('prepare')
    for key in ('kernel','userspace','inputs','output'):build.add_argument('--'+key,type=Path,required=True)
    run=s.add_parser('install');run.add_argument('archive',type=Path);run.add_argument('--sha256',required=True)
    s.add_parser('verify')
    a=p.parse_args();{'prepare':prepare,'install':install,'verify':verify}[a.command](a)
