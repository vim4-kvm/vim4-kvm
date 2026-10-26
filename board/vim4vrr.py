"""Offline EDID policy for experimental HDMI VRR; never accesses hardware.

Ranges describe a single protocol. A fixed timing's scan-range descriptor is
not evidence of VRR support. Callers supply the receiver's qualified range;
local HDMI output additionally needs a sink advertising the same protocol.
"""
from dataclasses import dataclass


FORUM = b'\xd8\x5d\xc4'
AMD = b'\x1a\x00\x00'
PROTOCOLS = {'hdmi-forum': FORUM, 'amd-freesync': AMD}


@dataclass(frozen=True)
class Range:
    minimum: int
    maximum: int

    def __post_init__(self):
        if not 1 <= self.minimum < self.maximum <= 1023:
            raise ValueError('VRR range must satisfy 1 <= minimum < maximum <= 1023 Hz')

    def intersect(self, other):
        low, high = max(self.minimum, other.minimum), min(self.maximum, other.maximum)
        if low >= high:
            raise ValueError('VRR ranges have no variable refresh interval in common')
        return Range(low, high)


def validate(edid):
    if (len(edid) not in (128, 256, 384, 512)
            or edid[:8] != b'\x00\xff\xff\xff\xff\xff\xff\x00'
            or len(edid) != 128 * (edid[126] + 1)
            or any(sum(edid[i:i + 128]) % 256 for i in range(0, len(edid), 128))):
        raise ValueError('Invalid EDID header, size, extension count or checksum')


def cta_blocks(extension):
    """Return data blocks and the offset where detailed timings start."""
    end = extension[2]
    if end == 0:
        if any(extension[4:127]):
            raise ValueError('CTA has data without a data-block boundary')
        return [], 4
    if not 4 <= end <= 127:
        raise ValueError('Invalid CTA data-block boundary')
    blocks, offset = [], 4
    while offset < end:
        header = extension[offset]
        length = header & 31
        if not header or offset + length + 1 > end:
            raise ValueError('Truncated or padded CTA data-block collection')
        blocks.append((header >> 5, bytes(extension[offset + 1:offset + length + 1])))
        offset += length + 1
    return blocks, end


def _forum_range(minimum, maximum):
    # HF-VSDB reserves maxima 1..99; zero means the selected mode's base rate,
    # not a zero-Hz ceiling. This tool only represents explicit bounded ranges.
    if not 1 <= minimum <= 48:
        raise ValueError('HDMI Forum VRR minimum must be between 1 and 48 Hz')
    if maximum == 0:
        raise ValueError('HDMI Forum VRRmax=0 depends on the video mode; '
                         'an explicitly qualified maximum is required')
    if maximum < 100:
        raise ValueError('HDMI Forum VRR maxima 1..99 are reserved; '
                         'an explicit maximum must be at least 100 Hz')
    return Range(minimum, maximum)


def capabilities(edid):
    validate(edid)
    result = {}
    for offset in range(128, len(edid), 128):
        extension = edid[offset:offset + 128]
        if extension[0] != 2:
            continue
        blocks, _ = cta_blocks(extension)
        for tag, payload in blocks:
            if tag != 3:
                continue
            if payload[:3] == FORUM and len(payload) >= 10:
                low, high = payload[8] & 63, ((payload[8] >> 6) << 8) | payload[9]
                protocol = 'hdmi-forum'
            elif payload[:3] == AMD and len(payload) >= 7 and payload[3] == 1:
                low, high = payload[5:7]
                protocol = 'amd-freesync'
            else:
                continue
            if low == high == 0:
                continue
            if protocol in result:
                raise ValueError('Duplicate VRR capability blocks')
            result[protocol] = (_forum_range(low, high) if protocol == 'hdmi-forum'
                                else Range(low, high))
    return result


