"""Build the shared RTK profile without replacing its preferred mode or identity."""
from board.vim4vrr import Range, rewrite, validate


def rtk_extended(original):
    """Add 1080p120, 1440p120 and ultrawide timings to the 256-byte RTK table.

    The second CTA keeps all original data-block positions and detailed timings
    intact. Its 2560x1080 mode uses CTA VIC 90; 1440-line PC modes use DTDs.
    """
    validate(original)
    if len(original) != 256:
        raise ValueError('Expected the original two-block RTK EDID')
    data = bytearray(original)
    data[0x8c:0x8e] = bytes((63, 64))
    data[0x72] = 120  # Vertical range maximum.
    data[0x74] = 180  # 1440p120 needs about 178 kHz horizontal scan rate.
    for offset in (0, 128):
        data[offset + 127] = -sum(data[offset:offset + 127]) % 256
    data = bytearray(rewrite(bytes(data), 'hdmi-forum', Range(48, 120)))
    # Reuse the existing 2560x1440 reduced-blanking timing, doubling its clock.
    start = 128 + data[130]
    timings = [data[o:o + 18] for o in range(start, 237, 18)]
    qhd = next(t for t in timings if t[2] | ((t[4] & 0xf0) << 4) == 2560
               and t[5] | ((t[7] & 0xf0) << 4) == 1440)
    qhd120 = bytearray(qhd)
    qhd120[:2] = (int.from_bytes(qhd[:2], 'little') * 2).to_bytes(2, 'little')
    # CVT reduced blanking: 3440 3488 3520 3600, 1440 1443 1453 1481.
    ultra = bytearray(qhd)
    ultra[:2] = (31975).to_bytes(2, 'little')
    ultra[2] = 3440 & 255
    ultra[4] = (3440 >> 8) << 4 | (ultra[4] & 15)
    ultra[8:12] = bytes((48, 32, 0x3a, 0))
    extra = bytearray(bytes((2, 3, 6, 0, 0x41, 90)) + qhd120 + ultra)
    extra.extend(bytes(128 - len(extra)))
    extra[127] = -sum(extra[:127]) % 256
    data[126] = 2
    data[127] = -sum(data[:127]) % 256
    result = bytes(data + extra)
    validate(result)
    return result
