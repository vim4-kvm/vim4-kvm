/* SPDX-License-Identifier: MIT
 * Native, exclusive VIM4 capture/encoder benchmark. See docs/driver-benchmark.md.
 * No pixel reads, parser, network or recording in the measured pipeline.
 */
#define _POSIX_C_SOURCE 200809L
#include <gst/app/gstappsink.h>
#include <gst/app/gstappsrc.h>
#include <gst/allocators/gstdmabuf.h>
#include <gst/video/video.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/file.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

typedef struct {
    guint64 total, idle, vpu_irqs, capture_irqs, jpeg_irqs;
    gint64 at_us, process_us, cma_kib, available_kib;
} Accounting;

typedef struct {
    guint index;
    gint64 source_us, encoder_us;
} Frame;

typedef struct {
    GstElement *pipeline, *encoder_source;
    GMutex lock;
    GHashTable *pending;
    GArray *bridge_ms, *encoder_ms, *total_ms, *gaps_ms;
    guint warmup, measured, raw_count, output_count, keyframes;
    guint width, height;
    guint64 bytes, largest_frame, first_pts, last_pts;
    gboolean capture_only;
    gchar *error, *raw_caps, *encoded_caps;
    Accounting before, start, end, after;
} Bench;

static gint64 memory_kib(const gchar *key)
{
    gchar *contents = NULL;
    if (!g_file_get_contents("/proc/meminfo", &contents, NULL, NULL))
        return -1;
    gchar *line = strstr(contents, key);
    gint64 result = line ? g_ascii_strtoll(line + strlen(key), NULL, 10) : -1;
    g_free(contents);
    return result;
}

static guint64 interrupt_count(const gchar *text, const gchar *name)
{
    guint64 total = 0;
    gchar **lines = g_strsplit(text, "\n", -1);
    for (guint i = 0; lines[i]; i++) {
        if (!strstr(lines[i], name))
            continue;
        gchar *cursor = strchr(lines[i], ':');
        if (!cursor)
            continue;
        cursor++;
        for (;;) {
            while (g_ascii_isspace(*cursor)) cursor++;
            if (!g_ascii_isdigit(*cursor)) break;
            gchar *end;
            total += g_ascii_strtoull(cursor, &end, 10);
            cursor = end;
        }
    }
    g_strfreev(lines);
    return total;
}

static Accounting accounting(void)
{
    Accounting result = {0};
    gchar *text = NULL;
    if (g_file_get_contents("/proc/stat", &text, NULL, NULL)) {
        guint64 ticks[8] = {0};
        if (sscanf(text, "cpu %" G_GUINT64_FORMAT " %" G_GUINT64_FORMAT
                   " %" G_GUINT64_FORMAT " %" G_GUINT64_FORMAT " %" G_GUINT64_FORMAT
                   " %" G_GUINT64_FORMAT " %" G_GUINT64_FORMAT " %" G_GUINT64_FORMAT,
                   &ticks[0], &ticks[1], &ticks[2], &ticks[3], &ticks[4], &ticks[5],
                   &ticks[6], &ticks[7]) == 8) {
            for (guint i = 0; i < 8; i++) result.total += ticks[i];
            result.idle = ticks[3] + ticks[4];
        }
        g_free(text);
    }
    if (g_file_get_contents("/proc/interrupts", &text, NULL, NULL)) {
        result.vpu_irqs = interrupt_count(text, "vpu_irq");
        result.capture_irqs = interrupt_count(text, "video-capture");
        result.jpeg_irqs = interrupt_count(text, "t7-jpeg");
        g_free(text);
    }
    struct rusage usage;
    getrusage(RUSAGE_SELF, &usage);
    result.process_us = (gint64)(usage.ru_utime.tv_sec + usage.ru_stime.tv_sec) * G_USEC_PER_SEC
                        + usage.ru_utime.tv_usec + usage.ru_stime.tv_usec;
    result.cma_kib = memory_kib("CmaFree:");
    result.available_kib = memory_kib("MemAvailable:");
    result.at_us = g_get_monotonic_time();
    return result;
}

static void fail_locked(Bench *bench, const gchar *message)
{
    if (bench->error) return;
    bench->error = g_strdup(message);
    GError *error = g_error_new_literal(GST_CORE_ERROR, GST_CORE_ERROR_FAILED, message);
    gst_element_post_message(bench->pipeline,
                             gst_message_new_error(GST_OBJECT(bench->pipeline), error, NULL));
    g_error_free(error);
}

