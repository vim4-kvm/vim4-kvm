/* Native regression tests; compile with the same pkg-config arguments as the tool. */
#define VIM4_BENCH_TEST
#include "../tools/vim4-driver-bench.c"

static void fixture(Bench *bench, gboolean capture_only)
{
    *bench = (Bench){.warmup = 2, .measured = 4, .capture_only = capture_only};
    bench->pipeline = gst_pipeline_new(NULL);
    bench->pending = g_hash_table_new_full(g_int64_hash, g_int64_equal, g_free, g_free);
    bench->bridge_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    bench->encoder_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    bench->total_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    bench->gaps_ms = g_array_new(FALSE, FALSE, sizeof(gdouble));
    g_mutex_init(&bench->lock);
}

static void clear_fixture(Bench *bench)
{
    gst_object_unref(bench->pipeline);
    g_hash_table_unref(bench->pending);
    g_array_unref(bench->bridge_ms); g_array_unref(bench->encoder_ms);
    g_array_unref(bench->total_ms); g_array_unref(bench->gaps_ms);
    g_free(bench->error); g_free(bench->raw_caps); g_free(bench->encoded_caps);
    g_mutex_clear(&bench->lock);
}

static void timing_matches_frames(void)
{
    for (guint capture_only = 0; capture_only < 2; capture_only++) {
        Bench bench;
        fixture(&bench, capture_only);
        GstPad *pad = gst_pad_new("test", GST_PAD_SRC);
        for (guint i = 0; i < 6; i++) {
            GstBuffer *buffer = gst_buffer_new_allocate(NULL, 10, NULL);
            GST_BUFFER_PTS(buffer) = i * GST_SECOND / 60;
            GstPadProbeInfo info = {.type = GST_PAD_PROBE_TYPE_BUFFER, .data = buffer};
            raw_probe(pad, &info, &bench);
            if (!capture_only) {
                encoder_probe(pad, &info, &bench);
                output_probe(pad, &info, &bench);
            }
            gst_buffer_unref(buffer);
        }
        g_assert_null(bench.error);
        g_assert_cmpuint(bench.raw_count, ==, 6);
        g_assert_cmpuint(bench.output_count, ==, 6);
        g_assert_cmpuint(g_hash_table_size(bench.pending), ==, 0);
        g_assert_cmpuint(bench.gaps_ms->len, ==, 3);
        g_assert_cmpuint(bench.total_ms->len, ==, capture_only ? 0 : 4);
        g_assert_cmpuint(bench.first_pts, ==, 2 * GST_SECOND / 60);
        g_assert_cmpuint(bench.last_pts, ==, 5 * GST_SECOND / 60);
        g_assert_cmpint(bench.start.at_us, >, 0);
        g_assert_cmpint(bench.end.at_us, >=, bench.start.at_us);
        gst_object_unref(pad);
        clear_fixture(&bench);
    }
}

static void unmatched_and_dropped_frames_fail(void)
{
    GstPad *pad = gst_pad_new("test", GST_PAD_SRC);
    Bench bench;
    fixture(&bench, FALSE);
    GstBuffer *first = gst_buffer_new(), *second = gst_buffer_new();
    GST_BUFFER_PTS(first) = 100;
    GST_BUFFER_PTS(second) = 200;
    GstPadProbeInfo info = {.type = GST_PAD_PROBE_TYPE_BUFFER, .data = first};
    raw_probe(pad, &info, &bench);
    encoder_probe(pad, &info, &bench);
    info.data = second;
    output_probe(pad, &info, &bench);
    g_assert_nonnull(strstr(bench.error, "no matching input"));
    clear_fixture(&bench);
    fixture(&bench, FALSE);
    info.data = first;
    raw_probe(pad, &info, &bench);
    encoder_probe(pad, &info, &bench);
    info.data = second;
    raw_probe(pad, &info, &bench);
    encoder_probe(pad, &info, &bench);
    output_probe(pad, &info, &bench);
    g_assert_nonnull(strstr(bench.error, "dropped or reordered"));
    clear_fixture(&bench);
    gst_buffer_unref(first); gst_buffer_unref(second); gst_object_unref(pad);
}

static void capture_duplicate_pts_fails(void)
{
    Bench bench;
    fixture(&bench, TRUE);
    GstPad *pad = gst_pad_new("test", GST_PAD_SRC);
    GstBuffer *buffer = gst_buffer_new();
    GST_BUFFER_PTS(buffer) = 0;
    GstPadProbeInfo info = {.type = GST_PAD_PROBE_TYPE_BUFFER, .data = buffer};
    for (guint i = 0; i < 4; i++) raw_probe(pad, &info, &bench);
    g_assert_nonnull(strstr(bench.error, "PTS did not advance"));
    clear_fixture(&bench);
    gst_buffer_unref(buffer); gst_object_unref(pad);
}

