#!/usr/bin/env python3
"""One unattended P0-5 command, prepared offline; no ticket before main uhd6.

--plan-only validates both payloads without board access (dry-run uhd5 allowed).
Normal invocation verifies origin/main locks, then enters board-queue once.
All actions run through board-window's ticket, MCP, SSH and RAM-boot contracts.
"""
import argparse
import base64
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
import tomllib
import urllib.request

REPO=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
UU=Path('/Applications/UURemote.app/Contents/Helpers/uuyc-cli')
FAULT=r'WARNING:|BUG:|Oops:|GPU [Ff]ault|job [Ff]ault|Kernel panic|cma_alloc.*fail'
# The real finally order, including bounded local cleanup. Reconnect includes
# reaping the old tunnel, the last HTTP readiness request and failure cleanup.
RECOVERY_SECONDS = {'collect':45, 'baseline':300, 'reconnect':45, 'config':65,
                    'source':120, 'sampling':10, 'tunnel':10}
LOCAL_CLEANUP_SECONDS = RECOVERY_SECONDS['sampling'] + RECOVERY_SECONDS['tunnel']
REQUIRED_RECOVERY_SECONDS = sum(RECOVERY_SECONDS.values()) - RECOVERY_SECONDS['collect']
# Fault stop can run in parallel with child/UU/thread unwinding. A current
# workload operation has already reserved its own timeout before this margin.
UNWIND_SECONDS = max(RECOVERY_SECONDS['config'], 15 + 16 + 15 + 12)
RECOVERY_RESERVE = sum(RECOVERY_SECONDS.values()) + UNWIND_SECONDS + 15


def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path))
    spec=importlib.util.spec_from_loader(name,loader)
    module=importlib.util.module_from_spec(spec); loader.exec_module(module); return module


w=load('board_window',REPO/'tools/board-window')
g=load('m6_gates',HERE/'m6-gates.py')


def payload(path,sha):
    if w.sha(path)!=sha: raise ValueError('payload SHA mismatch')
    plan=w.validate_bundle(path)
    with tarfile.open(path) as archive: manifest=json.load(archive.extractfile('manifest.json'))
    return dict(plan=plan,manifest=manifest)


def preflight(args, sources=None):
    result={gpu:payload(getattr(args,gpu),getattr(args,gpu+'_sha256')) for gpu in ('panfrost','kbase')}
    if not args.observer.is_file() or not os.access(args.observer,os.X_OK): raise ValueError('compile screenshot observer offline first')
    for gpu,item in result.items():
        if item['manifest']['gpu']!=gpu: raise ValueError('GPU payload mislabeled')
    if sources is not None:
        lock=sources['tested_build']
        if not lock['release'].startswith('7.3.0-vim4kvm-uhd6'): raise ValueError('main has no tested uhd6; no board ticket taken')
        for item in result.values():
            m=item['manifest']
            if m.get('dry_run') or m['release']!=lock['release'] or m['build_id']!=lock['build_id'] or \
                m['kernel_archive_sha256']!=lock['package_sha256'] or m['sha256']['Image']!=lock['image_sha256']:
                raise ValueError('payload does not match main tested_build; no board ticket taken')
        if not shutil.which(args.ffmpeg): raise ValueError('FFmpeg required for offline bitstream checks')
        if not os.environ.get('MANAGER_PASSWORD'): raise ValueError('set manager credentials before taking a board ticket')
    files=json.loads(args.baseline_files.read_text())
    if not isinstance(files,list) or not files or any(not isinstance(name,str) or not name.startswith('/') for name in files):
        raise ValueError('baseline-files must list absolute protected baseline paths')
    return result


def uu_device(cli, requested=None):
    if not cli.is_file(): raise ValueError('official UU CLI missing')
    status=json.loads(subprocess.check_output([str(cli),'device','status'],text=True))
    if not status.get('success') or status['data']['hasActiveConnections']:
        raise ValueError('official UU client is busy; no takeover')
    devices=json.loads(subprocess.check_output([str(cli),'device','list'],text=True))['data']['devices']
    matches=[d for d in devices if d['isOnline'] and (d['deviceId']==requested if requested else d['deviceName'].lower()=='vim4-kvm')]
    if len(matches)!=1: raise ValueError('expected one online VIM4 UU device')
    return matches[0]['deviceId']


