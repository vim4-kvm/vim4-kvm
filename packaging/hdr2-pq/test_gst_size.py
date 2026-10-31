#!/usr/bin/env python3
"""Execute the real allocation-size policy; no devices or GStreamer plugins."""
from pathlib import Path
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
start = text.index('static guint\ncalculate_max_sizeimage ')
function = text[start:text.index('\n}', start) + 2]
fixture = r'''
#include <assert.h>
typedef unsigned guint;
typedef struct { unsigned max_width, max_height; int element; } GstV4l2Object;
#define GST_IS_VIDEO_ENCODER(e) (e)
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define ENCODED_BUFFER_MIN_SIZE (256*1024)
'''
checks = r'''
int main(void) {
 GstV4l2Object obj={8192,8192,1};
 /* Same device maximum that generated the 32 MiB failed allocation. */
 assert(calculate_max_sizeimage(&obj,8,3840,2160)==4147200);
 assert(calculate_max_sizeimage(&obj,10,3840,2160)==5184000);
 assert(calculate_max_sizeimage(&obj,8,64,64)==256*1024);
 assert(calculate_max_sizeimage(&obj,8,0,0)==33554432);
 obj.element=0; /* Decoder resolution changes retain existing headroom. */
 assert(calculate_max_sizeimage(&obj,8,3840,2160)==33554432);
}
'''
with tempfile.TemporaryDirectory() as directory:
    source, binary = Path(directory) / 'size.c', Path(directory) / 'size'
    source.write_text(fixture + function + checks)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                    '-fno-sanitize-recover=all', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('Actual encoded allocation size: 4K encoder 4,147,200; decoder 33,554,432: PASS')