static void destroyed(gpointer data, GstMiniObject *object)
{
    g_atomic_int_set((gint *)data, 1);
    (void)object;
}

static void plane_views_keep_capture_lease(void)
{
    /* A file-backed DMA-buf exercises ownership only, without video ioctls. */
    for (guint height = 16; height <= 18; height += 2) {
        Bench bench = {.width = 16, .height = height};
        g_mutex_init(&bench.lock);
        GError *error = NULL;
        bench.pipeline = gst_parse_launch(
            "appsrc name=source is-live=true ! appsink name=bridge emit-signals=true sync=false async=false "
            "appsrc name=encoder_source is-live=true ! appsink name=output sync=false async=false enable-last-sample=false", &error);
        g_assert_no_error(error);
        bench.encoder_source = gst_bin_get_by_name(GST_BIN(bench.pipeline), "encoder_source");
        GstElement *source = gst_bin_get_by_name(GST_BIN(bench.pipeline), "source");
        GstElement *bridge = gst_bin_get_by_name(GST_BIN(bench.pipeline), "bridge");
        GstElement *output = gst_bin_get_by_name(GST_BIN(bench.pipeline), "output");
        g_signal_connect(bridge, "new-sample", G_CALLBACK(forward_sample), &bench);
        FILE *file = tmpfile();
        g_assert_nonnull(file);
        guint luma = bench.width * height;
        guint aligned = bench.width * GST_ROUND_UP_16(height);
        g_assert_cmpint(ftruncate(fileno(file), luma + aligned / 2), ==, 0);
        GstAllocator *allocator = gst_dmabuf_allocator_new();
        GstMemory *memory = gst_dmabuf_allocator_alloc(allocator, dup(fileno(file)), luma * 3 / 2);
        gst_object_unref(allocator);
        GstBuffer *original = gst_buffer_new();
        gst_buffer_append_memory(original, memory);
        GST_BUFFER_PTS(original) = 123456;
        gint released = 0;
        gst_mini_object_weak_ref(GST_MINI_OBJECT(original), destroyed, &released);
        g_assert_cmpint(gst_element_set_state(bench.pipeline, GST_STATE_PLAYING), !=, GST_STATE_CHANGE_FAILURE);
        g_assert_cmpint(gst_app_src_push_buffer(GST_APP_SRC(source), original), ==, GST_FLOW_OK);
        GstSample *sample = gst_app_sink_try_pull_sample(GST_APP_SINK(output), GST_SECOND);
        g_assert_nonnull(sample);
        GstBuffer *view = gst_sample_get_buffer(sample);
        g_assert_cmpuint(gst_buffer_n_memory(view), ==, 2);
        g_assert_cmpuint(GST_BUFFER_PTS(view), ==, 123456);
        GstParentBufferMeta *parent = gst_buffer_get_parent_buffer_meta(view);
        g_assert_nonnull(parent);
        g_assert_true(parent->buffer == original);
        g_assert_cmpuint(gst_memory_get_sizes(gst_buffer_peek_memory(view, 0), NULL, NULL), ==, aligned);
        g_assert_cmpuint(gst_memory_get_sizes(gst_buffer_peek_memory(view, 1), NULL, NULL), ==, aligned / 2);
        g_assert_cmpint(g_atomic_int_get(&released), ==, 0);
        gst_element_set_state(bench.pipeline, GST_STATE_NULL);
        gst_object_unref(source); gst_object_unref(bridge); gst_object_unref(output);
        gst_object_unref(bench.encoder_source); gst_object_unref(bench.pipeline);
        g_assert_cmpint(g_atomic_int_get(&released), ==, 0);
        gst_sample_unref(sample);
        g_assert_cmpint(g_atomic_int_get(&released), ==, 1);
        g_assert_null(bench.error);
        g_mutex_clear(&bench.lock);
        fclose(file);
    }
}

int main(int argc, char **argv)
{
    gst_init(&argc, &argv);
    g_test_init(&argc, &argv, NULL);
    g_test_add_func("/bench/timing-warmup-and-matching", timing_matches_frames);
    g_test_add_func("/bench/reject-unmatched-or-dropped", unmatched_and_dropped_frames_fail);
    g_test_add_func("/bench/reject-duplicate-capture-pts", capture_duplicate_pts_fails);
    g_test_add_func("/bench/leased-plane-views", plane_views_keep_capture_lease);
    return g_test_run();
}
