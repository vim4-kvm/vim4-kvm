#!/usr/bin/env python3
"""HDMI self-loop colour chart, raw NV12 analysis and exclusive board matrix.

chart/analyze are offline. run needs root, board/heavy locks, stopped capture
consumers, a native dynamic NV12 VDIN node and OUT connected to IN. It uses
display-color.c for atomic KMS and V4L2, never an encoder or USB capture card.
The measurement domain is VDIN's declared BT.709 limited NV12, including RX
conversion for RGB transport. This is not a direct probe of RGB wire samples.
"""
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import statistics
import struct
import subprocess
import time


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def chart(width, height):
    """Four bands: full primaries, all 256 greys, 75% bars and level steps."""
    if width < 1024 or height < 128 or width % 2 or height % 2:
        raise ValueError('chart needs even dimensions, at least 1024x128')
    primaries = [('black', (0, 0, 0)), ('white', (255, 255, 255)),
                 ('red', (255, 0, 0)), ('green', (0, 255, 0)),
                 ('blue', (0, 0, 255)), ('cyan', (0, 255, 255)),
                 ('magenta', (255, 0, 255)), ('yellow', (255, 255, 0))]
    bars = [('smpte75-' + name, tuple(round(c * .75) for c in rgb))
            for name, rgb in [primaries[i] for i in (1, 7, 5, 3, 6, 2, 4)]]
    levels = (0, 1, 2, 4, 8, 15, 16, 17, 32, 64, 128, 192, 234, 235, 236, 253, 254, 255)
    bands = [primaries, [('ramp-%03d' % n, (n, n, n)) for n in range(256)],
             bars, [('level-%03d' % n, (n, n, n)) for n in levels]]
    pixels, blocks = bytearray(), []
    for band, colors in enumerate(bands):
        y0, y1 = band * height // 4, (band + 1) * height // 4
        row = bytearray()
        for i, (name, rgb) in enumerate(colors):
            x0, x1 = i * width // len(colors), (i + 1) * width // len(colors)
            row.extend(bytes(rgb) * (x1 - x0))
            blocks.append(dict(name=name, rgb=list(rgb), rect=[x0, y0, x1, y1]))
        pixels.extend(row * (y1 - y0))
    return bytes(pixels), dict(width=width, height=height, blocks=blocks)


