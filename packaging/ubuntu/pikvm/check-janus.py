"""Exercise the actual Janus WebSocket transport and uStreamer plugin ABI."""
import json
from pathlib import Path
import subprocess
import tempfile
import time

import websocket


with tempfile.TemporaryDirectory() as directory:
    config = Path(directory)
    (config / 'janus.jcfg').write_text('general: { debug_level = 4 }\n')
    (config / 'janus.transport.websockets.jcfg').write_text(
        'general: { ws = true; ws_ip = "127.0.0.1"; ws_port = 18188; }\n')
    (config / 'janus.plugin.ustreamer.jcfg').write_text(
        'video: { sink = "vim4-pikvm-build-check"; }\n')
    with (config / 'janus.log').open('w+') as log:
        process = subprocess.Popen(['/usr/bin/janus', '--disable-colors',
                                    '--plugins-folder=/usr/lib/ustreamer/janus',
                                    '--configs-folder=' + directory], stdout=log, stderr=log)
        connection = None
        try:
            deadline = time.monotonic() + 10
            while connection is None:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Janus did not start')
                try:
                    connection = websocket.create_connection('ws://127.0.0.1:18188',
                                                              subprotocols=['janus-protocol'], timeout=1)
                except (OSError, websocket.WebSocketException):
                    time.sleep(0.1)

            def request(message):
                message['transaction'] = 'build-check'
                connection.send(json.dumps(message))
                return json.loads(connection.recv())

            info = request({'janus': 'info'})
            assert 'janus.plugin.ustreamer' in info['plugins'], info
            session = request({'janus': 'create'})['data']['id']
            handle = request({'janus': 'attach', 'session_id': session, 'plugin': 'janus.plugin.ustreamer'})
            assert handle['janus'] == 'success', handle
            reply = request({'janus': 'destroy', 'session_id': session})
            assert reply['janus'] == 'success', reply
            print('PASS: Janus WebSocket session and uStreamer plugin attach/destroy')
        finally:
            if connection:
                connection.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.seek(0)
            print(log.read())
