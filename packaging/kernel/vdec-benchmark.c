/* SPDX-License-Identifier: MIT */
/* Build with pkg-config --cflags --libs gstreamer-base-1.0. */
#include <gst/base/gstbasesink.h>
#include <stdio.h>
#include <sys/resource.h>

struct measurement {
	GMutex lock;
	guint64 frames;
	gint64 first;
	gint64 last;
};

static void handoff(GstElement *sink, GstBuffer *buffer, GstPad *pad,
		    gpointer user_data)
{
	struct measurement *measurement = user_data;
	gint64 now = g_get_monotonic_time();

	(void)sink;
	(void)buffer;
	(void)pad;
	g_mutex_lock(&measurement->lock);
	if (!measurement->frames)
		measurement->first = now;
	measurement->frames++;
	measurement->last = now;
	g_mutex_unlock(&measurement->lock);
}

static double cpu_seconds(void)
{
	struct rusage usage;

	if (getrusage(RUSAGE_SELF, &usage))
		return -1;
	return usage.ru_utime.tv_sec + usage.ru_stime.tv_sec +
	       (usage.ru_utime.tv_usec + usage.ru_stime.tv_usec) / 1000000.0;
}

static void report(GstElement *sink, struct measurement *measurement,
		   gint64 started, double cpu_start, gboolean final, gboolean success)
{
	GstStructure *stats = NULL;
	guint64 rendered = 0, dropped = 0, frames;
	gint64 first, last;
	double elapsed = (g_get_monotonic_time() - started) / 1000000.0;
	double cpu = cpu_seconds() - cpu_start;

	g_mutex_lock(&measurement->lock);
	frames = measurement->frames;
	first = measurement->first;
	last = measurement->last;
	g_mutex_unlock(&measurement->lock);
	g_object_get(sink, "stats", &stats, NULL);
	if (stats) {
		gst_structure_get_uint64(stats, "rendered", &rendered);
		gst_structure_get_uint64(stats, "dropped", &dropped);
		gst_structure_free(stats);
	}
	g_print("{\"event\":\"%s\",\"wall_us\":%" G_GINT64_FORMAT ",\"success\":%s,\"frames\":%" G_GUINT64_FORMAT
		",\"rendered\":%" G_GUINT64_FORMAT ",\"dropped\":%" G_GUINT64_FORMAT
		",\"elapsed_seconds\":%.6f,\"first_frame_seconds\":%.6f,"
		"\"frame_span_seconds\":%.6f,\"fps\":%.6f,\"cpu_seconds\":%.6f,"
		"\"one_core_percent\":%.6f}\n",
		final ? "summary" : "sample", g_get_real_time(), success ? "true" : "false",
		frames, rendered, dropped, elapsed, first ? (first - started) / 1000000.0 : -1,
		first ? (last - first) / 1000000.0 : 0,
		last > first ? (frames - 1) * 1000000.0 / (last - first) : 0,
		cpu, elapsed > 0 ? 100 * cpu / elapsed : 0);
	fflush(stdout);
}

int main(int argc, char **argv)
{
	struct measurement measurement = { 0 };
	GstElement *pipeline = NULL, *sink = NULL;
	GstBus *bus = NULL;
	GError *error = NULL;
	guint64 seconds;
	gint64 started = 0, next_report, first, last, stop_sent = 0;
	double cpu_start = 0;
	gboolean sync, success = FALSE;
	char *end;
	int result = 1;

	if (argc != 4) {
		g_printerr("Usage: %s 'pipeline ! fakesink name=measure' seconds sync(0|1)\n", argv[0]);
		return 2;
	}
	seconds = g_ascii_strtoull(argv[2], &end, 10);
	if (*end || !seconds || seconds > 600 ||
	    (g_strcmp0(argv[3], "0") && g_strcmp0(argv[3], "1")))
		return 2;
	sync = !g_strcmp0(argv[3], "1");
	g_mutex_init(&measurement.lock);
	gst_init(NULL, NULL);
	pipeline = gst_parse_launch(argv[1], &error);
	if (error || !pipeline) {
		g_printerr("Pipeline: %s\n", error ? error->message : "missing pipeline");
		goto done;
	}
	sink = gst_bin_get_by_name(GST_BIN(pipeline), "measure");
	if (!sink || !GST_IS_BASE_SINK(sink) ||
	    g_strcmp0(gst_plugin_feature_get_name(GST_PLUGIN_FEATURE(gst_element_get_factory(sink))), "fakesink")) {
		g_printerr("Pipeline must end in fakesink name=measure\n");
		goto done;
	}
	/* The playback measurement explicitly counts buffers more than 20 ms late.
	 * Throughput mode does not wait on a clock or drop late buffers. */
	g_object_set(sink, "sync", sync, "qos", TRUE, "signal-handoffs", TRUE,
		     "max-lateness", sync ? (gint64)(20 * GST_MSECOND) : (gint64)-1, NULL);
	g_signal_connect(sink, "handoff", G_CALLBACK(handoff), &measurement);
	bus = gst_element_get_bus(pipeline);
	started = next_report = g_get_monotonic_time();
	cpu_start = cpu_seconds();
	if (gst_element_set_state(pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE)
		goto done;
	for (;;) {
		GstMessage *message = gst_bus_timed_pop_filtered(bus, 100 * GST_MSECOND,
							       GST_MESSAGE_ERROR | GST_MESSAGE_EOS);
		gint64 now = g_get_monotonic_time();

		g_mutex_lock(&measurement.lock);
		first = measurement.first;
		last = measurement.last;
		g_mutex_unlock(&measurement.lock);
		if (message) {
			if (GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR) {
				gchar *debug = NULL;

				gst_message_parse_error(message, &error, &debug);
				g_printerr("Decode: %s (%s)\n", error->message, debug ? debug : "");
				g_free(debug);
			} else {
				/* Early EOS is not a completed duration measurement. */
				success = stop_sent && first && last >= stop_sent - G_USEC_PER_SEC;
			}
			gst_message_unref(message);
			break;
		}
		if (now >= next_report) {
			report(sink, &measurement, started, cpu_start, FALSE, FALSE);
			next_report = now + G_USEC_PER_SEC;
		}
		if (now - (last ? last : started) > 10 * G_USEC_PER_SEC ||
		    (stop_sent && now - stop_sent > 10 * G_USEC_PER_SEC)) {
			g_printerr("Decoder stalled or failed to drain\n");
			break;
		}
		if (!stop_sent && first && now - first >= (gint64)seconds * G_USEC_PER_SEC) {
			stop_sent = now;
			if (!gst_element_send_event(pipeline, gst_event_new_eos()))
				break;
		}
	}
	report(sink, &measurement, started, cpu_start, TRUE, success);
	result = success ? 0 : 1;
done:
	if (pipeline)
		gst_element_set_state(pipeline, GST_STATE_NULL);
	if (bus)
		gst_object_unref(bus);
	if (sink)
		gst_object_unref(sink);
	if (pipeline)
		gst_object_unref(pipeline);
	g_clear_error(&error);
	g_mutex_clear(&measurement.lock);
	return result;
}