def write_chart(directory, width, height):
    pixels, layout = chart(width, height)
    path = directory / 'chart.ppm'
    path.write_bytes(f'P6\n{width} {height}\n255\n'.encode() + pixels)
    layout['ppm_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    save(directory / 'chart.json', layout)
    return layout


def avi_decode(packet):
    if len(packet) != 17 or packet[:3] != b'\x82\x02\x0d' or sum(packet) % 256:
        raise ValueError('missing, torn or invalid AVI InfoFrame')
    colorspace = {0: 'rgb', 1: '422', 2: '444', 3: '420'}.get(packet[4] >> 5)
    quantization = (packet[6] >> 2) & 3 if colorspace == 'rgb' else packet[8] >> 6
    return dict(hex=packet.hex(), format=colorspace, quantization=quantization,
                colorimetry=packet[5] >> 6, vic=packet[7] & 127)


def reference(rgb, avi):
    """Quantize expected wire samples, then convert to the VDIN sample domain."""
    if avi['format'] == 'rgb':
        if avi['quantization'] not in (1, 2):
            raise ValueError('RGB measurement requires explicit AVI range')
        limited = avi['quantization'] == 1
        wire = [round(16 + c * 219 / 255) if limited else c for c in rgb]
        normalized = [(c - 16) * 255 / 219 if limited else c for c in wire]
    else:
        if avi['format'] not in ('444', '420') or avi['quantization'] != 0:
            raise ValueError('only limited YCbCr444/420 is calibrated')
        normalized = rgb
    r, g, b = normalized
    y = .2126 * r + .7152 * g + .0722 * b
    yuv = [round(16 + y * 219 / 255),
           round(128 + (b - y) / 1.8556 * 224 / 255),
           round(128 + (r - y) / 1.5748 * 224 / 255)]
    if avi['format'] != 'rgb':
        wire = yuv
    return wire, yuv


def y420_vics(edid):
    """Resolve CTA 420 blocks against each extension's local SVD ordering."""
    if len(edid) < 128 or len(edid) != 128 * (edid[126] + 1):
        raise ValueError('incomplete EDID')
    if any(sum(edid[i:i + 128]) % 256 for i in range(0, len(edid), 128)):
        raise ValueError('EDID checksum mismatch')
    result = set()
    for start in range(128, len(edid), 128):
        block = edid[start:start + 128]
        if block[0] != 2:
            continue
        end = block[2] or 4
        if end < 4 or end > 127:
            raise ValueError('invalid CTA data block boundary')
        svds, maps = [], []
        pos = 4
        while pos < end:
            tag, size = block[pos] >> 5, block[pos] & 31
            data = block[pos + 1:pos + 1 + size]
            if pos + 1 + size > end:
                raise ValueError('truncated CTA data block')
            if tag == 2:
                svds.extend(v & 127 for v in data)
            elif tag == 7 and data:
                if data[0] == 14:
                    result.update(data[1:])
                elif data[0] == 15:
                    maps.append(data[1:])
            pos += 1 + size
        for bitmap in maps:
            if not bitmap:
                result.update(svds)
            for i in range(len(bitmap) * 8):
                if bitmap[i // 8] & (1 << (i % 8)):
                    if i >= len(svds):
                        raise ValueError('420 map references a missing SVD')
                    result.add(svds[i])
    return result


def analyze(layout, meta, frames, avi):
    w, h, stride, uv = (meta[k] for k in ('width', 'height', 'stride', 'uv_offset'))
    if (w, h) != (layout['width'], layout['height']) or stride < w or uv < stride * h:
        raise ValueError('capture geometry/stride/UV offset differs from chart')
    if (meta['format'], meta['colorspace'], meta['ycbcr_enc'], meta['quantization']) != (
            'NV12', 3, 2, 2):
        raise ValueError('expected V4L2 REC709/709/limited NV12 contract')
    if len(frames) != 3 or any(len(raw) < uv + stride * h // 2 for raw in frames):
        raise ValueError('three complete raw frames required')
    if avi['colorimetry'] != 2:
        raise ValueError('AVI must declare BT.709')
    rows = []
    for block in layout['blocks']:
        x0, y0, x1, y1 = block['rect']
        # Interior chroma pairs stay in a single patch even for the narrow ramp.
        xs = [x for x in range(x0 + 1, x1 - 1) if x % 2 == 0 and x + 1 < x1 - 1]
        if not xs:
            raise ValueError('patch too narrow for an interior chroma pair')
        x = xs[len(xs) // 2]
        y = ((y0 + y1) // 2) & ~1
        wire, expected = reference(block['rgb'], avi)
        values, errors = [], []
        for raw in frames:
            channels = [[], [], []]
            for yy in range(y - 4, y + 4, 2):
                channels[0].extend(raw[yy * stride + x:yy * stride + x + 2])
                offset = uv + yy // 2 * stride + x
                channels[1].append(raw[offset])
                channels[2].append(raw[offset + 1])
            value = [statistics.median(c) for c in channels]
            values.append(value)
            # Include spatial variation, so one good median cannot hide noise.
            errors.append([max(abs(c - e) for c in samples)
                           for samples, e in zip(channels, expected)])
        maximum = max(c for frame in errors for c in frame)
        rows.append(dict(name=block['name'], source_rgb=block['rgb'],
                         expected_wire=wire, expected_nv12=expected,
                         measured_nv12=values, max_error=maximum, passed=maximum <= 2))
    return dict(domain='8-bit VDIN BT.709 limited Y/Cb/Cr', tolerance=2,
                maximum_error=max(r['max_error'] for r in rows),
                passed=all(r['passed'] for r in rows), blocks=rows,
                raw_sha256=[hashlib.sha256(raw).hexdigest() for raw in frames])


def vendor_tx_snapshot():
    root = Path('/sys/class/amhdmitx/amhdmitx0')
    packet_dump = (root / 'hdmitx_pkt_dump').read_text()
    fields = dict(re.findall(r'^AVI\.([\w_]+): (.+)$', packet_dump, re.M))
    fmt = fields.get('colorspace', '').lower()
    q = fields.get('quantization_range' if fmt == 'rgb' else 'ycc_quantization_range')
    quant = ({'default': 0, 'limited': 1, 'full': 2} if fmt == 'rgb' else
             {'limited': 0, 'full': 1}).get(q)
    if quant is None or fields.get('colorimetry') != 'BT.709':
        raise ValueError('vendor AVI helper has no valid BT.709 packet')
    regs = (0xd20, 0xd21, 0xda0, 0xda1, 0xb18, 0xb44, 0xb45, 0xb46,
            0x236, 0x6e1, 0x900, 0x235)
    started = time.clock_gettime(time.CLOCK_BOOTTIME)
    # Only the vendor's rh single-register read command; no wh register writes.
    for reg in regs:
        (root / 'debug').write_text(f'rh{reg:x}')
    kernel = subprocess.check_output(['dmesg', '--color=never'], text=True)
    kernel = '\n'.join(line for line in kernel.splitlines()
                       if (stamp := re.search(r'\[\s*(\d+\.\d+)\]', line)) and
                       float(stamp[1]) >= started)
    values = {int(reg, 16): int(value, 16) for reg, value in
              re.findall(r'HDMI reg\[([0-9a-f]+)\]=([0-9a-f]+)', kernel, re.I)}
    if any(reg not in values for reg in regs):
        raise ValueError('vendor secure register read missing from kernel log')
    avi = dict(format=fmt, quantization=quant, colorimetry=2,
               vic=int(fields['video_code']))
    return packet_dump, avi, {hex(reg): values[reg] for reg in regs}


def snapshot(vendor=False):
    """Read only documented control/matrix windows; never touch LUT ports."""
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    def read(address, size):
        with mmap.mmap(fd, mmap.PAGESIZE, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ,
                       offset=address & -mmap.PAGESIZE) as page:
            return page[address % mmap.PAGESIZE:address % mmap.PAGESIZE + size]
    try:
        # amlogic-t7.dtsi: RX COR is fe000000 + 3a0000, AVI packet at 1140.
        packet = read(0xfe3a1140, 17)
        if packet != read(0xfe3a1140, 17):
            raise ValueError('RX AVI changed during snapshot')
        regs = [0x271b, 0x2743, 0x1d5f, 0x1a0c, 0x1a0d,
                *range(0x3910, 0x391e), *range(0x39a0, 0x39ae)]
        for base in (0x38a0, 0x5b50):
            regs.extend(range(base, base + 0x1d))
            regs.extend(range(base + 0x28, base + 0x3d))
        vpu = {hex(word): struct.unpack('<I', read(0xff000000 + word * 4, 4))[0]
               for word in regs}
    finally:
        os.close(fd)
    if vendor:
        tx, tx_avi, tx_regs = vendor_tx_snapshot()
    else:
        links = list(Path('/sys/bus/platform/devices').glob('*/link_state'))
        tx_links = [p for p in links if 'hdmi-tx' in p.parent.name]
        if len(tx_links) != 1:
            raise ValueError('exactly one TX link_state required')
        tx = tx_links[0].read_text()
        match = re.search(r'packet0 enable=([0-9a-f]+) data=([0-9a-f ]+)', tx)
        if not match or int(match[1], 16) != 0xe0:
            raise ValueError('TX AVI packet disabled')
        tx_avi = avi_decode(bytes.fromhex(match[2])[:17])
        patterns = {0xd20: r'csc=([0-9a-f]+)/', 0xda0: r'csc=[0-9a-f]+/([0-9a-f]+)',
                    0xd21: r'csc_hi=([0-9a-f]+)/', 0xda1: r'csc_hi=[0-9a-f]+/([0-9a-f]+)',
                    0xb18: r'input_mask=([0-9a-f]+)', 0xb46: r'output_mask=([0-9a-f]+)',
                    0x236: r'p2t=([0-9a-f]+)', 0x6e1: r'gcp=([0-9a-f]+)',
                    0x900: r'scrctl=([0-9a-f]+)', 0x235: r'clkratio=([0-9a-f]+)'}
        tx_regs = {hex(reg): int(re.search(pattern, tx)[1], 16)
                   for reg, pattern in patterns.items()}
        mapping = int(re.search(r'output_map=([0-9a-f]+)', tx)[1], 16)
        tx_regs.update({'0xb44': mapping & 255, '0xb45': mapping >> 8})
    rx_avi = avi_decode(packet)
    if any(tx_avi[k] != rx_avi[k] for k in ('format', 'quantization', 'colorimetry', 'vic')):
        raise ValueError('TX/RX AVI mismatch')
    edids = {str(p): p.read_bytes().hex() for p in Path('/sys/class/drm').glob('*HDMI-A-*/edid')}
    return dict(tx_link=tx, tx_registers=tx_regs, rx_avi=rx_avi, tx_avi=tx_avi, vpu=vpu,
                edids=edids, cmdline=Path('/proc/cmdline').read_text().strip(),
                release=os.uname().release,
                taint=Path('/proc/sys/kernel/tainted').read_text().strip(),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def run_matrix(args):
    args.output.mkdir(parents=True, exist_ok=False)
    edids = [p.read_bytes() for p in Path('/sys/class/drm').glob('*HDMI-A-*/edid')]
    edids = [data for data in edids if data]
    if len(edids) != 1:
        raise ValueError('exactly one connected HDMI sink EDID required')
    (args.output / 'sink.edid').write_bytes(edids[0])
    supported420 = y420_vics(edids[0])
    rows = []
    for width, height, hz in ((1920, 1080, 60), (3840, 2160, 30), (3840, 2160, 60)):
        variants = (('rgb', 'native'), ('444', 'native'), ('420', 'native')) if args.vendor else (
            ('rgb', 'full'), ('rgb', 'limited'), ('444', 'limited'), ('420', 'limited'))
        for fmt, quant in variants:
            label = f'{width}x{height}-{hz}-{fmt}-{quant}'
            vic = {(1920, 1080, 60): 16, (3840, 2160, 30): 95, (3840, 2160, 60): 97}[
                width, height, hz]
            if fmt == '420' and vic not in supported420:
                row = dict(label=label, status='not-applicable', reason='EDID has no 420 for this VIC')
                rows.append(row)
                save(args.output / 'matrix.json', rows)
                print(json.dumps(row), flush=True)
                continue
            directory = args.output / label
            directory.mkdir()
            layout = write_chart(directory, width, height)
            command = [str(args.binary), 'tx-vendor' if args.vendor else 'tx', args.card,
                       str(width), str(height), str(hz),
                       fmt, quant, str(directory / 'chart.ppm'), str(directory / 'ready.json')]
            row = dict(label=label, format=fmt, range=quant, status='error')
            with (directory / 'tx.log').open('w') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 20
                    while not (directory / 'ready.json').exists():
                        if process.poll() is not None:
                            raise RuntimeError('TX rejected: ' + (directory / 'tx.log').read_text())
                        if time.monotonic() > deadline:
                            raise TimeoutError('KMS did not become ready')
                        time.sleep(.1)
                    # RX link qualification is asynchronous; require matching AVI
                    # before allocating capture buffers. Stale packets alone fail
                    # later native geometry, frame sequence and pixel checks.
                    while True:
                        try:
                            before = snapshot(args.vendor)
                            avi = before['rx_avi']
                            expected_q = (2 if quant == 'full' else 1) if fmt == 'rgb' else 0
                            if avi['format'] != fmt or (not args.vendor and
                                                       avi['quantization'] != expected_q):
                                raise ValueError('AVI differs from requested format/range')
                            if not args.vendor and before['taint'] != '0':
                                raise RuntimeError('kernel tainted')
                            break
                        except ValueError:
                            if time.monotonic() > deadline:
                                raise
                            time.sleep(.2)
                    save(directory / 'before.json', before)
                    if args.vendor:
                        row.update(status='register-snapshot', actual_avi=avi)
                    else:
                        subprocess.run([str(args.binary), 'capture', args.video, str(width), str(height),
                                        str(hz), str(directory / 'capture')], check=True, timeout=45)
                        after = snapshot()
                        save(directory / 'after.json', after)
                        if before['rx_avi'] != after['rx_avi'] or after['taint'] != '0':
                            raise RuntimeError('link changed or kernel tainted during capture')
                        meta = json.loads((directory / 'capture.json').read_text())
                        frames = [(directory / f'capture-{i}.raw').read_bytes() for i in range(3)]
                        report = analyze(layout, meta, frames, avi)
                        save(directory / 'analysis.json', report)
                        row.update(status='pass' if report['passed'] else 'fail',
                                   maximum_error=report['maximum_error'])
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                    row['error'] = str(error)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                            row.update(status='error', error='TX did not retire framebuffer')
                    row['tx_exit'] = process.returncode
                    if process.returncode and row['status'] in ('pass', 'register-snapshot'):
                        row.update(status='error', error='TX cleanup failed')
            rows.append(row)
            save(args.output / 'matrix.json', rows)
            print(json.dumps(row), flush=True)
            if (directory / 'ready.json').exists() and row['tx_exit'] != 0:
                raise RuntimeError('TX failed to retire; stop matrix and restore baseline')
            if not args.vendor and Path('/proc/sys/kernel/tainted').read_text().strip() != '0':
                raise RuntimeError('stop matrix after kernel fault; restore baseline')
    return int(any(r['status'] not in ('pass', 'register-snapshot', 'not-applicable') for r in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    create = sub.add_parser('chart')
    create.add_argument('--width', type=int, default=1920)
    create.add_argument('--height', type=int, default=1080)
    create.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('analyze')
    check.add_argument('directory', type=Path)
    run = sub.add_parser('run')
    run.add_argument('--exclusive', action='store_true', required=True)
    run.add_argument('--vendor', action='store_true', help='5.15 register reference; native AVI range')
    run.add_argument('--binary', type=Path, required=True)
    run.add_argument('--card', required=True)
    run.add_argument('--video', default='/dev/video0')
    run.add_argument('--output', type=Path, required=True)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--vendor', action='store_true')
    snap.add_argument('--output', type=Path, required=True)
    diff = sub.add_parser('diff')
    diff.add_argument('vendor', type=Path)
    diff.add_argument('candidate', type=Path)
    diff.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'chart':
        args.output.mkdir(parents=True, exist_ok=False)
        write_chart(args.output, args.width, args.height)
        return 0
    if args.action == 'run':
        return run_matrix(args)
    if args.action == 'snapshot':
        save(args.output, snapshot(args.vendor))
        return 0
    if args.action == 'diff':
        a, b = (json.loads(p.read_text()) for p in (args.vendor, args.candidate))
        if sorted(a['edids'].values()) != sorted(b['edids'].values()):
            raise ValueError('register comparison requires the same sink EDID')
        result = {group: [{'register': reg, 'vendor': a[group].get(reg),
                           'candidate': b[group].get(reg),
                           'equal': a[group].get(reg) == b[group].get(reg)}
                          for reg in sorted(a[group].keys() | b[group].keys())]
                  for group in ('vpu', 'tx_registers', 'tx_avi')}
        save(args.output, result)
        return 0
    directory = args.directory
    layout = json.loads((directory / 'chart.json').read_text())
    meta = json.loads((directory / 'capture.json').read_text())
    avi = json.loads((directory / 'before.json').read_text())['rx_avi']
    result = analyze(layout, meta, [(directory / f'capture-{i}.raw').read_bytes()
                                  for i in range(3)], avi)
    save(directory / 'analysis.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'blocks'}))
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
