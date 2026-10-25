#!/usr/bin/env python3
"""Exercise format choice from the patched upstream V4L2 source without hardware."""
from pathlib import Path
import subprocess
import sys
import tempfile

from test_gstreamer_orphan import function

FIXTURE = r'''
#include <assert.h>
#include <stdlib.h>
#include <glib.h>
#include <linux/videodev2.h>
typedef struct {
  struct v4l2_fmtdesc formats[2];
  unsigned count;
  gboolean prefered_non_contiguous;
} GstV4l2Object;
static struct v4l2_fmtdesc *
gst_v4l2_object_get_format_from_fourcc(GstV4l2Object *obj,guint32 fourcc) {
  for(unsigned i=0;i<obj->count;i++)
    if(obj->formats[i].pixelformat==fourcc)return &obj->formats[i];
  return NULL;
}
'''

CHECK = r'''
static void check(gboolean contiguous,gboolean separate,gboolean requested) {
  GstV4l2Object obj={0};
  if(contiguous)obj.formats[obj.count++].pixelformat=V4L2_PIX_FMT_NV21;
  if(separate)obj.formats[obj.count++].pixelformat=V4L2_PIX_FMT_NV21M;
  if(requested)g_setenv("GST_V4L2_PREFER_CONTIGUOUS","1",TRUE);
  else g_unsetenv("GST_V4L2_PREFER_CONTIGUOUS");
  obj.prefered_non_contiguous=TRUE;
  struct v4l2_fmtdesc *fmt=gst_v4l2_object_choose_raw_layout(
      &obj,V4L2_PIX_FMT_NV21,V4L2_PIX_FMT_NV21M,TRUE);
  if(!contiguous&&!separate){assert(!fmt);assert(!obj.prefered_non_contiguous);return;}
  guint32 expected=(separate&&(!requested||!contiguous))
      ? V4L2_PIX_FMT_NV21M:V4L2_PIX_FMT_NV21;
  assert(fmt&&fmt->pixelformat==expected);
  assert(obj.prefered_non_contiguous==(expected==V4L2_PIX_FMT_NV21M));
  /* Compressed/non-planar formats still use their ordinary single fourcc. */
  fmt=gst_v4l2_object_choose_raw_layout(&obj,expected,0,FALSE);
  assert(fmt&&fmt->pixelformat==expected&&!obj.prefered_non_contiguous);
  if(contiguous&&separate) {
    fmt=gst_v4l2_object_choose_raw_layout(&obj,V4L2_PIX_FMT_NV21,V4L2_PIX_FMT_NV21M,FALSE);
    assert(fmt&&fmt->pixelformat==V4L2_PIX_FMT_NV21M&&obj.prefered_non_contiguous);
  }
}
int main(void) {
  for(unsigned options=0;options<8;options++)
    check(options&1,options&2,options&4);
  return 0;
}
'''


def main():
    source = Path(sys.argv[1]).read_text()
    body = function(source, 'gst_v4l2_object_choose_raw_layout')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        cfile, binary = root / 'layout.c', root / 'layout'
        cfile.write_text(FIXTURE + '\nstatic struct v4l2_fmtdesc *\n' + body + CHECK)
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'glib-2.0'], text=True).split()
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(cfile), *flags, '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('Contiguous preference and unsupported-format fallback checks passed')


if __name__ == '__main__':
    main()
