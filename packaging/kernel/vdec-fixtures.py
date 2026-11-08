#!/usr/bin/env python3
"""Generate codec fixtures and compare captured I420 offline.

Requires FFmpeg with libx264 and ffprobe. Neither operation accesses a board.
generate-hevc-hang also uses libx265 and FFmpeg trace_headers. It patches only
SPS LT syntax and seals experiments for the existing vdec-window Fluster entry.
References are decoded from the actual compressed files, so encoder versions
may change fixture bytes without weakening the pixel comparison.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request


CASES = (
    ("baseline", 640, 368, 32, "baseline", "Constrained Baseline",
     "cabac=0:bframes=0:ref=2:8x8dct=0"),
    ("main", 640, 368, 64, "main", "Main",
     "cabac=1:bframes=2:ref=3:8x8dct=0:weightp=2"),
    ("high", 640, 368, 64, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1:weightp=2"),
    ("1080p", 1920, 1080, 16, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1"),
    ("uhd", 3840, 2160, 16, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1"),
    ("4k-limit", 4096, 2304, 8, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1"),
    ("high-jvt", 640, 368, 16, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1:cqm=jvt"),
)

MPEG2_CASES = (
    ("mpeg2-intra", 640, 368, 16, "main", "Main", ["-g", "1", "-bf", "0"]),
    ("mpeg2-ipb", 640, 368, 32, "main", "Main", ["-g", "12", "-bf", "2"]),
    ("mpeg2-matrix", 640, 368, 16, "main", "Main",
     ["-g", "12", "-bf", "2", "-intra_matrix",
      ",".join(str(8 + i % 17) for i in range(64)), "-inter_matrix",
      ",".join(str(16 + i % 13) for i in range(64))]),
    ("mpeg2-interlaced", 640, 368, 16, "main", "Main",
     ["-g", "12", "-bf", "2", "-flags", "+ildct+ilme", "-top", "1"]),
    ("mpeg2-1080p", 1920, 1080, 16, "main", "Main", ["-g", "12", "-bf", "2"]),
)

MJPEG_CASES = (
    ("mjpeg-420", 640, 368, 16, "baseline", "Baseline", []),
    ("mjpeg-no-app", 640, 368, 16, "baseline", "Baseline", []),
    ("mjpeg-1080p", 1920, 1080, 16, "baseline", "Baseline", []),
)

FIELD_SOURCE = 'https://samples.ffmpeg.org/MPEG2/mpeg2_field_encoding.ts'
FIELD_SOURCE_SHA256 = '9688333a145b9e2c2139b9cab6cd4966acd19788fd620b4b31db5c2891547cb8'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def frame_hashes(raw, frame_size):
    return [sha256(raw[i:i + frame_size])
            for i in range(0, len(raw), frame_size)]


def jpeg_without_leading_metadata(data):
    """Remove APP/COM immediately after each SOI in an FFmpeg MJPEG stream."""
    result = bytearray()
    start = 0
    while start < len(data):
        if data[start:start + 2] != b'\xff\xd8':
            raise ValueError('expected JPEG SOI')
        end = data.find(b'\xff\xd8', start + 2)
        if end < 0:
            end = len(data)
        offset = start + 2
        while offset + 4 <= end and data[offset] == 0xff:
            marker = data[offset + 1]
            if marker != 0xfe and not 0xe0 <= marker <= 0xef:
                break
            length = int.from_bytes(data[offset + 2:offset + 4], 'big')
            if length < 2 or offset + length + 2 > end:
                raise ValueError('truncated JPEG metadata')
            offset += length + 2
        result.extend(b'\xff\xd8' + data[offset:end])
        start = end
    return bytes(result)


def generate_fields(output):
    """Extract a complete field-pair interval from the pinned public sample."""
    output.mkdir(parents=True, exist_ok=False)
    with urllib.request.urlopen(FIELD_SOURCE, timeout=60) as response:
        transport = response.read()
    if sha256(transport) != FIELD_SOURCE_SHA256:
        raise ValueError('MPEG-2 field sample checksum mismatch')
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        (temp / 'source.ts').write_bytes(transport)
        demux = subprocess.run([
            'ffmpeg', '-v', 'error', '-i', str(temp / 'source.ts'),
            '-map', '0:v:0', '-c', 'copy', '-f', 'mpeg2video', str(temp / 'source.m2v'),
        ], check=True, capture_output=True)
        (output / 'demux.log').write_bytes(demux.stderr)
        data = (temp / 'source.m2v').read_bytes()
    # The transport sample begins and ends mid-picture. Keep 16 complete pairs
    # starting at the first sequence header; neither damaged edge is a fixture.
    data = data[data.index(b'\0\0\1\xb3'):]
    pictures = list(re.finditer(b'\x00\x00\x01\x00', data))
    data = data[:pictures[32].start()] + b'\0\0\1\xb7'
    chunks = data.split(b'\0\0\1')[1:]
    structures = [c[3] & 3 for c in chunks if c[0] == 0xb5 and c[1] >> 4 == 8]
    types = [(c[2] >> 3) & 7 for c in chunks if c[0] == 0]
    if structures != [2, 1] * 16 or types[0] != 1 or len(types) != 32:
        raise ValueError('expected 16 bottom/top field pairs starting with an I field')
    clip = output / 'mpeg2-fields.m2v'
    clip.write_bytes(data)
    stream = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(clip),
    ]))['streams'][0]
    if (stream['width'], stream['height'], stream['profile'], stream['field_order'],
            int(stream['nb_read_frames'])) != (720, 576, 'Simple', 'bb', 16):
        raise ValueError('unexpected field fixture properties')
    reference = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-xerror', '-i', str(clip), '-threads', '1',
        '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1',
    ])
    frame_size = 720 * 576 * 3 // 2
    if len(reference) != frame_size * 16:
        raise ValueError('field-pair reference count mismatch')
    case = dict(name='mpeg2-fields', codec='mpeg2', filename=clip.name,
                width=720, height=576, frames=16, frame_size=frame_size,
                profile='simple', field_order='bb', picture_structures=structures,
                compressed_sha256=sha256(data), decoded_sha256=sha256(reference),
                frame_sha256=frame_hashes(reference, frame_size))
    manifest = dict(codec='mpeg2', source_url=FIELD_SOURCE, source_sha256=FIELD_SOURCE_SHA256,
                    ffmpeg=subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
                    cases=[case])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return 0


def generate(output, codec="h264"):
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "codec": codec,
        "ffmpeg": subprocess.check_output(
            ["ffmpeg", "-version"], text=True).splitlines()[0],
        "cases": [],
    }
    cases = {"h264": CASES, "mpeg2": MPEG2_CASES, "mjpeg": MJPEG_CASES}[codec]
    extension = {"h264": ".h264", "mpeg2": ".m2v", "mjpeg": ".mjpg"}[codec]
    encoded_format = "yuvj420p" if codec == "mjpeg" else "yuv420p"
    # The JPEG firmware produces limited-range I420; compare in that range.
    reference_format = "yuv420p"
    for name, width, height, count, profile, actual_profile, params in cases:
        clip = output / (name + extension)
        # QP22 exercises negative PPS QP/chroma offsets. QP26 would hide
        # firmware parameter-table signed-code regressions.
        encoder = (["-c:v", "libx264", "-preset", "medium", "-qp", "22",
                    "-profile:v", profile, "-x264-params",
                    params + ":keyint=16:min-keyint=16:scenecut=0:slices=1", "-f", "h264"]
                   if codec == "h264" else
                   ["-c:v", "mpeg2video", "-q:v", "4", *params, "-f", "mpeg2video"])
        if codec == "mjpeg":
            encoder = ["-c:v", "mjpeg", "-q:v", "4", "-pix_fmt", "yuvj420p", "-f", "mjpeg"]
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", f"testsrc2=size={width}x{height}:rate=30",
            "-frames:v", str(count), "-an", "-threads", "1", *encoder, str(clip),
        ], check=True)
        if name == 'mjpeg-no-app':
            clip.write_bytes(jpeg_without_leading_metadata(clip.read_bytes()))
        streams = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-show_streams",
            "-of", "json", str(clip),
        ]))["streams"]
        if len(streams) != 1:
            raise ValueError(f"{name}: expected one video stream")
        stream = streams[0]
        actual = (stream["profile"], stream["width"], stream["height"],
                  stream["pix_fmt"], int(stream["nb_read_frames"]))
        if actual != (actual_profile, width, height, encoded_format, count):
            raise ValueError(f"{name}: unexpected encoded properties {actual}")
        expected_field_order = "tt" if name == "mpeg2-interlaced" else "progressive"
        if codec != "mjpeg" and stream.get("field_order") != expected_field_order:
            raise ValueError(f"{name}: unexpected field order {stream.get('field_order')}")
        raw = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(clip), "-threads", "1",
            "-pix_fmt", reference_format, "-f", "rawvideo", "pipe:1",
        ])
        frame_size = width * height * 3 // 2
        if len(raw) != frame_size * count:
            raise ValueError(f"{name}: software reference frame count mismatch")
        manifest["cases"].append(dict(
            name=name, width=width, height=height, frames=count,
            codec=codec, filename=clip.name, field_order=stream.get("field_order"),
            reference_format=reference_format,
            frame_size=frame_size, profile=profile,
            compressed_sha256=sha256(clip.read_bytes()),
            decoded_sha256=sha256(raw), frame_sha256=frame_hashes(raw, frame_size),
        ))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return 0


def pixel_errors(reference, captured, width, height):
    frame_size = width * height * 3 // 2
    if len(reference) != len(captured) or len(reference) % frame_size:
        raise ValueError("pixel measurement requires equal complete I420 frames")
    y_size = width * height
    planes = (("Y", 0, y_size), ("U", y_size, y_size * 5 // 4),
              ("V", y_size * 5 // 4, frame_size))
    frames = []
    for offset in range(0, len(reference), frame_size):
        result = {}
        for plane, start, end in planes:
            errors = Counter(a - b for a, b in zip(
                reference[offset + start:offset + end], captured[offset + start:offset + end]))
            count = end - start
            mse = sum(error * error * n for error, n in errors.items()) / count
            result[plane] = dict(
                max_absolute_error=max(abs(error) for error in errors),
                mean_error=sum(error * n for error, n in errors.items()) / count,
                exact_fraction=errors[0] / count,
                psnr_db=10 * math.log10(255 * 255 / mse) if mse else None,
            )
        frames.append(result)
    return frames


def hevc_hang_nals(data):
    """Return Annex B ranges, retaining each original start code."""
    starts = list(re.finditer(b'\x00\x00\x00?\x01', data))
    if not starts or starts[0].start() != 0:
        raise ValueError('expected Annex B HEVC input')
    result = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(data)
        payload = data[start.end():end]
        if len(payload) < 3 or payload[0] & 0x80 or not payload[1] & 7:
            raise ValueError('truncated or invalid HEVC NAL header')
        result.append((start.start(), start.end(), end, payload[0] >> 1 & 63))
    return result


def hevc_hang_rbsp(nal):
    result = bytearray(nal[:2])
    zeros = 0
    for value in nal[2:]:
        if zeros == 2 and value == 3:
            zeros = 0
            continue
        result.append(value)
        zeros = zeros + 1 if value == 0 else 0
    return bytes(result)


def hevc_hang_escape(rbsp):
    result = bytearray(rbsp[:2])
    zeros = 0
    for value in rbsp[2:]:
        if zeros == 2 and value <= 3:
            result.append(3)
            zeros = 0
        result.append(value)
        zeros = zeros + 1 if value == 0 else 0
    return bytes(result)


def hevc_hang_trace_sections(trace):
    """Use FFmpeg's syntax offsets instead of duplicating its SPS parser."""
    sections = []
    current = None
    for line in trace.splitlines():
        match = re.search(r'\[trace_headers @ [^]]+\]\s+(.*)', line)
        if not match:
            continue
        payload = match[1]
        if payload in ('Sequence Parameter Set', 'Picture Parameter Set',
                       'Video Parameter Set', 'Slice Segment Header',
                       'Access Unit Delimiter', 'Supplemental Enhancement Information'):
            current = {'kind': payload, 'fields': []}
            sections.append(current)
        else:
            field = re.fullmatch(r'(\d+)\s+(\S+)\s+([01]+)\s+=\s+(-?\d+)', payload)
            if field and current is not None:
                current['fields'].append((int(field[1]), field[2], field[3], int(field[4])))
    return sections