static gchar *pad_caps(GstPad *pad)
{
    GstCaps *caps = gst_pad_get_current_caps(pad);
    gchar *text = caps ? gst_caps_to_string(caps) : g_strdup("");
    if (caps) gst_caps_unref(caps);
    return text;
}

static void finish_frame(Bench *bench, GstBuffer *buffer, const Frame *frame, gint64 now)
{
    guint ordinal = ++bench->output_count;
    if (ordinal == bench->warmup) bench->start = accounting();
    if (ordinal > bench->warmup) {
        if (ordinal > bench->warmup + 1 && GST_BUFFER_PTS(buffer) <= bench->last_pts) {
            fail_locked(bench, "output PTS did not advance");
            return;
        }
        if (ordinal == bench->warmup + 1) bench->first_pts = GST_BUFFER_PTS(buffer);
        else {
            gdouble gap = (GST_BUFFER_PTS(buffer) - bench->last_pts) / 1e6;
            g_array_append_val(bench->gaps_ms, gap);
        }
        bench->last_pts = GST_BUFFER_PTS(buffer);
        if (!bench->capture_only) {
            gdouble bridge = (frame->encoder_us - frame->source_us) / 1000.0;
            gdouble encoder = (now - frame->encoder_us) / 1000.0;
            gdouble total = (now - frame->source_us) / 1000.0;
            g_array_append_val(bench->bridge_ms, bridge);
            g_array_append_val(bench->encoder_ms, encoder);
            g_array_append_val(bench->total_ms, total);
            guint64 size = gst_buffer_get_size(buffer);
            bench->bytes += size;
            bench->largest_frame = MAX(bench->largest_frame, size);
            if (!GST_BUFFER_FLAG_IS_SET(buffer, GST_BUFFER_FLAG_DELTA_UNIT)) bench->keyframes++;
        }
    }
    if (ordinal == bench->warmup + bench->measured) bench->end = accounting();
}

static GstPadProbeReturn raw_probe(GstPad *pad, GstPadProbeInfo *info, gpointer data)
{
    Bench *bench = data;
    GstBuffer *buffer = GST_PAD_PROBE_INFO_BUFFER(info);
    gint64 now = g_get_monotonic_time();
    g_mutex_lock(&bench->lock);
    bench->raw_count++;
    if (!bench->raw_caps) bench->raw_caps = pad_caps(pad);
    if (!GST_BUFFER_PTS_IS_VALID(buffer)) fail_locked(bench, "missing raw PTS");
    else if (bench->capture_only) finish_frame(bench, buffer, NULL, now);
    else if (g_hash_table_size(bench->pending) >= 64 ||
             g_hash_table_contains(bench->pending, &GST_BUFFER_PTS(buffer)))
        fail_locked(bench, "duplicate PTS or more than 64 pending frames");
    else {
        guint64 *pts = g_new(guint64, 1);
        *pts = GST_BUFFER_PTS(buffer);
        Frame *frame = g_new0(Frame, 1);
        frame->index = bench->raw_count;
        frame->source_us = now;
        g_hash_table_insert(bench->pending, pts, frame);
    }
    g_mutex_unlock(&bench->lock);
    return GST_PAD_PROBE_OK;
}

static GstPadProbeReturn encoder_probe(GstPad *pad, GstPadProbeInfo *info, gpointer data)
{
    Bench *bench = data;
    GstBuffer *buffer = GST_PAD_PROBE_INFO_BUFFER(info);
    gint64 now = g_get_monotonic_time();
    g_mutex_lock(&bench->lock);
    Frame *frame = g_hash_table_lookup(bench->pending, &GST_BUFFER_PTS(buffer));
    if (!frame) fail_locked(bench, "encoder input PTS has no source frame");
    else if (frame->encoder_us) fail_locked(bench, "duplicate encoder input PTS");
    else frame->encoder_us = now;
    g_mutex_unlock(&bench->lock);
    (void)pad;
    return GST_PAD_PROBE_OK;
}

