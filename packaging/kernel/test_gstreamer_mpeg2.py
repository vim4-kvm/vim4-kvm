#!/usr/bin/env python3
"""Replay actual MPEG-2 sequence control conversion, without opening a device."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    source = Path(sys.argv[1]).read_text()
    start = source.index('  /* copy quantiser from the sequence header,')
    end = source.index('  /* *INDENT-ON* */', start)
    conversion = source[start:end]
    vbv_type = re.search(r'(guint\d+) vbv_buffer_size;', source).group(1)
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <linux/v4l2-controls.h>
typedef uint16_t guint16;
typedef uint32_t guint32;
struct state {
    unsigned int width, height;
    VBV_TYPE vbv_buffer_size;
    struct v4l2_ctrl_mpeg2_sequence v4l2_sequence;
    struct v4l2_ctrl_mpeg2_quantisation v4l2_quantisation;
};
struct sequence { unsigned char intra_quantizer_matrix[64], non_intra_quantizer_matrix[64]; };
struct extension { unsigned int profile, level, profile_level_escape_bit, chroma_format, progressive; };
static void convert(struct state *self, struct sequence *seq, struct extension *seq_ext)
{
CONVERSION
}
int main(void)
{
    struct state state = { .width = 640, .height = 368 };
    struct sequence seq;
    struct extension ext = { .profile = 4, .level = 8, .chroma_format = 1, .progressive = 1 };
    for (unsigned int i = 0; i < 64; i++) {
        seq.intra_quantizer_matrix[i] = 8 + i;
        seq.non_intra_quantizer_matrix[i] = 16 + i;
    }
    const unsigned int vbv[] = { 112, 0x12345, 0x3ffff };
    for (unsigned int i = 0; i < 3; i++) {
        state.vbv_buffer_size = vbv[i];
        convert(&state, &seq, &ext);
        assert(state.v4l2_sequence.vbv_buffer_size == vbv[i]);
        assert(state.v4l2_sequence.profile_and_level_indication == 0x48);
        assert(!memcmp(state.v4l2_quantisation.intra_quantiser_matrix,
                       state.v4l2_quantisation.chroma_intra_quantiser_matrix, 64));
        assert(!memcmp(state.v4l2_quantisation.non_intra_quantiser_matrix,
                       state.v4l2_quantisation.chroma_non_intra_quantiser_matrix, 64));
    }
    /* A new sequence must also discard matrices retained from the old one. */
    memset(seq.intra_quantizer_matrix, 23, 64);
    ext.profile_level_escape_bit = 1;
    convert(&state, &seq, &ext);
    assert(state.v4l2_sequence.profile_and_level_indication == 0xc8);
    for (unsigned int i = 0; i < 64; i++)
        assert(state.v4l2_quantisation.chroma_intra_quantiser_matrix[i] == 23);
    return 0;
}
'''.replace('VBV_TYPE', vbv_type).replace('CONVERSION', conversion)
    with tempfile.TemporaryDirectory(prefix='gst-mpeg2-') as temp:
        root = Path(temp)
        (root / 'test.c').write_text(code)
        subprocess.run(['cc', '-Wall', '-Werror', str(root / 'test.c'),
                        '-o', str(root / 'test')], check=True)
        subprocess.run([str(root / 'test')], check=True)
    print('MPEG-2 sequence controls: PASS')


if __name__ == '__main__':
    main()
