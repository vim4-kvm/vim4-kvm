"""Execute the production queue boundary with controlled ioctl completion."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeviceTests(unittest.TestCase):
    def test_error_completion_and_failed_stop_do_not_recycle_dma(self):
        if not shutil.which('pkg-config') or subprocess.run(
                ['pkg-config', '--exists', 'libdrm'], capture_output=True).returncode:
            self.skipTest('Linux libdrm development files required')
        fixture = r'''
#include <stdarg.h>
#define ioctl fixture_ioctl
#include "devices.c"
#undef ioctl
#include <assert.h>
static unsigned mode, queues;
int fixture_ioctl(int fd, unsigned long request, ...) {
    (void)fd;
    va_list args; va_start(args,request); void *arg=va_arg(args,void *); va_end(args);
    if(request==VIDIOC_DQBUF) {
        struct v4l2_buffer *b=arg;
        b->index=0; b->sequence=42; b->bytesused=64*32*3/2;
        b->timestamp.tv_sec=1; b->timestamp.tv_usec=123;
        b->flags=V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC | (mode==1 ? V4L2_BUF_FLAG_ERROR : 0);
        if(mode==2) b->index=7;
        return 0;
    }
    if(request==VIDIOC_QBUF) {queues++;return 0;}
    if(request==VIDIOC_STREAMOFF) {errno=EIO;return -1;}
    assert(0);return -1;
}
int main(void) {
    struct capture c={.fd=99,.running=1,.count=4,.pitch=64,.height=32};
    struct completed_frame f;
    c.queued[0]=1;
    assert(!pt_capture_read(&c,&f) && f.sequence==42 && f.timestamp_ns==1000123000ULL);
    assert(!c.queued[0] && !queues);
    assert(!pt_capture_queue(&c,0) && queues==1);
    assert(pt_capture_queue(&c,0)==-EINVAL && queues==1);
    mode=1;
    assert(pt_capture_read(&c,&f)==-EIO && !c.queued[0] && queues==1);
    mode=2;c.queued[0]=1;
    assert(pt_capture_read(&c,&f)==-EPROTO && c.queued[0]);
    assert(pt_capture_stop(&c)==-EIO && c.running && c.queued[0]);
    return 0;
}
'''
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'libdrm'], text=True).split()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'fixture.c').write_text(fixture)
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-I',
                            str(ROOT / 'packaging/passthrough73'), str(path / 'fixture.c'),
                            '-o', str(path / 'fixture'), *flags], check=True)
            subprocess.run([str(path / 'fixture')], check=True)
