"""Fixed VIM4 mainline V4L2 metadata and EDID operations; no capture ownership."""
import ctypes
import errno
import fcntl
from pathlib import Path
import struct

VIDEO_CLASS = Path('/sys/class/video4linux')
RX_STATUS = Path('/sys/kernel/debug/fe398000.hdmi-receiver/status')


def capture_device():
    nodes = [Path('/dev') / entry.name for entry in VIDEO_CLASS.glob('video*')
             if (entry / 'name').read_text().strip() == 't7-vdin-test']
    if len(nodes) != 1:
        raise ValueError('Expected exactly one VIM4 mainline capture device')
    return nodes[0]


def ioctl(fd, number, data, *, read_only=False):
    # Linux ARM64 _IOWR('V', number, type); sizes come from the packed UAPI.
    direction = 0x80000000 if read_only else 0xc0000000
    return fcntl.ioctl(fd, direction | len(data) << 16 | ord('V') << 8 | number, data, True)


def decode_timings(data):
    kind, width, height, interlaced, _, clock, hf, hs, hb, vf, vs, vb = struct.unpack_from('=IIIIIQIIIIII', data)
    if kind != 0 or interlaced or not width or not height or not clock:
        raise ValueError('Unsupported HDMI input timing')
    total = (width + hf + hs + hb) * (height + vf + vs + vb)
    rate = clock / total
    if not 1 <= rate <= 120:
        raise ValueError('Invalid HDMI input clock')
    return {'signal': True, 'width': width, 'height': height, 'refreshHz': rate, 'audio': False}


def status():
    with capture_device().open('r+b', buffering=0) as device:
        timings = bytearray(132)
        try:
            ioctl(device.fileno(), 99, timings, read_only=True)  # VIDIOC_QUERY_DV_TIMINGS
        except OSError as error:
            if error.errno in (errno.ENOLINK, errno.ENODATA, errno.ERANGE):
                return {'signal': False, 'audio': False}
            raise
        result = decode_timings(timings)
        # v4l2_format's union is aligned to eight bytes on the supported ARM64.
        current = bytearray(208)
        struct.pack_into('=I', current, 0, 1)  # V4L2_BUF_TYPE_VIDEO_CAPTURE
        ioctl(device.fileno(), 4, current)  # VIDIOC_G_FMT
        result['captureWidth'], result['captureHeight'] = struct.unpack_from('=II', current, 8)
    fields = dict(line.split(':', 1) for line in RX_STATUS.read_text().splitlines() if ':' in line)
    fields = {key: value.strip() for key, value in fields.items()}
    avi = bytes.fromhex(fields.get('avi_packet', ''))
    if len(avi) >= 5:
        result['colorSpace'] = {0: 'RGB', 1: 'YUV422', 2: 'YUV444', 3: 'YUV420'}.get(avi[4] >> 5, '')
    result['depth'] = {0: 8, 4: 8, 5: 10, 6: 12}.get(int(fields.get('color_depth_code', '0'), 0), 0)
    result['audio'] = fields.get('audio_active') == '1'
    result['hdr'] = 'HDR10' if fields.get('hdr_input') == '1' else 'SDR'
    return result


def validate_edid(data):
    if len(data) not in (128, 256, 384, 512) or data[:8] != b'\x00\xff\xff\xff\xff\xff\xff\x00':
        raise ValueError('Invalid HDMI EDID length/header')
    if data[126] != len(data) // 128 - 1 or any(sum(data[i:i + 128]) & 255 for i in range(0, len(data), 128)):
        raise ValueError('Invalid HDMI EDID extension/checksum')


def set_edid(data):
    validate_edid(data)
    storage = ctypes.create_string_buffer(data)
    request = bytearray(struct.pack('=III5IQ', 0, 0, len(data) // 128, 0, 0, 0, 0, 0, ctypes.addressof(storage)))
    with capture_device().open('r+b', buffering=0) as device:
        ioctl(device.fileno(), 41, request)  # VIDIOC_S_EDID


def disable_edid():
    with capture_device().open('r+b', buffering=0) as device:
        ioctl(device.fileno(), 41, bytearray(40))