class Window:
    def __init__(self,args):
        self.args=args; self.output=REPO/'logs'/args.window
        self.output.mkdir(parents=True,exist_ok=False)
        self.failures=[]; self.child=None; self.number=0
        self.operations=threading.Lock()
        self.expected_taint=0
        self.remote='/var/tmp/'+args.window
        self.deadline=time.monotonic()+30*60-RECOVERY_RESERVE

    def require_lease(self,seconds):
        queue,token=w.require_board()
        lease=queue.read(token)
        remaining=lease['started']+lease['seconds']-time.time()
        if lease['state']!='held' or lease['heavy'] or remaining<seconds:
            raise RuntimeError('board lease cannot cover this operation')

    def require_work(self,seconds=0):
        if self.failures: raise RuntimeError('monitor rejected workload: '+'; '.join(self.failures))
        if time.monotonic()+seconds>self.deadline: raise RuntimeError('workload deadline; reserve recovery time')
        self.require_lease(seconds+RECOVERY_RESERVE)

    def work_ssh(self,command,timeout=RECOVERY_SECONDS['config']):
        with self.operations:
            self.require_work(timeout)
            return w.ssh('vim4',command,timeout=timeout)

    def command(self,command,timeout=60):
        self.number+=1
        path=self.output/f'{self.number:03}-command.log'
        with path.open('w') as log:
            with self.operations:
                self.require_work(timeout)
                self.child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                until=min(self.deadline,time.monotonic()+timeout)
                while self.child.poll() is None:
                    try:
                        self.require_work()
                        if time.monotonic()>until: raise RuntimeError('window command timed out')
                    except Exception:
                        os.killpg(self.child.pid,signal.SIGTERM)
                        try: self.child.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(self.child.pid,signal.SIGKILL)
                            self.child.wait(timeout=5)
                        raise
                    time.sleep(.2)
                if self.child.returncode: raise RuntimeError('window command failed: '+str(path))
            finally: self.child=None

    def cli(self,*args,timeout=300):
        if args[0]!='boot-candidate': raise ValueError('use the restricted recovery CLI for collection/return')
        with self.operations:
            self.require_work(timeout)
            self._cli(args,timeout)

    def recovery_cli(self,*args,reserve_after=0):
        if args==('collect','--readonly'): timeout=RECOVERY_SECONDS['collect']
        elif args==('return-baseline',): timeout=RECOVERY_SECONDS['baseline']
        else: raise ValueError('not an allowed recovery CLI operation')
        with self.operations:
            try: self.require_lease(timeout+reserve_after)
            except RuntimeError as error:
                if args[0]!='collect': raise
                (self.output/'collection-skipped.json').write_text(json.dumps(dict(reason=str(error))))
                return False
            self._cli(args,timeout)
            return True

    def _cli(self,args,timeout):
        subprocess.run([str(REPO/'tools/board-window'),'--window',self.args.window,
            '--device',self.args.device,*map(str,args)],check=True,timeout=timeout)

    def board(self,operation,*args):
        if operation not in ('save','configure','stop','status','metadata','plugins'):
            raise ValueError('not an allowed workload operation')
        with self.operations:
            self.require_work(RECOVERY_SECONDS['config'])
            return self._board(operation,args)

    def recovery_board(self,operation,reserve_after=0):
        if operation not in ('stop','status','restore'): raise ValueError('not an allowed recovery board operation')
        with self.operations:
            self.require_lease(RECOVERY_SECONDS['config']+reserve_after)
            return self._board(operation,())

    def _board(self,operation,args):
        command=['sudo','-n','python3',self.remote+'.py',operation,'--checkpoint',self.remote+'.json',*args]
        value=w.ssh('vim4',shlex.join(command),timeout=RECOVERY_SECONDS['config'])
        if value.strip():
            self.number+=1; (self.output/f'{self.number:03}-{operation}.json').write_text(value)
        return value

    def halt(self,reason,ready=None):
        # Latch cancellation before waiting for an in-flight configure. The
        # shared operation lock orders its completion before stop; every later
        # workload checks the latch while holding that same lock.
        self.failures.append(reason)
        if ready is not None: ready.set()
        try: self.recovery_board('stop',reserve_after=REQUIRED_RECOVERY_SECONDS)
        except Exception as error:
            self.failures.append('fault stop failed: '+str(error))
            (self.output/'fault-stop-error.log').write_text(str(error))

    def screenshot(self,client,path):
        with self.operations:
            self.require_work(40)
            client.screenshot(path)

    def api(self,path,value=None,method=None):
        request=urllib.request.Request('http://127.0.0.1:18081/api/'+path,
            data=None if value is None else json.dumps(value).encode(),
            headers={'Content-Type':'application/json'},method=method)
        return json.load(urllib.request.urlopen(request,timeout=15))

    def open_tunnel(self, previous=None, recovery=False,reserve_after=0):
        # A RAM reboot can leave the old SSH process alive briefly while its
        # forwarding channel is already unusable. Recreate our own transport
        # after every boot, including the final baseline return.
        if recovery: self.require_lease(RECOVERY_SECONDS['reconnect']+reserve_after)
        else: self.require_work(RECOVERY_SECONDS['reconnect'])
        if previous is not None:
            previous.terminate(); previous.wait(timeout=10)
        tunnel=subprocess.Popen(['ssh','-N','-oExitOnForwardFailure=yes',
            '-L','18081:127.0.0.1:8081','vim4'])
        until=time.monotonic()+8
        try:
            while True:
                try:
                    self.api('vim4/video')
                    return tunnel
                except OSError:
                    if tunnel.poll() is not None or time.monotonic()>until: raise
                    time.sleep(.2)
        except Exception:
            tunnel.terminate(); tunnel.wait(timeout=10)
            raise

    def watch(self,event,ready=None):
        try:
            initial=w.ssh('vim4','sudo -n dmesg',timeout=5)
            taint=w.ssh('vim4','cat /proc/sys/kernel/tainted',timeout=5).strip()
        except Exception as error:
            self.halt('initial monitor read failed: '+str(error),ready)
            return
        if re.search(FAULT,initial) or int(taint)!=self.expected_taint:
            (self.output/'boot-fault.log').write_text(initial)
            self.halt('boot fault/taint',ready); return
        if ready is not None: ready.set()
        while not event.wait(2):
            try:
                current=w.ssh('vim4','sudo -n dmesg',timeout=5)
                new=current[len(initial):] if current.startswith(initial) else current
                taint=w.ssh('vim4','cat /proc/sys/kernel/tainted',timeout=5).strip()
                if re.search(FAULT,new) or int(taint)!=self.expected_taint:
                    (self.output/'first-fault.log').write_text(new+'\ntaint='+taint)
                    self.halt('kernel fault/taint'); return
            except Exception as error:
                self.halt('monitor failed: '+str(error)); return

    def uu(self,gpu):
        """Actual official client + fresh Receiver Reports; never send HID.

        Its remembered HDR opt-in is respected. No admin override bypasses the
        native client's capability checks. PQ/Main10 is checked on the shared
        producer by the independent receiver, not inferred from sender FPS.
        """
        device=self.args.uu_device_id
        if self.api('config/uu-remote')['status']['device_id']!=device:
            raise RuntimeError('selected official UU target does not belong to this board')
        self.command([str(self.args.uu_cli),'device','connect',device],timeout=20)
        samples=[]; done=threading.Event()
        def sample():
            while not done.is_set():
                try:
                    sessions=self.api('config/uu-remote')['status']['sessions']
                    samples.append(dict(time=time.time(),sessions=sessions))
                except OSError: pass
                done.wait(1)
        thread=threading.Thread(target=sample,daemon=True); thread.start()
        try:
            self.command(['node',str(HERE/'application-receiver.mjs'),self.args.url,'onekvm',
                str(self.output/f'{gpu}-uu-shared-main10'),'pq','15','','',self.args.local_ip],timeout=65)
            remote=[session for row in samples for session in row['sessions'] if session['state']=='connected'
                and session['video_codec'].lower() in ('h265','hevc')
                and (session.get('video_stats') or {}).get('receiver') is not None]
            fresh=[s for s in remote if s['video_stats']['receiver']['age_ms']<6000
                and s['video_stats']['receiver']['total_lost']==0]
            if len(fresh)<2: raise RuntimeError('no fresh official-client HEVC Receiver Reports')
            (self.output/f'{gpu}-uu-receive.json').write_text(json.dumps(dict(
                official_client=True,shared_producer='Main10/PQ independently captured',receiver_reports=samples,
                proves='RTP reception; does not prove UU decoder/rendering or optical HDR'),indent=2))
        finally:
            done.set(); thread.join(timeout=16)
            subprocess.run([str(self.args.uu_cli),'device','disconnect',device],check=True,timeout=15,
                stdout=subprocess.DEVNULL)

    def run(self):
        queue,token=w.require_board()
        key=json.loads(w.ssh('vim4','cat /var/lib/one-kvm/mcp/credentials.json'))['api_key']
        tunnel=None
        client=w.MCP('http://127.0.0.1:18081/api/mcp',key)
        m6=g.M6(client,lambda:w.source_hdr('vim4'),self.args.observer,self.output/'m6')
        saved=False; booted=False
        try:
            queue.sampling(token,True)
            tunnel=self.open_tunnel()
            initial_hdr=w.source_hdr('vim4')
            if initial_hdr is not False: raise RuntimeError('start with M6 HDR off')
            if not client.idle(self.output)['idle']: raise RuntimeError('M6 is not visually idle')
            m6.qualify(initial_hdr)
            data=base64.b64encode((HERE/'phase2-board.py').read_bytes()).decode()
            script=f"from pathlib import Path; import base64; p=Path({self.remote+'.py'!r}); p.write_bytes(base64.b64decode({data!r})); p.chmod(0o700)"
            self.work_ssh('sudo -n python3 -c '+shlex.quote(script))
            self.board('save'); saved=True
            with self.operations:
                self.require_work(120)
                m6.toggle(True); m6.close()
            for gpu in ('panfrost','kbase'):
                # The matched uhd6 kbase modules intentionally set TAINT_OOT_MODULE.
                # All other taint bits and all WARN/faults remain failures.
                self.expected_taint=4096 if gpu=='kbase' else 0
                booted=True
                self.cli('boot-candidate',getattr(self.args,gpu),'--sha256',getattr(self.args,gpu+'_sha256'),
                    '--baseline-files',*json.loads(self.args.baseline_files.read_text()))
                tunnel=self.open_tunnel(tunnel)
                end=threading.Event(); ready=threading.Event()
                monitor=threading.Thread(target=self.watch,args=(end,ready),daemon=True); monitor.start()
                try:
                    if not ready.wait(8) or self.failures: raise RuntimeError('kernel monitor startup failed')
                    self.board('plugins')
                    self.board('stop'); before=json.loads(self.board('status'))['cma']['CmaFree']
                    self.board('configure','--app','onekvm')
                    (self.output/f'{gpu}-hdmi-metadata.json').write_text(self.board('metadata'))
                    seconds=180 if gpu=='panfrost' else 10
                    self.command(['node',str(HERE/'application-receiver.mjs'),self.args.url,'onekvm',
                        str(self.output/f'{gpu}-onekvm-native'),'pq',str(seconds),'3840','2160',
                        self.args.local_ip],timeout=seconds+70)
                    self.screenshot(client,self.output/f'{gpu}-native-sdr-snapshot.jpg')
                    for app in ('nanokvm','jetkvm','pikvm'):
                        for name,height,hdr in (('native',0,'on'),('scaled',1080,'on'),('mapped',1080,'off'),('restored',0,'on')):
                            self.board('configure','--app',app,'--height',str(height),'--hdr',hdr)
                            url=self.args.url.rstrip('/')+('/kvm/' if app=='pikvm' else '/')
                            self.command(['node',str(HERE/'application-receiver.mjs'),url,app,
                                str(self.output/f'{gpu}-{app}-{name}'),'pq' if hdr=='on' else 'sdr','10',
                                '1920' if height else '3840',str(height or 2160)],timeout=65)
                    self.board('stop')
                    after=json.loads(self.board('status'))
                    if after['taint']!=self.expected_taint or after['cma']['CmaFree']<before:
                        raise RuntimeError('CMA not fully returned or taint changed')
                    self.recovery_cli('collect','--readonly',reserve_after=RECOVERY_RESERVE)
                    self.board('configure','--app','onekvm')
                    self.uu(gpu)
                    self.board('stop')
                    final=json.loads(self.board('status'))
                    if final['taint']!=self.expected_taint or final['cma']['CmaFree']<before:
                        raise RuntimeError('UU teardown did not return CMA or taint changed')
                finally:
                    end.set(); monitor.join(timeout=12)
                if self.failures: raise RuntimeError('; '.join(self.failures))
        finally:
            # Keep each recovery independent; a failed collection cannot skip
            # baseline return, config restoration or M6 HDR/window restoration.
            errors=[]
            def reconnect(reserve_after):
                nonlocal tunnel
                tunnel=self.open_tunnel(tunnel,recovery=True,reserve_after=reserve_after)
            def restore_source(reserve_after):
                with self.operations:
                    self.require_lease(RECOVERY_SECONDS['source']+reserve_after)
                    m6.restore()
            steps=[]
            if booted:
                steps.extend([
                    ('baseline',lambda reserve:self.recovery_cli('return-baseline',reserve_after=reserve)),
                    ('reconnect',reconnect)])
            if saved:
                steps.append(('config',lambda reserve:self.recovery_board('restore',reserve_after=reserve)))
            if m6.restore_needed:
                steps.append(('source',restore_source))
            remaining=sum(RECOVERY_SECONDS[name] for name,_ in steps)+LOCAL_CLEANUP_SECONDS
            try: self.recovery_cli('collect','--readonly',reserve_after=remaining)
            except Exception as error: errors.append(str(error))
            for name,action in steps:
                remaining-=RECOVERY_SECONDS[name]
                try: action(remaining)
                except Exception as error: errors.append(name+': '+str(error))
            # Queue release must not consume an unbounded part of the lease.
            try:
                subprocess.run([str(REPO/'tools/board-queue'),'--root',str(queue.root),
                    'sampling','--ticket',token,'off'],check=True,capture_output=True,text=True,
                    timeout=RECOVERY_SECONDS['sampling'])
            except Exception as error: errors.append('sampling: '+str(error))
            try:
                if tunnel is not None:
                    tunnel.terminate(); tunnel.wait(timeout=RECOVERY_SECONDS['tunnel'])
            except Exception as error: errors.append('tunnel: '+str(error))
            (self.output/'recovery.json').write_text(json.dumps(dict(errors=errors,
                source_recovery_pending=m6.restore_needed),indent=2))
            if errors: raise RuntimeError('Recovery incomplete: '+'; '.join(errors))


