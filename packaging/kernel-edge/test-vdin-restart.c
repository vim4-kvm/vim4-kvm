/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Keep the source and fd alive while the ioctl fixture changes interval type. */
#include <gst/gst.h>

int main(int argc, char **argv)
{
    gst_init(&argc, &argv);
    gchar *text = g_strdup_printf("v4l2src device=/dev/zero io-mode=rw num-buffers=1 ! "
        "video/x-raw,format=%s ! fakesink name=end sync=false", argv[1]);
    GstElement *pipeline = gst_parse_launch(text, NULL);
    GstElement *end = gst_bin_get_by_name(GST_BIN(pipeline), "end");
    GstElement *source = gst_bin_get_by_name(GST_BIN(pipeline), "v4l2src0");
    GstPad *src = gst_element_get_static_pad(source, "src");
    GstBus *bus = gst_element_get_bus(pipeline);
    GstPad *sink = gst_element_get_static_pad(end, "sink");
    for (int i = 0; i < 3; i++) {
        gst_element_set_state(pipeline, GST_STATE_READY);
        gst_element_get_state(pipeline, NULL, NULL, GST_SECOND);
        if (i) gst_caps_unref(gst_pad_query_caps(src, NULL));
        g_setenv("TEST_VRR_BASE", i == 1 ? "120" : "0", TRUE);
        gst_element_set_state(pipeline, GST_STATE_PLAYING);
        GstMessage *msg = gst_bus_timed_pop_filtered(bus, GST_SECOND, GST_MESSAGE_EOS | GST_MESSAGE_ERROR);
        g_assert_nonnull(msg);
        g_assert_cmpint(GST_MESSAGE_TYPE(msg), ==, GST_MESSAGE_EOS);
        gst_message_unref(msg);
        GstCaps *caps = gst_pad_get_current_caps(sink);
        g_assert_nonnull(caps);
        const GstStructure *s = gst_caps_get_structure(caps, 0);
        int n, d;
        g_assert_true(gst_structure_get_fraction(s, "framerate", &n, &d));
        g_assert_cmpint(n, ==, i == 1 ? 0 : 60);
        g_assert_cmpint(d, ==, 1);
        gboolean bounded = gst_structure_get_fraction(s, "max-framerate", &n, &d);
        g_assert_cmpint(bounded, ==, i == 1);
        if (bounded) g_assert_cmpint(n, ==, 120 * d);
        gst_caps_unref(caps);
    }
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(src);
    gst_object_unref(source);
    gst_object_unref(sink);
    gst_object_unref(bus);
    gst_object_unref(end);
    gst_object_unref(pipeline);
    g_free(text);
    return 0;
}
