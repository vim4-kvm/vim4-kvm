"""Real GStreamer/SCM_RIGHTS with file-backed memory, not VDIN DMA hardware."""
import array
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('BROKER_GST_PLUGIN'), 'Compiled GStreamer source required')
class GstBrokerTests(unittest.TestCase):
    def test_complete_frame_retains_fd_until_gstreamer_memory_release(self):
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        self.assertIsNotNone(Gst.Plugin.load_file(os.environ['BROKER_GST_PLUGIN']))
        failures, acknowledgements = [], []
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as pixels:
            pixels.truncate(64 * 32 * 3 // 2)
            path = str(Path(directory) / 'capture.sock')
            server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            server.bind(path)
            server.listen(1)
            server.settimeout(5)
            control = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            control.bind(str(Path(directory) / 'control.sock'))
            control.listen(1)
            control.settimeout(5)
            def state_reply():
                try:
                    with control.accept()[0] as client:
                        self.assertEqual(json.loads(client.recv(4096))['op'], 'status')
                        client.send(json.dumps(dict(version=1,state=dict(inputRate=5998))).encode())
                except BaseException as error:
                    failures.append(error)
            status_worker = threading.Thread(target=state_reply)
            status_worker.start()
            def reply():
                try:
                    with server.accept()[0] as client:
                        client.settimeout(5)
                        request = json.loads(client.recv(4096))
                        self.assertEqual(request['op'], 'subscribe')
                        client.send(json.dumps(dict(version=1, type='ready')).encode())
                        self.assertEqual(json.loads(client.recv(4096))['op'], 'take')
                        message = dict(version=1, type='frame', token=42, modifier=0,
                            format='NV12', allocation_size=64 * 32 * 3 // 2,
                            frame=dict(width=64, height=32, pitch=64, uv_offset=64*32,
                                       generation=3, timestamp_ns=1,
                                       colorspace='rec709', quantization='limited'))
                        client.sendmsg([json.dumps(message).encode()],
                            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i',[pixels.fileno()]))])
                        acknowledgements.append(json.loads(client.recv(4096)))
                except BaseException as error:
                    failures.append(error)
            worker = threading.Thread(target=reply)
            worker.start()
            with patch.dict(os.environ, VIM4_BROKER_SOCKET=path):
                pipeline = Gst.parse_launch('vim4brokersrc name=source num-buffers=1 ! fakesink sync=false')
                try:
                    self.assertEqual(pipeline.get_by_name('source').get_property('input-rate'),5998)
                    pipeline.set_state(Gst.State.PLAYING)
                    message = pipeline.get_bus().timed_pop_filtered(5 * Gst.SECOND,
                                              Gst.MessageType.EOS | Gst.MessageType.ERROR)
                    self.assertIsNotNone(message)
                    self.assertEqual(message.type, Gst.MessageType.EOS,
                        message.parse_error() if message.type == Gst.MessageType.ERROR else '')
                finally:
                    pipeline.set_state(Gst.State.NULL)
                worker.join(6)
                status_worker.join(6)
            server.close()
            control.close()
            self.assertFalse(worker.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(acknowledgements[0]['token'], 42)
            self.assertEqual(acknowledgements[0]['generation'], 3)
