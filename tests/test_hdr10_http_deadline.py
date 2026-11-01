"""Real localhost headers/body trickle below each socket-read timeout."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import signal
import threading
import time
import unittest

from test_hdr10_phase2 import load

window=load('phase2-window')


class HttpDeadlineTests(unittest.TestCase):
    def exchange(self,phase,deadline):
        disconnected=threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                body=b'{"result":{}}'
                headers=b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'
                chunks=([headers[i:i+5] for i in range(0,len(headers),5)]+[body]
                    if phase=='headers' else [headers]+[bytes([b]) for b in body])
                try:
                    for index,chunk in enumerate(chunks):
                        if index:disconnected.wait(.04)
                        self.wfile.write(chunk);self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError):
                    disconnected.set()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
        thread.start()
        old_handler=signal.getsignal(signal.SIGALRM)
        client=window.w.MCP(f'http://127.0.0.1:{server.server_port}/mcp','fixture')
        start=time.monotonic()
        try:
            if deadline:
                with self.assertRaises(TimeoutError):client.rpc('initialize',{},deadline=start+.15)
                self.assertLess(time.monotonic()-start,.4)
                self.assertTrue(disconnected.wait(1),'timed-out HTTP request must close its socket')
            else:
                self.assertEqual(client.rpc('initialize',{}),{})
                self.assertGreater(time.monotonic()-start,.4)
            self.assertEqual(signal.getsignal(signal.SIGALRM),old_handler)
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.,0.))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=1)

    def test_slow_headers_are_aborted_and_connection_closed(self):
        self.exchange('headers',True)

    def test_continuously_arriving_body_is_aborted_and_connection_closed(self):
        self.exchange('body',True)

    def test_no_deadline_preserves_slow_response_behavior(self):
        self.exchange('body',False)


if __name__=='__main__':unittest.main()