static GstPadProbeReturn output_probe(GstPad *pad, GstPadProbeInfo *info, gpointer data)
{
    Bench *bench = data;
    GstBuffer *buffer = GST_PAD_PROBE_INFO_BUFFER(info);
    gint64 now = g_get_monotonic_time();
    g_mutex_lock(&bench->lock);
    Frame *frame = g_hash_table_lookup(bench->pending, &GST_BUFFER_PTS(buffer));
    if (!bench->encoded_caps) bench->encoded_caps = pad_caps(pad);
    if (!frame || !frame->encoder_us) fail_locked(bench, "encoded PTS has no matching input");
    else {
        if (frame->index != bench->output_count + 1)
            fail_locked(bench, "encoder dropped or reordered an input frame");
        finish_frame(bench, buffer, frame, now);
        g_hash_table_remove(bench->pending, &GST_BUFFER_PTS(buffer));
    }
    g_mutex_unlock(&bench->lock);
    return GST_PAD_PROBE_OK;
}

static GstFlowReturn forward_sample(GstAppSink *sink, gpointer data)
{
    Bench *bench = data;
    GstSample *sample = gst_app_sink_pull_sample(sink);
    if (!sample) return GST_FLOW_EOS;
    GstBuffer *original = gst_sample_get_buffer(sample);
    GstMemory *memory = gst_buffer_n_memory(original) == 1 ? gst_buffer_peek_memory(original, 0) : NULL;
    guint luma = bench->width * bench->height;
    guint aligned_luma = bench->width * GST_ROUND_UP_16(bench->height);
    GstBuffer *view = NULL;
    GstFlowReturn result = GST_FLOW_ERROR;
    GstMemory *padded = NULL;
    if (!memory || !gst_is_dmabuf_memory(memory)) goto failed;
    if (gst_buffer_get_size(original) != luma * 3 / 2) goto failed;
    if (luma != aligned_luma) {
        gint original_fd = gst_dmabuf_memory_get_fd(memory);
        struct stat status;
        if (fstat(original_fd, &status) || status.st_size < (gint64)luma + aligned_luma / 2)
            goto failed;
        gint owned_fd = dup(original_fd);
        if (owned_fd < 0) goto failed;
        GstAllocator *allocator = gst_dmabuf_allocator_new();
        padded = gst_dmabuf_allocator_alloc(allocator, owned_fd, status.st_size);
        gst_object_unref(allocator);
        if (!padded) { close(owned_fd); goto failed; }
        memory = padded;
    }
    view = gst_buffer_new();
    GstMemory *y = gst_memory_share(memory, 0, aligned_luma);
    GstMemory *uv = gst_memory_share(memory, luma, aligned_luma / 2);
    if (!y || !uv) {
        if (y) gst_memory_unref(y);
        if (uv) gst_memory_unref(uv);
        goto failed;
    }
    gst_buffer_append_memory(view, y);
    gst_buffer_append_memory(view, uv);
    /* Keep the capture-pool buffer leased until V4L2 releases encoder input. */
    gst_buffer_add_parent_buffer_meta(view, original);
    gsize offsets[GST_VIDEO_MAX_PLANES] = {0, aligned_luma};
    gint strides[GST_VIDEO_MAX_PLANES] = {(gint)bench->width, (gint)bench->width};
    gst_buffer_add_video_meta_full(view, GST_VIDEO_FRAME_FLAG_NONE, GST_VIDEO_FORMAT_NV12,
                                  bench->width, bench->height, 2, offsets, strides);
    GST_BUFFER_PTS(view) = GST_BUFFER_PTS(original);
    GST_BUFFER_DTS(view) = GST_BUFFER_DTS(original);
    GST_BUFFER_DURATION(view) = GST_BUFFER_DURATION(original);
    result = gst_app_src_push_buffer(GST_APP_SRC(bench->encoder_source), view);
    view = NULL; /* push_buffer takes ownership, including on failure. */
    goto done;
failed:
    g_mutex_lock(&bench->lock);
    fail_locked(bench, "cannot construct leased NV12 DMA plane views");
    g_mutex_unlock(&bench->lock);
done:
    if (view) gst_buffer_unref(view);
    if (padded) gst_memory_unref(padded);
    gst_sample_unref(sample);
    return result;
}

static void forward_eos(GstAppSink *sink, gpointer data)
{
    Bench *bench = data;
    gst_app_src_end_of_stream(GST_APP_SRC(bench->encoder_source));
    (void)sink;
}