def hevc_hang_fields(section):
    return {name: value for _, name, _, value in section['fields']}


def hevc_hang_patch_sps(nal, sections, count):
    """Replace only the LT syntax; all slice bytes remain untouched."""
    if count not in (0, 1, 8):
        raise ValueError('expected LT count 0, 1 or 8')
    raw = hevc_hang_rbsp(nal)
    bits = ''.join(f'{value:08b}' for value in raw)
    for section in sections:
        fields = section['fields']
        if section['kind'] != 'Sequence Parameter Set' or not fields:
            continue
        # Match the complete traced SPS, including header and trailing bits.
        # A different SPS id or a repeated header cannot select the wrong offsets.
        position = 0
        for offset, _, encoded, _ in fields:
            if offset != position or bits[offset:offset + len(encoded)] != encoded:
                break
            position += len(encoded)
        else:
            if position == len(bits):
                break
    else:
        raise ValueError('SPS bytes do not match a complete FFmpeg trace')
    by_name = {name: (offset, encoded, value) for offset, name, encoded, value in fields}
    begin = by_name['long_term_ref_pics_present_flag'][0]
    end = by_name['sps_temporal_mvp_enabled_flag'][0]
    stop = by_name['rbsp_stop_one_bit'][0]
    poc_bits = by_name['log2_max_pic_order_cnt_lsb_minus4'][2] + 4
    code = f'{count + 1:b}'
    replacement = '1' + '0' * (len(code) - 1) + code
    replacement += ''.join(f'{i:0{poc_bits}b}0' for i in range(count))
    patched = bits[:begin] + replacement + bits[end:stop] + '1'
    patched += '0' * (-len(patched) % 8)
    return hevc_hang_escape(bytes(int(patched[i:i + 8], 2)
                                  for i in range(0, len(patched), 8)))