def main():
    def terminated(signum,frame):
        # board-queue forwards termination to this child. Unwind through the
        # same recovery path as a failed receiver rather than abandoning M6.
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,terminated)
    parser=argparse.ArgumentParser(description=__doc__)
    for gpu in ('panfrost','kbase'):
        parser.add_argument('--'+gpu,type=Path,required=True)
        parser.add_argument('--'+gpu+'-sha256',required=True)
    parser.add_argument('--observer',type=Path,required=True)
    parser.add_argument('--baseline-files',type=Path,required=True)
    parser.add_argument('--url',default='http://192.168.50.210:8080')
    parser.add_argument('--local-ip',default='192.168.50.239')
    parser.add_argument('--device',default='/dev/cu.usbserial-1100')
    parser.add_argument('--window',default='hdr10-phase2-'+str(int(time.time())))
    parser.add_argument('--uu-cli',type=Path,default=UU)
    parser.add_argument('--uu-device-id')
    parser.add_argument('--ffmpeg',default='ffmpeg',help='local executable for post-window SPS/VUI checks')
    parser.add_argument('--plan-only',action='store_true')
    parser.add_argument('--execute',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.plan_only:
        data=preflight(args)
        print(json.dumps(dict(estimated_minutes=15,hard_max_minutes=30,stability_seconds=180,
            dry_run={k:v['manifest'].get('dry_run',False) for k,v in data.items()},
            board_access=False,uu_official_receive='official client RR plus independently captured shared Main10; rendering unverified')))
        return
    if not args.execute: subprocess.run(['git','fetch','origin'],cwd=REPO,check=True)
    sources=tomllib.loads(subprocess.check_output(['git','show','origin/main:packaging/kernel-edge/sources.toml'],cwd=REPO,text=True))
    preflight(args,sources)
    if args.execute: Window(args).run()
    else:
        device=uu_device(args.uu_cli,args.uu_device_id)
        command=[str(REPO/'tools/board-queue'),'run','--who','hdr10','--purpose',args.window,'--max-min','30','--',sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--uu-device-id',device,'--execute']
        subprocess.run(command,check=True)
        subprocess.run([str(REPO/'tools/board-queue'),'run','--heavy','--who','hdr10',
            '--purpose','phase2-bitstream-analysis','--',sys.executable,str(HERE/'analyze-phase2.py'),
            str(REPO/'logs'/args.window),'--ffmpeg',args.ffmpeg],check=True)


if __name__=='__main__': main()
