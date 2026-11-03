"""Replay the patched encoder's startup and per-frame controls without hardware.

Run with the path to the patched sys/v4l2/gstv4l2videoenc.c on Linux.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

from test_gstreamer_orphan import function


def main(source):
    start = function(source, 'gst_v4l2_video_enc_start')
    submit = function(source, 'gst_v4l2_video_enc_handle_frame')
    setup = start[start.index('  const GstStructure *controls'):start.index('  gst_v4l2_object_unlock')]
    controls = submit[submit.index('  if (frame->input_buffer) {'):submit.index('    GST_VIDEO_ENCODER_STREAM_UNLOCK')]
    fixture = r'''
#include <assert.h>
#include <gst/video/video.h>
#include <linux/videodev2.h>
#include <string.h>

static int writes, requests;
static int record_ioctl(int fd, unsigned long op, struct v4l2_control *ctrl) {
  assert(op == VIDIOC_S_CTRL);
  if (ctrl->id == V4L2_CID_MPEG_VIDEO_FORCE_KEY_FRAME) requests++;
  else {
    assert(ctrl->id == V4L2_CID_MPEG_VIDEO_H264_P_FRAME_MIN_QP);
    ++writes;
  }
  return 0;
}
static struct {
  GstStructure *extra_controls;
  struct v4l2_capability vcap;
  int video_fd;
  int (*ioctl)(int, unsigned long, struct v4l2_control *);
} output = {.vcap.driver = "wave5-enc", .ioctl = record_ioctl};
static struct {
  typeof(output) *v4l2output;
  const char *codec_name;
  gboolean wave5_avc_recovery;
  guint recovery_steps;
} device = {&output, "H264"}, *self = &device;
#define GST_V4L2_VIDEO_ENC_GET_CLASS(self) (self)
#undef GST_ELEMENT_ERROR
#undef GST_ELEMENT_WARNING
#define GST_ELEMENT_ERROR(...) ((void)0)
#define GST_ELEMENT_WARNING(...) ((void)0)
static void start(void) {
SETUP
}
static GstFlowReturn submit(GstVideoCodecFrame *frame) {
  GstFlowReturn ret = GST_FLOW_OK;
CONTROLS
  }
drop:
  return ret;
}
int main(void) {
  gst_init(NULL, NULL);
  const int floors[] = {-1, 26, 12};
  for (guint i = 0; i < G_N_ELEMENTS(floors); ++i) {
    output.extra_controls = gst_structure_new("controls", "video_gop_size", G_TYPE_INT, 0, NULL);
    if (floors[i] >= 0)
      gst_structure_set(output.extra_controls, "h264_p_frame_minimum_qp_value", G_TYPE_INT, floors[i], NULL);
    writes = requests = 0;
    start();
    GstVideoCodecFrame frame = {.input_buffer = gst_buffer_new()};
    for (int n = 0; n < 32; ++n) {
      frame.flags = n == 16 ? GST_VIDEO_CODEC_FRAME_FLAG_FORCE_KEYFRAME : 0;
      assert(submit(&frame) == GST_FLOW_OK);
    }
    assert(requests == 1);
    assert(writes == (floors[i] == 12 ? 28 : 0));
    gst_buffer_unref(frame.input_buffer);
    gst_structure_free(output.extra_controls);
  }
}
'''
    with tempfile.TemporaryDirectory() as temp:
        test = Path(temp) / 'test.c'
        test.write_text(fixture.replace('SETUP', setup).replace('CONTROLS', controls))
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gstreamer-video-1.0'], text=True)
        exe = test.with_suffix('')
        subprocess.run(['cc', '-std=gnu11', '-o', exe, test, *flags.split()], check=True)
        subprocess.run([exe], check=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]).read_text())
