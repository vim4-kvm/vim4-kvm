"""M6 bootstrap with the deployment's reviewed screenshots and bounded human replies.

Sends HID only to the verified M6 scene. Unknown layout or missing reply aborts.
"""
import json
import select
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent

class Session:
    def __init__(self, plan, gates, bw, logs):
        global LOGS
        LOGS = logs
        self.plan, self.gates, self.bw = plan, gates, bw
        self.cutoff = time.time()+1200

    def run(self, argv, name, timeout):
        with (LOGS/name).open('w') as stream:
            subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=timeout)

    def review_screen(self, name):
        path = LOGS / (name + '.jpg')
        result=self.mcp.screenshot(path)
        text=' '.join(block.get('text','') for block in result['content'])
        assert __import__('re').search(r'Screen\s+1920\s*[x×]\s*1080',text), text
        print('REVIEW_SCREEN', path, 'reply go, us, or abort', flush=True)
        if not select.select([sys.stdin], [], [], min(120, self.cutoff-time.time()))[0]:
            raise TimeoutError('M6 screenshot review expired')
        reply = sys.stdin.readline().strip()
        assert reply in ('go', 'us'), 'M6 state not approved; stopping'
        return reply

    def select_input_source(self, name):
        self.mcp.call('left_click', {'coordinate':[1624,12]})
        time.sleep(.3)
        self.mcp.screenshot(LOGS/(name+'.jpg'))
        print('SELECT_SOURCE',LOGS/(name+'.jpg'),'reply x y for reviewed source row, or abort',flush=True)
        if not select.select([sys.stdin],[],[],min(120,self.cutoff-time.time()))[0]:
            raise TimeoutError('Input source review expired')
        point=list(map(int,sys.stdin.readline().strip().split()))
        assert len(point)==2 and 1450<=point[0]<1900 and 25<=point[1]<600
        self.mcp.call('left_click',{'coordinate':point})

    def m6_bootstrap(self):
        assert self.review_screen('m6-before-tools')=='go'
        # Dismiss only our uncommitted input from window8, then explicitly select US.
        self.mcp.call('hold_key', {'text':'Escape','duration':.1})
        self.select_input_source('m6-original-source-select-us')
        self.mcp.call('left_click', {'coordinate':[1376,1045]})
        time.sleep(.5)
        self.mcp.call('hold_key', {'text': 'super+n','duration':.15})
        time.sleep(.5)
        assert self.review_screen('m6-terminal') == 'go'
        command = f"curl -fsS http://{self.plan['receiver_ip']}:18274/b -o /tmp/d73;sh /tmp/d73"
        for character in command:
            self.mcp.call('hold_key', {'text': 'space' if character == ' ' else character, 'duration': .05})
            time.sleep(.02)
        assert self.review_screen('m6-bootstrap-command') == 'go'
        self.mcp.call('hold_key', {'text': 'enter','duration':.1})
        time.sleep(2)
        assert self.review_screen('m6-bootstrap-running') == 'go'
        self.gates.saved('m6-probe.log', self.gates.m6('probe'))
        self.mcp.call('left_click',{'coordinate':[523,1040]})

    def m6_scene(self):
        credentials = json.loads(self.bw.ssh(self.plan['host'], 'sudo -n cat /var/lib/one-kvm/mcp/credentials.json'))
        key = credentials.get('token') or credentials.get('api_key') or credentials.get('bearer_token')
        assert key
        self.mcp = self.bw.MCP('http://127.0.0.1:18088/api/mcp', key)
        self.mcp.screenshot(LOGS/'idle-before.jpg')
        time.sleep(2)
        self.mcp.screenshot(LOGS/'idle-after.jpg')
        self.run(['node',str(OUT/'m6-scene.mjs'),str(LOGS/'idle-before.jpg'),str(LOGS/'idle-after.jpg')], 'm6-scene.json',30)
        assert self.review_screen('m6-known-testufo') == 'go'
        self.gates.saved('video-saved.json', dict(video=self.gates.api('config/video'),mode=self.gates.api('stream/mode')))

    def close_m6_tools(self):
        if (LOGS/'m6-probe.log').exists():
            self.mcp.call('left_click',{'coordinate':[1376,1045]})
            assert self.review_screen('m6-own-terminal-before-close')=='go'
            self.mcp.call('hold_key',{'text':'super+w','duration':.15})
            self.select_input_source('m6-restore-original-source')
            self.mcp.call('left_click',{'coordinate':[523,1040]})
            time.sleep(.5)
            assert self.review_screen('m6-restored-testufo')=='go'


