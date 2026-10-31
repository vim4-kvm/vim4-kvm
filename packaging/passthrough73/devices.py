"""Linux V4L2/DRM adapters backed by devices.c, with no implicit retirement.

The caller drains all broker reader leases before close, source reconfiguration
or capture STREAMOFF. Scanout requires an already configured CRTC; connector
selection, modesetting and hotplug qualification remain the controller's job.
"""
import ctypes as C
import errno
import os
from pathlib import Path

from .leases import Buffer, Frame


class _Completed(C.Structure):
    _fields_ = [('index', C.c_uint), ('sequence', C.c_uint), ('timestamp_ns', C.c_uint64)]


def _library(path):
    lib = C.CDLL(str(path or Path(__file__).with_name('libpassthrough73.so')))
    pointer = C.c_void_p
    signatures = {
        'pt_capture_open': [C.c_char_p, C.c_uint, C.POINTER(pointer)],
        'pt_capture_stop': [pointer], 'pt_capture_start': [pointer],
        'pt_capture_close': [pointer], 'pt_capture_fd': [pointer],
        'pt_capture_info': [pointer, C.c_uint],
        'pt_capture_export': [pointer, C.c_uint], 'pt_capture_length': [pointer, C.c_uint],
        'pt_capture_queue': [pointer, C.c_uint],
        'pt_capture_read': [pointer, C.POINTER(_Completed)],
        'pt_scanout_create': [C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_uint, C.c_uint,
                              C.POINTER(pointer)],
        'pt_scanout_commit': [pointer, C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_int],
        'pt_scanout_retired': [pointer], 'pt_scanout_destroy': [pointer],
        'pt_reader_fence': [C.c_int], 'pt_plane_disable': [C.c_int, C.c_uint],
        'pt_modeset': [C.c_int, C.c_uint, C.c_uint, C.c_uint, C.c_uint],
    }
    for name, args in signatures.items():
        getattr(lib, name).argtypes = args
        getattr(lib, name).restype = C.c_int
    return lib


def _check(result, operation):
    if result < 0:
        raise OSError(-result, operation + ': ' + os.strerror(-result))
    return result


class CaptureDevice:
    """Exclusive single-plane NV12 streaming queue; EXPBUF once per pool slot."""

    def __init__(self, path, generation=1, count=14, library=None):
        self.lib = _library(library)
        self.pointer = C.c_void_p()
        self.generation = generation
        _check(self.lib.pt_capture_open(os.fsencode(path), count, C.byref(self.pointer)), 'capture open')
        self.count, self.width, self.height, self.pitch, self.size, colorspace, quantization = [
            self.lib.pt_capture_info(self.pointer, i) for i in range(7)]
        self.colorspace = {3: 'rec709', 8: 'srgb', 10: 'bt2020'}.get(colorspace, f'v4l2:{colorspace}')
        self.quantization = {0: 'default', 1: 'full', 2: 'limited'}.get(quantization, f'v4l2:{quantization}')
        self.buffers = [Buffer(i, self.lib.pt_capture_export(self.pointer, i),
                               self.lib.pt_capture_length(self.pointer, i)) for i in range(self.count)]

    def fileno(self):
        return self.lib.pt_capture_fd(self.pointer)

    def start(self):
        _check(self.lib.pt_capture_start(self.pointer), 'STREAMON')

    def read_frame(self):
        value = _Completed()
        result = self.lib.pt_capture_read(self.pointer, C.byref(value))
        if result == -errno.EAGAIN:
            return None
        _check(result, 'DQBUF/complete frame validation')
        return Frame(self.generation, value.index, value.sequence, value.timestamp_ns,
                     self.width, self.height, self.pitch, self.pitch * self.height,
                     self.colorspace, self.quantization)

    def requeue(self, generation, index):
        if generation != self.generation:
            raise ValueError('Cannot QBUF a retired generation into the current queue')
        _check(self.lib.pt_capture_queue(self.pointer, index), 'QBUF')

    def stop(self):
        _check(self.lib.pt_capture_stop(self.pointer), 'STREAMOFF (descriptors retained on failure)')

    def close(self):
        if self.pointer.value:
            _check(self.lib.pt_capture_close(self.pointer), 'capture close (stop must succeed)')
            self.pointer = C.c_void_p()


class Scanout:
    """PRIME framebuffer and its driver READ fence; no page-flip shortcut.

    drm_fd must have atomic client capability enabled and master permission. A
    controller must TEST_ONLY first and configure the CRTC before plane commits.
    Keep both this object and its broker lease after any real-commit failure.
    """

    def __init__(self, drm_fd, dma_fd, frame, library=None):
        self.lib = _library(library)
        self.pointer = C.c_void_p()
        self.frame = frame
        _check(self.lib.pt_scanout_create(drm_fd, dma_fd, frame.width, frame.height,
                                          frame.pitch, frame.uv_offset, C.byref(self.pointer)), 'PRIME/AddFB2')

    def commit(self, plane, crtc, test_only=False):
        _check(self.lib.pt_scanout_commit(self.pointer, plane, crtc, self.frame.width,
                                          self.frame.height, test_only), 'atomic plane commit')

    def retired(self):
        return bool(_check(self.lib.pt_scanout_retired(self.pointer), 'READ fence poll'))

    def close(self):
        if self.pointer.value:
            _check(self.lib.pt_scanout_destroy(self.pointer), 'scanout close (READ retirement required)')
            self.pointer = C.c_void_p()