def hevc_hang_lt_variant(data, sections, count):
    result = bytearray()
    for start, payload, end, kind in hevc_hang_nals(data):
        result.extend(data[start:payload])
        nal = data[payload:end]
        result.extend(hevc_hang_patch_sps(nal, sections, count) if kind == 33 else nal)
    return bytes(result)


def hevc_hang_first_au(data):
    have_picture = False
    for start, payload, _, kind in hevc_hang_nals(data):
        if have_picture and (kind in (32, 33, 34, 35, 39) or
                             kind < 32 and data[payload + 2] & 0x80):
            return data[:start]
        if kind < 32:
            if not have_picture and kind not in (19, 20):
                raise ValueError('LTRPSPS first picture must be IDR')
            have_picture = True
    if not have_picture:
        raise ValueError('input has no picture')
    return data


def hevc_hang_inspect(clip):
    trace = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'trace', '-i', str(clip),
                            '-map', '0:v:0', '-c:v', 'copy', '-bsf:v', 'trace_headers',
                            '-f', 'null', '-'], check=True, capture_output=True, text=True).stderr
    clip.with_suffix('.headers.log').write_text(trace)
    return hevc_hang_trace_sections(trace)


def hevc_hang_reference(clip, expected_frames=None):
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_frames', '-of', 'json', str(clip)]))
    stream, = probe['streams']
    frames = [frame for frame in probe['frames'] if frame['media_type'] == 'video']
    width, height = stream['width'], stream['height']
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-xerror', '-i', str(clip),
                                   '-threads', '1', '-pix_fmt', 'yuv420p',
                                   '-f', 'rawvideo', '-'])
    frame_size = width * height * 3 // 2
    if (not frames or len(raw) != frame_size * len(frames) or
            expected_frames is not None and len(frames) != expected_frames):
        raise ValueError('software reference frame count mismatch: ' + clip.name)
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(clip), '-threads', '1',
                    '-pix_fmt', 'yuv420p', '-f', 'framemd5', str(clip.with_suffix('.framemd5'))],
                   check=True)
    checksum = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-xerror', '-i', str(clip), '-threads', '1',
        '-pix_fmt', 'yuv420p', '-f', 'md5', '-'], text=True).strip().removeprefix('MD5=')
    if checksum != hashlib.md5(raw).hexdigest():
        raise ValueError('FFmpeg MD5 differs from the visible I420 reference')
    return dict(name=clip.stem, codec='hevc', filename=clip.name, width=width, height=height,
                frames=len(frames), picture_types=[f['pict_type'] for f in frames],
                reference_format='yuv420p', frame_size=frame_size,
                compressed_sha256=sha256(clip.read_bytes()), decoded_sha256=sha256(raw),
                frame_sha256=frame_hashes(raw, frame_size),
                md5=checksum,
                frame_md5=[hashlib.md5(raw[i:i + frame_size]).hexdigest()
                           for i in range(0, len(raw), frame_size)])


