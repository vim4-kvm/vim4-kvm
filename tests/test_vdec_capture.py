"""The pixel oracle must omit V4L2 padding and preserve unconverted Y/U/V bytes."""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'packaging/kernel/vdec-capture.c'


class CaptureLayoutTests(unittest.TestCase):
    def test_padded_video_meta_is_written_as_visible_i420(self):
        if not shutil.which('cc') or not shutil.which('pkg-config'):
            self.skipTest('C compiler and GStreamer development packages required')
        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'gstreamer-app-1.0',
                                'gstreamer-video-1.0'], text=True, capture_output=True)
        if flags.returncode:
            self.skipTest('GStreamer development packages required')
        code = '#define main capture_main\n#include ' + json.dumps(str(SOURCE)) + r'''
#undef main
#include <assert.h>
int main(void)
{
    gst_init(NULL, NULL);
    GstVideoInfo info;
    GstVideoFrame frame;
    GstBuffer *buffer = gst_buffer_new_allocate(NULL, 192, NULL);
    GstMapInfo map;
    gsize offsets[4] = { 0, 128, 160, 0 };
    gint strides[4] = { 16, 8, 8, 0 };
    gst_video_info_set_format(&info, GST_VIDEO_FORMAT_I420, 10, 4);
    assert(gst_buffer_map(buffer, &map, GST_MAP_WRITE));
    memset(map.data, 0xee, map.size);
    for (unsigned p = 0; p < 3; p++)
        for (unsigned y = 0; y < (p ? 2 : 4); y++)
            for (unsigned x = 0; x < (p ? 5 : 10); x++)
                map.data[offsets[p] + y * strides[p] + x] = 16 + p * 50 + y * 10 + x;
    gst_buffer_unmap(buffer, &map);
    assert(gst_buffer_add_video_meta_full(buffer, GST_VIDEO_FRAME_FLAG_NONE,
                                          GST_VIDEO_FORMAT_I420, 10, 4, 3, offsets, strides));
    assert(gst_video_frame_map(&frame, &info, buffer, GST_MAP_READ));
    FILE *output = tmpfile();
    assert(output && write_i420(output, &frame, &info));
    assert(ftell(output) == 60);
    rewind(output);
    for (unsigned p = 0; p < 3; p++)
        for (unsigned y = 0; y < (p ? 2 : 4); y++)
            for (unsigned x = 0; x < (p ? 5 : 10); x++)
                assert(fgetc(output) == (int)(16 + p * 50 + y * 10 + x));
    assert(fgetc(output) == EOF);
    fclose(output);
    gst_video_frame_unmap(&frame);
    gst_buffer_unref(buffer);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'capture-test.c'
            binary = Path(directory) / 'capture-test'
            source.write_text(code)
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(source),
                            *shlex.split(flags.stdout), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
