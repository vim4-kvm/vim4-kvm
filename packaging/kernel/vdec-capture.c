/* SPDX-License-Identifier: MIT */
/* Build with pkg-config --cflags --libs gstreamer-app-1.0 gstreamer-video-1.0. */
#include <gst/app/gstappsink.h>
#include <gst/video/video.h>
#include <stdio.h>

static gboolean write_i420(FILE *output, GstVideoFrame *frame, const GstVideoInfo *visible)
{
	for (guint plane = 0; plane < 3; plane++) {
		guint width = GST_VIDEO_INFO_COMP_WIDTH(visible, plane);
		guint height = GST_VIDEO_INFO_COMP_HEIGHT(visible, plane);
		gint stride = GST_VIDEO_FRAME_PLANE_STRIDE(frame, plane);
		const guint8 *data = GST_VIDEO_FRAME_PLANE_DATA(frame, plane);

		/* GstVideoMeta may put each plane after padded rows or a larger stride. */
		for (guint row = 0; row < height; row++) {
			if (fwrite(data + (gssize)row * stride, 1, width, output) != width)
				return FALSE;
		}
	}
	return TRUE;
}

int main(int argc, char **argv)
{
	GstElement *pipeline = NULL, *sink = NULL;
	GstBus *bus = NULL;
	GError *error = NULL;
	FILE *output = NULL;
	guint frames = 0;
	guint64 expected;
	char *end;
	int status = 1;

	if (argc != 4) {
		g_printerr("Usage: %s 'pipeline ! appsink name=capture' output.i420 frames\n", argv[0]);
		return 2;
	}
	expected = g_ascii_strtoull(argv[3], &end, 10);
	if (!expected || *end || expected > G_MAXUINT)
		return 2;
	gst_init(NULL, NULL);
	pipeline = gst_parse_launch(argv[1], &error);
	if (error || !pipeline) {
		g_printerr("Pipeline: %s\n", error ? error->message : "missing pipeline");
		goto done;
	}
	sink = gst_bin_get_by_name(GST_BIN(pipeline), "capture");
	if (!sink || !GST_IS_APP_SINK(sink)) {
		g_printerr("Pipeline must end in appsink name=capture\n");
		goto done;
	}
	gst_app_sink_set_max_buffers(GST_APP_SINK(sink), 2);
	g_object_set(sink, "sync", FALSE, NULL);
	output = fopen(argv[2], "wb");
	if (!output) {
		perror(argv[2]);
		goto done;
	}
	bus = gst_element_get_bus(pipeline);
	if (gst_element_set_state(pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE)
		goto done;
	for (;;) {
		GstSample *sample = gst_app_sink_try_pull_sample(GST_APP_SINK(sink), 5 * GST_SECOND);
		GstVideoInfo info;
		GstVideoFrame frame;
		gboolean written;

		if (!sample) {
			GstMessage *message = gst_bus_pop_filtered(bus, GST_MESSAGE_ERROR);

			if (message) {
				gchar *debug = NULL;

				gst_message_parse_error(message, &error, &debug);
				g_printerr("Decode: %s (%s)\n", error->message, debug ? debug : "");
				g_free(debug);
				gst_message_unref(message);
			} else if (gst_app_sink_is_eos(GST_APP_SINK(sink)) && frames == expected) {
				status = 0;
			} else {
				g_printerr("Capture stopped or timed out at frame %u/%" G_GUINT64_FORMAT "\n",
					   frames, expected);
			}
			break;
		}
		if (!gst_video_info_from_caps(&info, gst_sample_get_caps(sample)) ||
		    GST_VIDEO_INFO_FORMAT(&info) != GST_VIDEO_FORMAT_I420 || frames >= expected ||
		    !gst_video_frame_map(&frame, &info, gst_sample_get_buffer(sample), GST_MAP_READ)) {
			g_printerr("Invalid frame layout, format or frame count\n");
			gst_sample_unref(sample);
			break;
		}
		if (!frames) {
			gchar *caps = gst_caps_to_string(gst_sample_get_caps(sample));

			g_print("Caps: %s\nStrides: %d %d %d\n", caps,
				GST_VIDEO_FRAME_PLANE_STRIDE(&frame, 0),
				GST_VIDEO_FRAME_PLANE_STRIDE(&frame, 1),
				GST_VIDEO_FRAME_PLANE_STRIDE(&frame, 2));
			g_free(caps);
		}
		written = write_i420(output, &frame, &info);
		gst_video_frame_unmap(&frame);
		gst_sample_unref(sample);
		if (!written)
			break;
		frames++;
	}
done:
	if (pipeline)
		gst_element_set_state(pipeline, GST_STATE_NULL);
	if (output && fclose(output))
		status = 1;
	if (bus)
		gst_object_unref(bus);
	if (sink)
		gst_object_unref(sink);
	if (pipeline)
		gst_object_unref(pipeline);
	g_clear_error(&error);
	g_print("Captured %u frames; status %d\n", frames, status);
	return status;
}
