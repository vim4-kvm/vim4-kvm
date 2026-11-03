#!/usr/bin/env python3
"""Exercise the actual V4L2 caps path that rejected the native HDR source.

No device is opened. Requires the pinned GStreamer source tree, development
libraries and a C compiler. The old patch maps P010 to a video format but
returns NULL before the encoder can expose it as sink caps.
"""
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from test_gstreamer_orphan import function


def check_capture_fallback(source, flags):
    text = source.with_name('gstv4l2src.c').read_text()
    fixture = r'''
#include <gst/video/video.h>
#undef GST_DEBUG_OBJECT
#define GST_DEBUG_OBJECT(...) ((void)0)
typedef struct { int unused; } GstV4l2Object;
typedef struct {
  GstV4l2Object *v4l2object;
  unsigned offset, renegotiation_adjust;
  gboolean pending_set_fmt;
} GstV4l2Src;
typedef GstV4l2Src GstBaseSrc;
#define GST_V4L2SRC(x) (x)
typedef struct { GError *error; } GstV4l2Error;
#define GST_V4L2_ERROR_INIT {NULL}
struct PreferredCapsInfo { int width, height; };
static int attempts, error_code;
static void gst_v4l2_clear_error(GstV4l2Error *e) {g_clear_error(&e->error);}
static void gst_v4l2_error(GstV4l2Src *s, GstV4l2Error *e)
{(void)s; gst_v4l2_clear_error(e);}
static void gst_v4l2_src_fixate_struct_with_preference(GstStructure *s,
    struct PreferredCapsInfo *p) {(void)s; (void)p;}
static int gst_v4l2src_fixed_caps_compare(GstCaps *a, GstCaps *b, void *p) {
  (void)p;
  const char *left=gst_structure_get_string(gst_caps_get_structure(a,0),"format");
  const char *right=gst_structure_get_string(gst_caps_get_structure(b,0),"format");
  return g_str_equal(right,"v308")-g_str_equal(left,"v308");
}
static gboolean gst_v4l2_object_caps_is_subset(GstV4l2Object *o,GstCaps *c)
{(void)o; (void)c; return FALSE;}
static gboolean gst_v4l2_object_caps_equal(GstV4l2Object *o,GstCaps *c)
{(void)o; (void)c; return FALSE;}
static GstCaps *gst_v4l2_object_get_current_caps(GstV4l2Object *o)
{(void)o; return NULL;}
static gboolean gst_v4l2_object_try_format(GstV4l2Object *o,GstCaps *c,GstV4l2Error *e) {
  (void)o; attempts++;
  if(g_str_equal(gst_structure_get_string(gst_caps_get_structure(c,0),"format"),"RGB"))
    return TRUE;
  e->error=g_error_new_literal(GST_RESOURCE_ERROR,error_code,"TRY_FMT rejected");
  return FALSE;
}
'''
    fixture += '\nstatic GstCaps *\n' + function(text, 'gst_v4l2src_fixate')
    fixture += r'''
int main(void) {
  gst_init(NULL,NULL);
  GstV4l2Src source={0}; struct PreferredCapsInfo pref={1920,1080};
  const char *mixed="video/x-raw,format=v308,width=1920,height=1080,framerate=60/1;"
                    "video/x-raw,format=RGB,width=1920,height=1080,framerate=60/1";
  error_code=GST_RESOURCE_ERROR_SETTINGS; /* V4L2 EINVAL mapping */
  GstCaps *chosen=gst_v4l2src_fixate(&source,gst_caps_from_string(mixed),&pref);
  g_assert_nonnull(chosen); g_assert_cmpint(attempts,==,2);
  g_assert_cmpstr(gst_structure_get_string(gst_caps_get_structure(chosen,0),"format"),==,"RGB");
  gst_caps_unref(chosen); attempts=0;
  chosen=gst_v4l2src_fixate(&source,gst_caps_from_string(
      "video/x-raw,format=v308,width=1920,height=1080,framerate=60/1"),&pref);
  g_assert_null(chosen); g_assert_cmpint(attempts,==,1);
  attempts=0; error_code=GST_RESOURCE_ERROR_FAILED;
  chosen=gst_v4l2src_fixate(&source,gst_caps_from_string(mixed),&pref);
  g_assert_null(chosen); g_assert_cmpint(attempts,==,1);
}
'''
    with tempfile.TemporaryDirectory() as temporary:
        cfile, binary = Path(temporary) / 'fallback.c', Path(temporary) / 'fallback'
        cfile.write_text(fixture)
        # The unchanged upstream fixate loop compares gint with guint.
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare', str(cfile),
                        *flags, '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def main():
    source = Path(sys.argv[1]).resolve()
    text = source.read_text()
    fixture = r'''
#include <gst/video/video.h>
#include "ext/videodev2.h"
typedef struct { GstObject *dbg_obj; } GstV4l2Object;
static guint32 available_fourcc;
static struct v4l2_fmtdesc *
gst_v4l2_object_choose_raw_layout (GstV4l2Object *object, guint32 fourcc,
    guint32 noncontiguous, gboolean raw)
{
  static struct v4l2_fmtdesc format;
  (void)object; (void)noncontiguous;
  g_assert_true(raw);
  format.pixelformat = fourcc;
  return fourcc == available_fourcc ? &format : NULL;
}
'''
    fixture += '\nstatic GstVideoFormat\n' + function(
        text, 'gst_v4l2_object_v4l2fourcc_to_video_format')
    fixture += '\nstatic GstStructure *\n' + function(
        text, 'gst_v4l2_object_v4l2fourcc_to_bare_struct')
    fixture += '\nstatic gboolean\n' + function(
        text, 'gst_v4l2_object_get_caps_info')
    fixture += r'''
int main(void) {
  gst_init(NULL, NULL);
  GstCaps *source = gst_caps_from_string(
      "video/x-raw,format=P010_10LE,width=3840,height=2160,framerate=60/1");
  GstStructure *structure =
      gst_v4l2_object_v4l2fourcc_to_bare_struct(V4L2_PIX_FMT_P010);
  g_assert_nonnull(structure);
  GstCaps *encoder = gst_caps_new_full(structure, NULL);
  g_assert_true(gst_caps_can_intersect(source, encoder));
  GstCaps *negotiated = gst_caps_intersect(source, encoder);
  GstVideoInfo info;
  g_assert_true(gst_video_info_from_caps(&info, negotiated));
  g_assert_cmpint(GST_VIDEO_INFO_FORMAT(&info), ==, GST_VIDEO_FORMAT_P010_10LE);
  g_assert_cmpint(info.stride[0], ==, 7680);
  g_assert_cmpuint(info.size, ==, 24883200);
  gst_caps_unref(negotiated);
  gst_caps_unref(encoder);
  structure = gst_v4l2_object_v4l2fourcc_to_bare_struct(V4L2_PIX_FMT_NV12);
  g_assert_nonnull(structure);
  encoder = gst_caps_new_full(structure, NULL);
  g_assert_false(gst_caps_can_intersect(source, encoder));
  gst_caps_unref(encoder);
  gst_caps_unref(source);
  /* Private packed 4:2:2 data must never acquire standard raw caps here. */
  g_assert_null(gst_v4l2_object_v4l2fourcc_to_bare_struct(
      v4l2_fourcc('A', 'M', 'L', 'Y')));
  /* Capture YUV24 must advertise raw caps and negotiate back to YUV3. */
  GstV4l2Object object = {0};
  struct v4l2_fmtdesc *format;
  source = gst_caps_from_string(
      "video/x-raw,format=v308,width=3840,height=2160,framerate=60/1");
  structure = gst_v4l2_object_v4l2fourcc_to_bare_struct(V4L2_PIX_FMT_YUV24);
  g_assert_nonnull(structure);
  encoder = gst_caps_new_full(structure, NULL);
  g_assert_true(gst_caps_can_intersect(source, encoder));
  available_fourcc = V4L2_PIX_FMT_YUV24;
  g_assert_true(gst_v4l2_object_get_caps_info(&object, source, &format, &info));
  g_assert_cmpuint(format->pixelformat, ==, V4L2_PIX_FMT_YUV24);
  g_assert_cmpint(info.stride[0], ==, 11520);
  g_assert_cmpuint(info.size, ==, 24883200);
  available_fourcc = V4L2_PIX_FMT_NV12;
  g_assert_false(gst_v4l2_object_get_caps_info(&object, source, &format, &info));
  gst_caps_unref(encoder);
  gst_caps_unref(source);
  return 0;
}
'''
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'gstreamer-video-1.0'], text=True))
    with tempfile.TemporaryDirectory() as temporary:
        cfile, binary = Path(temporary) / 'caps.c', Path(temporary) / 'caps'
        cfile.write_text(fixture)
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-I', str(source.parent),
                        str(cfile), *flags, '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('P010 caps and bidirectional YUV24/v308 negotiation: PASS')
    check_capture_fallback(source, flags)
    print('Actual v4l2src fixate: RGB fallback, fixed v308 and fatal link error: PASS')


if __name__ == '__main__':
    main()