def hevc_hang_checked_input(path, expected):
    data = path.read_bytes()
    if sha256(data) != expected:
        raise ValueError('source SHA256 mismatch: ' + str(path))
    return data


def hevc_hang_ctu_size(sps):
    return 1 << (sps['log2_min_luma_coding_block_size_minus3'] + 3 +
                 sps['log2_diff_max_min_luma_coding_block_size'])


def hevc_hang_wpp_off(output):
    clip = output / 'hevc-ctu64-wpp0.h265'
    command = ['ffmpeg', '-hide_banner', '-f', 'lavfi', '-i', 'testsrc2=size=64x240:rate=25',
               '-frames:v', '12', '-pix_fmt', 'yuv420p', '-c:v', 'libx265', '-preset', 'medium',
               '-crf', '24', '-x265-params',
               'ctu=64:wpp=0:pools=1:frame-threads=1:keyint=12:min-keyint=12:'
               'scenecut=0:bframes=2:b-adapt=0:open-gop=0:ref=2', '-f', 'hevc', str(clip)]
    encoded = subprocess.run(command, check=True, capture_output=True)
    clip.with_suffix('.encode.log').write_bytes(encoded.stderr)
    sections = hevc_hang_inspect(clip)
    case = hevc_hang_reference(clip, 12)
    sps = [hevc_hang_fields(s) for s in sections if s['kind'] == 'Sequence Parameter Set']
    pps = [hevc_hang_fields(s) for s in sections if s['kind'] == 'Picture Parameter Set']
    if (case['width'], case['height']) != (64, 240) or not {'P', 'B'} <= set(case['picture_types']):
        raise ValueError('WPP fixture geometry or inter picture types differ')
    if not sps or not pps or any(hevc_hang_ctu_size(s) != 64 for s in sps):
        raise ValueError('x265 changed the requested CTU size')
    if any(p['entropy_coding_sync_enabled_flag'] != 0 for p in pps):
        raise ValueError('one-column inter experiment must have WPP disabled')
    case.update(sps=sps, pps=pps, requested_wpp=0)
    return command, case