def select_range(receiver, requested, protocol, sink=None):
    if protocol not in PROTOCOLS:
        raise ValueError('Unknown VRR protocol')
    selected = receiver.intersect(requested)
    if sink is not None:
        # The current TX sends HDMI Forum VTEM, not AMD FreeSync SPD packets.
        if protocol != 'hdmi-forum':
            raise ValueError('Local output currently requires HDMI Forum VRR')
        support = capabilities(sink).get(protocol)
        if support is None:
            raise ValueError('HDMI OUT display does not advertise HDMI Forum VRR')
        selected = selected.intersect(support)
    return selected


def rewrite(edid, protocol, selected):
    """Change VRR declarations only; preserve fixed timings and other blocks.

    Remove the alternate protocol's declaration so a source cannot negotiate
    its old, potentially wider range. No timing or colour format is qualified
    by this operation. A caller must use a baseline qualified for those modes.
    """
    validate(edid)
    capabilities(edid)  # Reject ambiguous/malformed existing declarations.
    if protocol not in PROTOCOLS:
        raise ValueError('Unknown VRR protocol')
    if protocol == 'hdmi-forum':
        _forum_range(selected.minimum, selected.maximum)
    if protocol == 'amd-freesync' and selected.maximum > 255:
        raise ValueError('AMD FreeSync v1 maximum is an eight-bit field')
    extensions = [bytearray(edid[i:i + 128]) for i in range(128, len(edid), 128)]
    ctas = [index for index, extension in enumerate(extensions) if extension[0] == 2]
    if not ctas:
        raise ValueError('A CTA baseline is required; no extension is added automatically')
    target = next((i for i in ctas if any(tag == 3 and p[:3] == PROTOCOLS[protocol]
                  for tag, p in cta_blocks(extensions[i])[0])), ctas[0])
    inserted = False
    for index in ctas:
        extension = extensions[index]
        blocks, end = cta_blocks(extension)
        updated = []
        for tag, payload in blocks:
            if tag == 3 and payload[:3] == AMD:
                if protocol != 'amd-freesync':
                    continue
                if len(payload) < 7 or payload[3] != 1:
                    raise ValueError('Unsupported AMD FreeSync block version/length')
                payload = payload[:5] + bytes((selected.minimum, selected.maximum)) + payload[7:]
                inserted = True
            elif tag == 3 and payload[:3] == FORUM:
                if protocol == 'hdmi-forum':
                    if len(payload) < 7:
                        raise ValueError('Truncated HDMI Forum VSDB')
                    value = bytearray(payload.ljust(10, b'\0'))
                    value[8] = selected.minimum | ((selected.maximum >> 8) << 6)
                    value[9] = selected.maximum & 255
                    payload = bytes(value)
                    inserted = True
                elif len(payload) >= 10:
                    payload = payload[:8] + b'\0\0' + payload[10:]
            updated.append((tag, payload))
        if index == target and not inserted:
            # New declarations deliberately omit QMS/FVA/FRL and deep colour.
            payload = (FORUM + bytes((1, 0, 0, 0, 0,
                       selected.minimum | ((selected.maximum >> 8) << 6), selected.maximum & 255))
                       if protocol == 'hdmi-forum' else
                       AMD + bytes((1, 1, selected.minimum, selected.maximum)))
            updated.append((3, payload))
            inserted = True
        collection = b''.join(bytes(((tag << 5) | len(payload),)) + payload for tag, payload in updated)
        # Only trailing zero padding may be consumed. DTD bytes remain intact.
        tail = bytes(extension[end:127]).rstrip(b'\0')
        if 4 + len(collection) + len(tail) > 127:
            raise ValueError('CTA has no room for VRR without deleting existing timings')
        result = bytearray(extension[:4] + collection + tail)
        result[2] = 4 + len(collection)
        result.extend(bytes(128 - len(result)))
        result[127] = -sum(result[:127]) % 256
        extensions[index] = result
    result = edid[:128] + b''.join(extensions)
    if capabilities(result) != {protocol: selected}:
        raise ValueError('EDID does not contain exactly the selected VRR declaration')
    return result
