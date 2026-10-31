"""Read existing named RX/VDIN diagnostics, never infer mapping from preference.

The caller provides reviewed hdr_status/status paths from the selected kernel.
This temporary diagnostic dependency should become per-frame V4L2 metadata.
It proves the programmed pixel domain, not LUT contents or screen luminance.
"""
from pathlib import Path


def fields(path):
    return dict(line.split(': ', 1) for line in Path(path).read_text().splitlines() if ': ' in line)


def mapped_sdr(rx_path, hdr_path, colorspace, quantization):
    before = fields(rx_path)
    hdr = fields(hdr_path)
    after = fields(rx_path)
    for name in ('hdr_input', 'link_ready', 'capture_users', 'drm_received_ns'):
        if name not in before or before[name] != after.get(name):
            raise ValueError('RX changed during mapping readback')
    if before['link_ready'] != '1' or int(before['capture_users']) < 1:
        raise ValueError('RX has no active qualified capture lease')
    if colorspace != 'rec709' or quantization != 'limited':
        raise ValueError('Capture is not SDR 709 limited')
    if hdr.get('stream_active') != '1' or hdr.get('curve_pending') != '0':
        raise ValueError('HDR2 programming is not stable')
    if before['hdr_input'] == '0' and hdr.get('profile_programmed') == '0':
        return False
    if before['hdr_input'] == '1' and hdr.get('profile_programmed') == '1':
        control = int(hdr['hdr_ctrl'], 16)
        required = (1 << 15) | (1 << 14) | (1 << 13)
        if control & required == required:
            return True
    raise ValueError('Source HDR and HDR2 hardware readback disagree')