def generate_hevc_hang(args):
    """Prepare LT experiments and one-column inter without WPP.

    libx265 disables WPP for both requested narrow geometries. Use the passed
    two-column WPP_E conformance input as the control, without altering x265.
    """
    intra = hevc_hang_checked_input(args.intra, args.intra_sha256)
    ltr = hevc_hang_checked_input(args.ltr, args.ltr_sha256)
    wpp_control = hevc_hang_checked_input(args.wpp_control, args.wpp_control_sha256)
    if any(kind < 32 and kind not in (19, 20) for *_, kind in hevc_hang_nals(intra)):
        raise ValueError('LT mother fixture must contain only IDR pictures')
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(codec='hevc', purpose='hevc-hang',
                    generator_sha256=sha256(Path(__file__).read_bytes()),
                    ffmpeg=subprocess.check_output(['ffmpeg', '-version'], text=True),
                    inputs={str(args.intra): args.intra_sha256, str(args.ltr): args.ltr_sha256,
                            str(args.wpp_control): args.wpp_control_sha256},
                    cases=[], commands=[])

    def save_case(name, data, expected=None):
        clip = output / (name + '.h265')
        clip.write_bytes(data)
        sections = hevc_hang_inspect(clip)
        case = hevc_hang_reference(clip, expected)
        case['sps'] = [hevc_hang_fields(s) for s in sections if s['kind'] == 'Sequence Parameter Set']
        case['pps'] = [hevc_hang_fields(s) for s in sections if s['kind'] == 'Picture Parameter Set']
        manifest['cases'].append(case)
        return sections, case

    intra_sections, mother = save_case('hevc-intra', intra)
    if set(mother['picture_types']) != {'I'}:
        raise ValueError('LT mother fixture is not all I')
    for count in (0, 1, 8):
        _, case = save_case('hevc-lt' + str(count),
                            hevc_hang_lt_variant(intra, intra_sections, count), mother['frames'])
        if (case['frame_md5'] != mother['frame_md5'] or
                any(s['long_term_ref_pics_present_flag'] != 1 or
                    s['num_long_term_ref_pics_sps'] != count for s in case['sps'])):
            raise ValueError('LT variant changed pixels or has incorrect LT syntax')
    first = hevc_hang_first_au(ltr)
    ltr_sections, original = save_case('ltrpsps-first', first, 1)
    _, cleared = save_case('ltrpsps-first-lt0', hevc_hang_lt_variant(first, ltr_sections, 0), 1)
    if cleared['frame_md5'] != original['frame_md5']:
        raise ValueError('clearing the SPS LT list changed the IDR pixels')
    _, control = save_case('wpp-e', wpp_control)
    if (not control['sps'] or not control['pps'] or
            any((s['pic_width_in_luma_samples'] + hevc_hang_ctu_size(s) - 1) //
                hevc_hang_ctu_size(s) != 2 for s in control['sps']) or
            any(p['entropy_coding_sync_enabled_flag'] != 1 for p in control['pps'])):
        raise ValueError('WPP control must have two CTU columns and WPP enabled')
    command, case = hevc_hang_wpp_off(output)
    manifest['commands'].append(command)
    manifest['cases'].append(case)
    manifest['files'] = {p.name: sha256(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    hevc_hang_bundle(output, args.fluster_bundle, args.fluster_bundle_sha256)
    return 0


def hevc_hang_bundle(fixtures, source, expected):
    """Seal a private generated suite using the existing locked Fluster files."""
    original = hevc_hang_checked_input(source / 'bundle-manifest.json', expected)
    sealed = json.loads(original)
    manifest = json.loads((fixtures / 'manifest.json').read_text())
    bundle = fixtures / 'bundle'
    bundle.mkdir()
    files = {}
    for name, digest in sealed['files'].items():
        if not name.startswith('fluster/'):
            continue
        data = hevc_hang_checked_input(source / name, digest)
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[name] = digest
    order = ('hevc-intra', 'hevc-lt0', 'ltrpsps-first-lt0', 'wpp-e',
             'hevc-lt1', 'hevc-lt8', 'hevc-ctu64-wpp0')
    cases = {case['name']: case for case in manifest['cases']}
    suite = dict(name='HEVC-HANG', codec='H.265', description='Private LT/WPP diagnosis',
                 test_vectors=[])
    vectors = []
    for name in order:
        case = cases[name]
        relative = f'resources/HEVC-HANG/{name}/{case["filename"]}'
        data = hevc_hang_checked_input(fixtures / case['filename'], case['compressed_sha256'])
        target = bundle / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        files[relative] = case['compressed_sha256']
        vector = dict(name=name, source='offline-generated:' + name,
                      source_checksum=hashlib.md5(data).hexdigest(), input_file=target.name,
                      profile='Main', output_format='yuv420p', result=case['md5'])
        suite['test_vectors'].append(vector)
        vectors.append(dict(vector, input_path=relative, availability='available'))
    suite_path = bundle / 'suites/HEVC-HANG.json'
    suite_path.parent.mkdir()
    suite_path.write_text(json.dumps(suite, indent=2) + '\n')
    files['suites/HEVC-HANG.json'] = sha256(suite_path.read_bytes())
    (bundle / 'fixture-manifest.json').write_bytes((fixtures / 'manifest.json').read_bytes())
    files['fixture-manifest.json'] = sha256((bundle / 'fixture-manifest.json').read_bytes())
    # Each selection ends with its sole risk vector. Later boots use only the
    # healthy intra control before the risk vector, via existing followups.
    selections = {}
    for name, risk in (('initial', 4), ('lt8', 5), ('wpp0', 6)):
        selection = dict(suite='HEVC-HANG', start=0, count=5 if name == 'initial' else 1)
        selection['fluster_followups'] = ([] if name == 'initial' else
                                         [dict(suite='HEVC-HANG', start=risk, count=1)])
        selections[name] = selection
    selection_path = bundle / 'window-selections.json'
    selection_path.write_text(json.dumps(selections, indent=2) + '\n')
    files[selection_path.name] = sha256(selection_path.read_bytes())
    result = dict(schema=1, fluster_revision=sealed['fluster_revision'],
                  source_bundle_sha256=expected, files=files,
                  suites=[dict(name='HEVC-HANG', codec='H.265', test_method='md5',
                               suite_file='suites/HEVC-HANG.json',
                               mainline_decoder='GStreamer-H.265-V4L2',
                               vendor_decoder='GStreamer-H.265-V4L2', vectors=vectors)])
    (bundle / 'bundle-manifest.json').write_text(json.dumps(result, indent=2) + '\n')


def compare(fixtures, name, captured, measure_error=False):
    manifest = json.loads((fixtures / "manifest.json").read_text())
    case = next((c for c in manifest["cases"] if c["name"] == name), None)
    if case is None:
        raise ValueError(f"unknown fixture: {name}")
    if sha256((fixtures / case.get("filename", name + ".h264")).read_bytes()) != case["compressed_sha256"]:
        raise ValueError(f"{name}: compressed fixture changed")
    raw = captured.read_bytes()
    hashes = frame_hashes(raw, case["frame_size"])
    expected = case["frame_sha256"]
    mismatch = next((i for i in range(max(len(hashes), len(expected)))
                     if i >= len(hashes) or i >= len(expected)
                     or hashes[i] != expected[i]), None)
    exact = len(raw) == case["frames"] * case["frame_size"] and mismatch is None
    result = dict(
        name=name, bytes=len(raw), complete_frames=len(raw) // case["frame_size"],
        expected_frames=case["frames"], first_mismatch=mismatch,
        exact=exact, all_zero=bool(raw) and not any(raw),
    )
    if measure_error:
        reference = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(fixtures / case.get("filename", name + ".h264")),
            "-threads", "1", "-pix_fmt", case.get("reference_format", "yuv420p"),
            "-f", "rawvideo", "pipe:1",
        ])
        if sha256(reference) != case["decoded_sha256"]:
            raise ValueError("software reference differs from the fixture manifest")
        result["pixel_errors"] = pixel_errors(reference, raw, case["width"], case["height"])
    print(json.dumps(result, indent=2))
    return 0 if exact else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate_parser = commands.add_parser("generate", help="create a new fixture directory")
    generate_parser.add_argument("output", type=Path)
    generate_parser.add_argument("--codec", choices=("h264", "mpeg2", "mjpeg"), default="h264")
    fields_parser = commands.add_parser("generate-fields", help="download and trim the pinned MPEG-2 field sample")
    fields_parser.add_argument("output", type=Path)
    hang_parser = commands.add_parser('generate-hevc-hang', help='prepare offline SPS LT and WPP experiments')
    hang_parser.add_argument('output', type=Path)
    hang_parser.add_argument('--intra', type=Path, required=True, help='already passed all-IDR Annex B mother')
    hang_parser.add_argument('--intra-sha256', required=True)
    hang_parser.add_argument('--ltr', type=Path, required=True, help='original LTRPSPS Annex B input')
    hang_parser.add_argument('--ltr-sha256', required=True)
    hang_parser.add_argument('--wpp-control', type=Path, required=True, help='passed two-column WPP_E input')
    hang_parser.add_argument('--wpp-control-sha256', required=True)
    hang_parser.add_argument('--fluster-bundle', type=Path, required=True, help='existing sealed Fluster bundle')
    hang_parser.add_argument('--fluster-bundle-sha256', required=True, help='SHA256 of its bundle-manifest.json')
    compare_parser = commands.add_parser("compare", help="compare one captured I420 stream")
    compare_parser.add_argument("fixtures", type=Path)
    compare_parser.add_argument("name")
    compare_parser.add_argument("captured", type=Path)
    compare_parser.add_argument("--measure-error", action="store_true",
                                help="report per-frame Y/U/V differences; exit still requires exact pixels")
    args = parser.parse_args()
    if args.command == "generate":
        return generate(args.output, args.codec)
    if args.command == "generate-fields":
        return generate_fields(args.output)
    if args.command == 'generate-hevc-hang':
        return generate_hevc_hang(args)
    return compare(args.fixtures, args.name, args.captured, args.measure_error)


if __name__ == "__main__":
    raise SystemExit(main())
