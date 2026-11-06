#!/usr/bin/env python3
"""Replay MPEG-2 sequence and picture matrix updates without a device."""
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
    start = source.index('  /* overwrite the sequence ones if needed,')
    end = source.index('\n  return GST_FLOW_OK;', start)
    matrix_update = source[start:end]
    vbv_type = re.search(r'(guint\d+) vbv_buffer_size;', source).group(1)
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <linux/v4l2-controls.h>
typedef uint16_t guint16;
typedef uint32_t guint32;
struct state {
    unsigned int need_quantiser;
    unsigned int width, height;
    VBV_TYPE vbv_buffer_size;
    struct v4l2_ctrl_mpeg2_sequence v4l2_sequence;
    struct v4l2_ctrl_mpeg2_quantisation v4l2_quantisation;
};
struct sequence { unsigned char intra_quantizer_matrix[64], non_intra_quantizer_matrix[64]; };
struct extension { unsigned int profile, level, profile_level_escape_bit, chroma_format, progressive; };
struct matrix_extension {
    unsigned int load_intra_quantiser_matrix, load_non_intra_quantiser_matrix;
    unsigned int load_chroma_intra_quantiser_matrix, load_chroma_non_intra_quantiser_matrix;
    unsigned char intra_quantiser_matrix[64], non_intra_quantiser_matrix[64];
    unsigned char chroma_intra_quantiser_matrix[64], chroma_non_intra_quantiser_matrix[64];
};
struct slice { struct matrix_extension *quant_matrix; };
static void update(struct state *self, struct slice *slice)
{
MATRIX_UPDATE
}
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
    /* att updates luma in a picture extension without chroma load flags. */
    struct matrix_extension matrix = { .load_intra_quantiser_matrix = 1,
        .load_non_intra_quantiser_matrix = 1 };
    struct slice slice = { .quant_matrix = &matrix };
    memset(matrix.intra_quantiser_matrix, 8, 64);
    memset(matrix.non_intra_quantiser_matrix, 8, 64);
    update(&state, &slice);
    assert(state.need_quantiser);
    for (unsigned int i = 0; i < 64; i++) {
        assert(state.v4l2_quantisation.chroma_intra_quantiser_matrix[i] == 8);
        assert(state.v4l2_quantisation.chroma_non_intra_quantiser_matrix[i] == 8);
    }
    /* Explicit chroma matrices override the inherited luma in the same update. */
    matrix.load_chroma_intra_quantiser_matrix = 1;
    matrix.load_chroma_non_intra_quantiser_matrix = 1;
    memset(matrix.chroma_intra_quantiser_matrix, 25, 64);
    memset(matrix.chroma_non_intra_quantiser_matrix, 31, 64);
    update(&state, &slice);
    matrix.load_intra_quantiser_matrix = matrix.load_non_intra_quantiser_matrix = 0;
    matrix.load_chroma_intra_quantiser_matrix = matrix.load_chroma_non_intra_quantiser_matrix = 0;
    update(&state, &slice);
    slice.quant_matrix = 0;
    update(&state, &slice);
    for (unsigned int i = 0; i < 64; i++) {
        assert(state.v4l2_quantisation.intra_quantiser_matrix[i] == 8);
        assert(state.v4l2_quantisation.non_intra_quantiser_matrix[i] == 8);
        assert(state.v4l2_quantisation.chroma_intra_quantiser_matrix[i] == 25);
        assert(state.v4l2_quantisation.chroma_non_intra_quantiser_matrix[i] == 31);
    }
    return 0;
}
'''.replace('VBV_TYPE', vbv_type).replace('CONVERSION', conversion).replace('MATRIX_UPDATE', matrix_update)
    with tempfile.TemporaryDirectory(prefix='gst-mpeg2-') as temp:
        root = Path(temp)
        (root / 'test.c').write_text(code)
        subprocess.run(['cc', '-Wall', '-Werror', str(root / 'test.c'),
                        '-o', str(root / 'test')], check=True)
        subprocess.run([str(root / 'test')], check=True)
    print('MPEG-2 sequence and picture matrix controls: PASS')


if __name__ == '__main__':
    main()