static void add_probe(GstElement *element, const gchar *pad_name, GstPadProbeCallback callback, Bench *bench)
{
    GstPad *pad = gst_element_get_static_pad(element, pad_name);
    gst_pad_add_probe(pad, GST_PAD_PROBE_TYPE_BUFFER, callback, bench, NULL);
    gst_object_unref(pad);
}

static gint compare_double(gconstpointer a, gconstpointer b)
{
    gdouble x = *(const gdouble *)a, y = *(const gdouble *)b;
    return (x > y) - (x < y);
}

static void append_distribution(GString *json, const gchar *name, GArray *values)
{
    g_string_append_printf(json, ",\n  \"%s\": ", name);
    if (!values->len) { g_string_append(json, "null"); return; }
    g_array_sort(values, compare_double);
    g_string_append_printf(json, "{\"count\": %u, \"p50\": %.6f, \"p95\": %.6f, \"p99\": %.6f, \"max\": %.6f}",
                           values->len, g_array_index(values, gdouble, (values->len - 1) * 50 / 100),
                           g_array_index(values, gdouble, (values->len - 1) * 95 / 100),
                           g_array_index(values, gdouble, (values->len - 1) * 99 / 100),
                           g_array_index(values, gdouble, values->len - 1));
}

static void append_string(GString *json, const gchar *key, const gchar *value)
{
    g_string_append_printf(json, ",\n  \"%s\": \"", key);
    for (const guchar *p = (const guchar *)(value ? value : ""); *p; p++) {
        if (*p < 32) g_string_append_printf(json, "\\u%04x", *p);
        else {
            if (*p == '"' || *p == '\\') g_string_append_c(json, '\\');
            g_string_append_c(json, *p);
        }
    }
    g_string_append_c(json, '"');
}

static void append_file(GString *json, const gchar *key, const gchar *path)
{
    gchar *text = NULL;
    if (g_file_get_contents(path, &text, NULL, NULL)) g_strchomp(text);
    append_string(json, key, text);
    g_free(text);
}

#ifndef VIM4_BENCH_TEST
static gboolean video_device_is(const gchar *device, const gchar *expected)
{
    gchar *basename = g_path_get_basename(device);
    gchar *path = g_strdup_printf("/sys/class/video4linux/%s/name", basename);
    gchar *name = NULL;
    gboolean matches = g_file_get_contents(path, &name, NULL, NULL) &&
                       !strcmp(g_strchomp(name), expected);
    g_free(name); g_free(path); g_free(basename);
    return matches;
}

int main(int argc, char **argv)
{
    gchar *backend = NULL, *codec = NULL, *output = NULL, *device = NULL, *save_bitstream = NULL;
    gint frames = 1800, warmup = 120, bitrate = 20000000, gop = 60, width = 3840, height = 2160;
    gint timeout = 90, quality = 80, fps = 60;
    gboolean exclusive = FALSE, secondary = FALSE;
    GOptionEntry options[] = {
        {"backend", 0, 0, G_OPTION_ARG_STRING, &backend, "edge or stock", "BACKEND"},
        {"codec", 0, 0, G_OPTION_ARG_STRING, &codec, "capture, h264, h265 or jpeg", "CODEC"},
        {"quality", 0, 0, G_OPTION_ARG_INT, &quality, "Hardware JPEG quality", "1..100"},
        {"output", 0, 0, G_OPTION_ARG_FILENAME, &output, "New JSON report", "PATH"},
        {"save-bitstream", 0, 0, G_OPTION_ARG_FILENAME, &save_bitstream, "Separate correctness run; invalidates CPU comparison", "NEW_PATH"},
        {"device", 0, 0, G_OPTION_ARG_FILENAME, &device, "Edge capture device", "PATH"},
        {"frames", 0, 0, G_OPTION_ARG_INT, &frames, "Measured frames", "N"},
        {"warmup", 0, 0, G_OPTION_ARG_INT, &warmup, "Excluded initial frames", "N"},
        {"bitrate", 0, 0, G_OPTION_ARG_INT, &bitrate, "Bits per second", "BPS"},
        {"gop", 0, 0, G_OPTION_ARG_INT, &gop, "GOP length; intra refresh disabled", "N"},
        {"width", 0, 0, G_OPTION_ARG_INT, &width, "1920 or 3840", "PIXELS"},
        {"height", 0, 0, G_OPTION_ARG_INT, &height, "1080 or 2160", "PIXELS"},
        {"fps", 0, 0, G_OPTION_ARG_INT, &fps, "Negotiated capture and encoder rate", "FPS"},
        {"secondary", 0, 0, G_OPTION_ARG_NONE, &secondary, "Stock native-HDR VDIN1 HDMI capture", NULL},
        {"timeout", 0, 0, G_OPTION_ARG_INT, &timeout, "Pipeline deadline in seconds", "SECONDS"},
        {"exclusive", 0, 0, G_OPTION_ARG_NONE, &exclusive, "Caller has exclusive use of capture/encoder", NULL},
        {NULL, 0, 0, 0, NULL, NULL, NULL}
    };
    GError *error = NULL;
    GOptionContext *context = g_option_context_new("- VIM4 driver benchmark (no recording)");
    g_option_context_add_main_entries(context, options, NULL);
    if (!g_option_context_parse(context, &argc, &argv, &error)) {
        g_printerr("%s\n", error->message); return 1;
    }
    if (!exclusive || !backend || !codec || !output ||
        (strcmp(backend, "edge") && strcmp(backend, "stock")) ||
        (strcmp(codec, "capture") && strcmp(codec, "h264") && strcmp(codec, "h265") && strcmp(codec, "jpeg")) ||
        quality < 1 || quality > 100 ||
        frames < 2 || frames > 100000 || warmup < 1 || warmup > 10000 ||
        bitrate < 1000000 || bitrate > 60000000 || gop < 1 || gop > 1000 ||
        timeout < 1 || (save_bitstream && codec && !strcmp(codec, "capture")) ||
        fps < 1 || fps > 120 || (secondary && strcmp(backend, "stock")) ||
        (fps > 60 && (!secondary || width != 1920 || height != 1080 || !strcmp(codec, "jpeg"))) ||
        !((width == 3840 && height == 2160) || (width == 1920 && height == 1080))) {
        g_printerr("Require --exclusive --backend=edge|stock --codec=capture|h264|h265|jpeg --output=NEW.json and valid limits\n");
        return 1;
    }
    /* A read-only flock also permits stock's unprivileged application user.
     * Avoid O_CREAT when opening another user's existing file in sticky /tmp. */
    int lock_fd = open("/tmp/vim4-driver-bench.lock", O_RDONLY | O_NOFOLLOW);
    if (lock_fd < 0 && errno == ENOENT) {
        lock_fd = open("/tmp/vim4-driver-bench.lock", O_RDONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
        if (lock_fd < 0 && errno == EEXIST)
            lock_fd = open("/tmp/vim4-driver-bench.lock", O_RDONLY | O_NOFOLLOW);
    }
    if (lock_fd < 0 || flock(lock_fd, LOCK_EX | LOCK_NB)) {
        g_printerr("Cannot acquire native benchmark lock: %s\n", g_strerror(errno)); return 1;
    }
    int report_fd = open(output, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (report_fd < 0) { g_printerr("Cannot create new report: %s\n", g_strerror(errno)); return 1; }
    gboolean edge = !strcmp(backend, "edge");
    gboolean capture_only = !strcmp(codec, "capture");
    gboolean jpeg = !strcmp(codec, "jpeg");
    if (save_bitstream) {
        int fd = open(save_bitstream, O_WRONLY | O_CREAT | O_EXCL, 0644);
        if (fd < 0) { g_printerr("Cannot reserve new bitstream: %s\n", g_strerror(errno)); return 1; }
        close(fd);
    }
    if (!device) device = g_strdup("/dev/video0");
    struct utsname kernel;
    uname(&kernel);
    if ((edge && !g_str_has_prefix(kernel.release, "7.")) ||
        (!edge && !g_str_has_prefix(kernel.release, "5.15."))) {
        g_printerr("Backend does not match running kernel %s\n", kernel.release); return 1;
    }
    gst_init(NULL, NULL);
    Bench bench = {.warmup = (guint)warmup, .measured = (guint)frames,
                   .width = (guint)width, .height = (guint)height, .capture_only = capture_only};
    g_mutex_init(&bench.lock);
    bench.pending = g_hash_table_new_full(g_int64_hash, g_int64_equal, g_free, g_free);
    bench.bridge_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    bench.encoder_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    bench.total_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    bench.gaps_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    gchar *source = edge ? g_strdup("v4l2src name=source io-mode=dmabuf") :
        g_strdup(secondary ? "vim4vdin1src name=source" : "vfmcapsrc name=source");
    gchar *raw_caps = g_strdup_printf("video/x-raw,format=%s,width=%d,height=%d,framerate=%d/1",
                                      edge ? "NV12" : "NV21", width, height, fps);
    gchar *encoding = NULL;
    if (capture_only) encoding = g_strdup("");
    else if (jpeg) encoding = g_strdup_printf("vim4jpegenc name=encoder quality=%d ! ", quality);
    else if (edge) encoding = g_strdup_printf(
        "appsink name=bridge emit-signals=true sync=false async=false max-buffers=1 "
        "appsrc name=encoder_source is-live=true format=time block=true max-buffers=2 "
        "caps=\"video/x-raw,format=NV12,width=%d,height=%d,framerate=%d/1,colorimetry=bt709,"
        "interlace-mode=progressive,pixel-aspect-ratio=1/1\" ! "
        "v4l2%senc name=encoder output-io-mode=dmabuf-import ! "
        "video/x-%s,profile=%s,level=(string)%s ! ",
        width, height, fps, codec, codec, !strcmp(codec, "h264") ? "high" : "main",
        "5.1");
    else encoding = g_strdup_printf(
        "amlvenc name=encoder bitrate=%d gop=%d framerate=%d i-qp-min=-1 qp-max=-1 intra-refresh-rows=0 ! "
        "video/x-%s ! ", bitrate / 1000, gop, fps, codec);
    gchar *description = g_strdup_printf("%s ! %s ! %s%s name=output sync=false async=false",
                                         source, raw_caps, encoding, save_bitstream ? "filesink" : "fakesink");
    bench.pipeline = gst_parse_launch(description, &error);
    if (error || !bench.pipeline) {
        g_printerr("Pipeline: %s\n", error ? error->message : "no pipeline"); return 1;
    }
    if (save_bitstream) {
        GstElement *file_sink = gst_bin_get_by_name(GST_BIN(bench.pipeline), "output");
        g_object_set(file_sink, "location", save_bitstream, NULL);
        gst_object_unref(file_sink);
    }
    GstElement *capture = gst_bin_get_by_name(GST_BIN(bench.pipeline), "source");
    if (edge) {
        if (!video_device_is(device, "t7-vdin-test")) {
            g_printerr("Capture must be t7-vdin-test\n"); return 1;
        }
        g_object_set(capture, "device", device, NULL);
    }
    g_object_set(capture, "num-buffers", frames + warmup, NULL);
    add_probe(capture, "src", raw_probe, &bench);
    if (!capture_only) {
        GstElement *encoder = gst_bin_get_by_name(GST_BIN(bench.pipeline), "encoder");
        if (edge && !jpeg) {
            gchar *encoder_device = NULL;
            g_object_get(encoder, "device", &encoder_device, NULL);
            if (!encoder_device || !video_device_is(encoder_device, "C&M Wave5 VPU encoder")) {
                g_printerr("Encoder must be C&M Wave5 VPU encoder\n"); return 1;
            }
            g_free(encoder_device);
            GstStructure *controls = gst_structure_new("controls", "video_bitrate", G_TYPE_INT, bitrate,
                "video_gop_size", G_TYPE_INT, gop, "frame_level_rate_control_enable", G_TYPE_INT, 1,
                "h264_mb_level_rate_control", G_TYPE_INT, 1, NULL);
            if (!strcmp(codec, "h265")) gst_structure_set(controls, "hevc_level", G_TYPE_INT, 8, NULL);
            g_object_set(encoder, "extra-controls", controls, NULL);
            gst_structure_free(controls);
            bench.encoder_source = gst_bin_get_by_name(GST_BIN(bench.pipeline), "encoder_source");
            GstElement *bridge = gst_bin_get_by_name(GST_BIN(bench.pipeline), "bridge");
            g_signal_connect(bridge, "new-sample", G_CALLBACK(forward_sample), &bench);
            g_signal_connect(bridge, "eos", G_CALLBACK(forward_eos), &bench);
            gst_object_unref(bridge);
        }
        add_probe(encoder, "sink", encoder_probe, &bench);
        add_probe(encoder, "src", output_probe, &bench);
        gst_object_unref(encoder);
    }
    gst_object_unref(capture);
    GString *json = g_string_new("{\n  \"schema\": 1");
    append_string(json, "backend", backend); append_string(json, "codec", codec);
    append_string(json, "kernel_release", kernel.release); append_string(json, "kernel_build", kernel.version);
    append_string(json, "gstreamer", gst_version_string()); append_string(json, "pipeline", description);
    append_string(json, "measurement_kind", save_bitstream ? "bitstream-verification-with-file-io" : "no-payload-read");
    append_string(json, "saved_bitstream", save_bitstream);
    append_file(json, "cpu0_governor", "/sys/devices/system/cpu/cpufreq/policy0/scaling_governor");
    append_file(json, "cpu4_governor", "/sys/devices/system/cpu/cpufreq/policy4/scaling_governor");
    append_file(json, "cpu0_max_khz", "/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq");
    append_file(json, "cpu4_max_khz", "/sys/devices/system/cpu/cpufreq/policy4/scaling_max_freq");
    append_file(json, "cpu0_current_khz", "/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq");
    append_file(json, "cpu4_current_khz", "/sys/devices/system/cpu/cpufreq/policy4/scaling_cur_freq");
    if (edge) append_file(json, "direct_dma", "/sys/module/t7_vdin_test/parameters/direct_dma");
    append_file(json, "wave_a_hz", "/sys/kernel/debug/clk/wave_a/clk_rate");
    append_file(json, "wave_b_hz", "/sys/kernel/debug/clk/wave_b/clk_rate");
    append_file(json, "wave_c_hz", "/sys/kernel/debug/clk/wave_c/clk_rate");
    if (jpeg) {
        append_file(json, "hcodec_hz", "/sys/kernel/debug/clk/hcodec/clk_rate");
        g_string_append_printf(json, ",\n  \"jpeg_quality\": %d", quality);
    }
    append_file(json, "thermal0_millicelsius", "/sys/class/thermal/thermal_zone0/temp");
    append_file(json, "taint_before", "/proc/sys/kernel/tainted");
    g_string_append_printf(json, ",\n  \"width\": %d,\n  \"height\": %d,\n  \"requested_bitrate_bps\": %d,"
                           "\n  \"gop\": %d,\n  \"intra_refresh_rows\": 0", width, height,
                           jpeg ? 0 : bitrate, jpeg ? 0 : gop);
    bench.before = accounting();
    gboolean success = gst_element_set_state(bench.pipeline, GST_STATE_PLAYING) != GST_STATE_CHANGE_FAILURE;
    GstBus *bus = gst_element_get_bus(bench.pipeline);
    GstMessage *message = success ? gst_bus_timed_pop_filtered(bus, (guint64)timeout * GST_SECOND,
                                               GST_MESSAGE_ERROR | GST_MESSAGE_EOS) : NULL;
    if (!message) { success = FALSE; g_printerr("Pipeline failed to start or timed out\n"); }
    else if (GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR) {
        gchar *debug = NULL;
        gst_message_parse_error(message, &error, &debug);
        g_printerr("Pipeline error: %s (%s)\n", error->message, debug ? debug : "");
        g_mutex_lock(&bench.lock);
        if (!bench.error) bench.error = g_strdup(error->message);
        g_mutex_unlock(&bench.lock);
        success = FALSE; g_clear_error(&error); g_free(debug);
    }
    if (message) gst_message_unref(message);
    /* Flush both halves before NULL, including when input negotiation failed. */
    gst_element_send_event(bench.pipeline, gst_event_new_flush_start());
    gst_element_set_state(bench.pipeline, GST_STATE_NULL);
    if (gst_element_get_state(bench.pipeline, NULL, NULL, 5 * GST_SECOND) != GST_STATE_CHANGE_SUCCESS)
        success = FALSE;
    gst_object_unref(bus);
    if (bench.encoder_source) gst_object_unref(bench.encoder_source);
    gst_object_unref(bench.pipeline);
    bench.after = accounting();
    append_file(json, "taint_after", "/proc/sys/kernel/tainted");
    append_file(json, "thermal0_after_millicelsius", "/sys/class/thermal/thermal_zone0/temp");
    success = success && !bench.error && bench.raw_count == (guint)(frames + warmup) &&
              bench.output_count == bench.raw_count && !g_hash_table_size(bench.pending) &&
              bench.end.total > bench.start.total && bench.end.at_us > bench.start.at_us;
    gdouble elapsed = (bench.end.at_us - bench.start.at_us) / 1e6;
    gdouble busy = bench.end.total > bench.start.total ?
        100.0 * (1.0 - (gdouble)(bench.end.idle - bench.start.idle) / (bench.end.total - bench.start.total)) : 0;
    append_string(json, "error", bench.error);
    append_string(json, "raw_caps", bench.raw_caps); append_string(json, "encoded_caps", bench.encoded_caps);
    g_string_append_printf(json, ",\n  \"success\": %s,\n  \"warmup_frames\": %d,\n  \"measured_frames\": %d,"
        "\n  \"raw_frames\": %u,\n  \"output_frames\": %u,\n  \"measurement_seconds\": %.6f,"
        "\n  \"whole_board_cpu_percent\": %.6f,\n  \"process_one_core_cpu_percent\": %.6f,"
        "\n  \"steady_fps\": %.6f,\n  \"encoded_payload_bps\": %.0f,\n  \"largest_frame_bytes\": %" G_GUINT64_FORMAT
        ",\n  \"keyframes\": %u,\n  \"vpu_irqs\": %" G_GUINT64_FORMAT ",\n  \"capture_irqs\": %" G_GUINT64_FORMAT
        ",\n  \"cma_kib_before\": %" G_GINT64_FORMAT ",\n  \"cma_kib_streaming\": %" G_GINT64_FORMAT
        ",\n  \"cma_kib_after\": %" G_GINT64_FORMAT ",\n  \"available_kib_streaming\": %" G_GINT64_FORMAT,
        success ? "true" : "false", warmup, frames, bench.raw_count, bench.output_count, elapsed, busy,
        elapsed > 0 ? (bench.end.process_us - bench.start.process_us) / (elapsed * 10000) : 0,
        bench.last_pts > bench.first_pts ? (frames - 1) * 1e9 / (bench.last_pts - bench.first_pts) : 0,
        elapsed > 0 ? bench.bytes * 8 / elapsed : 0, bench.largest_frame, bench.keyframes,
        bench.end.vpu_irqs - bench.start.vpu_irqs, bench.end.capture_irqs - bench.start.capture_irqs,
        bench.before.cma_kib, bench.start.cma_kib, bench.after.cma_kib, bench.start.available_kib);
    append_distribution(json, "source_to_encoder_sink_ms", bench.bridge_ms);
    append_distribution(json, "encoder_sink_to_src_ms", bench.encoder_ms);
    append_distribution(json, "source_to_encoded_ms", bench.total_ms);
    append_distribution(json, "capture_pts_gap_ms", bench.gaps_ms);
    if (jpeg) g_string_append_printf(json, ",\n  \"jpeg_irqs\": %" G_GUINT64_FORMAT,
                                   bench.end.jpeg_irqs - bench.start.jpeg_irqs);
    g_string_append(json, "\n}\n");
    FILE *report = fdopen(report_fd, "w");
    if (!report) return 1;
    gboolean written = fwrite(json->str, 1, json->len, report) == json->len;
    if (fclose(report)) written = FALSE;
    g_print("%s\n", success && written ? "PASS" : "FAIL");
    g_string_free(json, TRUE);
    g_hash_table_unref(bench.pending);
    g_array_unref(bench.bridge_ms); g_array_unref(bench.encoder_ms);
    g_array_unref(bench.total_ms); g_array_unref(bench.gaps_ms);
    g_free(bench.raw_caps); g_free(bench.encoded_caps); g_free(bench.error);
    g_mutex_clear(&bench.lock);
    g_free(source); g_free(raw_caps); g_free(encoding); g_free(description);
    g_option_context_free(context);
    g_free(backend); g_free(codec); g_free(output); g_free(device); g_free(save_bitstream);
    close(lock_fd);
    return success && written ? 0 : 1;
}
#endif
