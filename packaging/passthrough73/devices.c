/* SPDX-License-Identifier: MIT */
/* Linux device boundary. Compile: cc -shared -fPIC -O2 -Wall -Wextra -Werror
 * devices.c -o libpassthrough73.so $(pkg-config --cflags --libs libdrm)
 * Errors are negative errno. Caller owns event-loop ordering and reader leases.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/dma-buf.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>

#define MAX_BUFFERS 16
#define POOL_BUDGET (192U * 1024U * 1024U)
struct capture {
    int fd, running;
    unsigned count, width, height, pitch, size, colorspace, quantization, rate;
    int exports[MAX_BUFFERS];
    unsigned lengths[MAX_BUFFERS];
    unsigned char queued[MAX_BUFFERS];
};
struct completed_frame {
    unsigned index, sequence;
    uint64_t timestamp_ns;
};

static int call(int fd, unsigned long request, void *argument)
{
    int result;
    do { result = ioctl(fd, request, argument); } while (result < 0 && errno == EINTR);
    return result < 0 ? -errno : 0;
}

int pt_capture_stop(struct capture *c)
{
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    int result;
    if (!c->running) return 0;
    result = call(c->fd, VIDIOC_STREAMOFF, &type);
    if (result) return result; /* Keep every descriptor if DMA stop is unproven. */
    c->running = 0;
    memset(c->queued, 0, sizeof(c->queued));
    return 0;
}

int pt_capture_close(struct capture *c)
{
    int result;
    if (!c) return 0;
    result = pt_capture_stop(c);
    if (result) return result;
    for (unsigned i = 0; i < c->count; i++)
        if (c->exports[i] >= 0) close(c->exports[i]);
    if (c->fd >= 0) close(c->fd);
    free(c);
    return 0;
}

int pt_capture_open(const char *path, unsigned count, struct capture **output)
{
    struct capture *c;
    struct v4l2_capability caps = {0};
    struct v4l2_format format = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    struct v4l2_requestbuffers request = {
        .count = count, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP
    };
    int result;
    *output = NULL;
    if (count < 4 || count > MAX_BUFFERS) return -EINVAL;
    c = calloc(1, sizeof(*c));
    if (!c) return -ENOMEM;
    c->fd = -1;
    for (unsigned i = 0; i < MAX_BUFFERS; i++) c->exports[i] = -1;
    c->fd = open(path, O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (c->fd < 0) { result = -errno; goto fail; }
    result = call(c->fd, VIDIOC_QUERYCAP, &caps);
    if (result) goto fail;
    unsigned features = caps.capabilities & V4L2_CAP_DEVICE_CAPS ? caps.device_caps : caps.capabilities;
    if ((features & (V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING)) !=
        (V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING)) { result = -ENOTSUP; goto fail; }
    result = call(c->fd, VIDIOC_G_FMT, &format);
    if (result) goto fail;
    struct v4l2_dv_timings timings = {0};
    result = call(c->fd, VIDIOC_QUERY_DV_TIMINGS, &timings);
    if (!result) {
        uint64_t htotal = (uint64_t)timings.bt.width + timings.bt.hfrontporch +
                         timings.bt.hsync + timings.bt.hbackporch;
        uint64_t vtotal = (uint64_t)timings.bt.height + timings.bt.vfrontporch +
                         timings.bt.vsync + timings.bt.vbackporch;
        if (htotal && vtotal) c->rate = timings.bt.pixelclock * 100 / (htotal * vtotal);
        format.fmt.pix.width = timings.bt.width;
        format.fmt.pix.height = timings.bt.height;
        format.fmt.pix.pixelformat = V4L2_PIX_FMT_NV12;
        result = call(c->fd, VIDIOC_S_FMT, &format);
        if (result) goto fail;
    } else if (result != -EINVAL && result != -ENOTTY) goto fail;
    struct v4l2_event_subscription subscription = {.type = V4L2_EVENT_SOURCE_CHANGE};
    result = call(c->fd, VIDIOC_SUBSCRIBE_EVENT, &subscription);
    if (result && result != -EINVAL && result != -ENOTTY) goto fail;
    struct v4l2_pix_format *f = &format.fmt.pix;
    if (f->pixelformat != V4L2_PIX_FMT_NV12 || !f->width || !f->height ||
        (f->width & 1) || (f->height & 1) || f->bytesperline < f->width ||
        (uint64_t)f->bytesperline * f->height * 3 / 2 > f->sizeimage ||
        (uint64_t)f->sizeimage * count > POOL_BUDGET) { result = -EINVAL; goto fail; }
    c->width = f->width; c->height = f->height; c->pitch = f->bytesperline;
    c->size = f->sizeimage; c->colorspace = f->colorspace; c->quantization = f->quantization;
    result = call(c->fd, VIDIOC_REQBUFS, &request);
    if (result) goto fail;
    if (request.count < 4 || request.count > count) { result = -ENOBUFS; goto fail; }
    c->count = request.count;
    for (unsigned i = 0; i < c->count; i++) {
        struct v4l2_buffer buffer = {.index = i, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
                                    .memory = V4L2_MEMORY_MMAP};
        struct v4l2_exportbuffer export = {.index = i, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
                                          .flags = O_CLOEXEC | O_RDWR};
        result = call(c->fd, VIDIOC_QUERYBUF, &buffer);
        if (result) goto fail;
        if (buffer.length < c->size) { result = -EINVAL; goto fail; }
        c->lengths[i] = buffer.length;
        result = call(c->fd, VIDIOC_EXPBUF, &export);
        if (result) goto fail;
        c->exports[i] = export.fd; /* Exactly one export per buffer per pool. */
    }
    *output = c;
    return 0;
fail:
    pt_capture_close(c);
    return result;
}

int pt_capture_queue(struct capture *c, unsigned index)
{
    struct v4l2_buffer b = {.index = index, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
                           .memory = V4L2_MEMORY_MMAP};
    int result;
    if (index >= c->count || c->queued[index]) return -EINVAL;
    result = call(c->fd, VIDIOC_QBUF, &b);
    if (!result) c->queued[index] = 1;
    return result;
}

int pt_capture_start(struct capture *c)
{
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    int result;
    if (c->running) return -EBUSY;
    for (unsigned i = 0; i < c->count; i++) {
        result = pt_capture_queue(c, i);
        if (result) return result;
    }
    result = call(c->fd, VIDIOC_STREAMON, &type);
    if (!result) c->running = 1;
    return result;
}

int pt_capture_read(struct capture *c, struct completed_frame *frame)
{
    struct v4l2_buffer b = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP};
    int result = call(c->fd, VIDIOC_DQBUF, &b);
    if (result) return result;
    if (b.index >= c->count || !c->queued[b.index]) return -EPROTO;
    c->queued[b.index] = 0;
    frame->index = b.index; frame->sequence = b.sequence;
    frame->timestamp_ns = (uint64_t)b.timestamp.tv_sec * 1000000000 + b.timestamp.tv_usec * 1000;
    if (b.flags & V4L2_BUF_FLAG_ERROR) return -EIO;
    if ((b.flags & V4L2_BUF_FLAG_TIMESTAMP_MASK) != V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC ||
        b.bytesused < c->pitch * c->height * 3 / 2) return -EPROTO;
    return 0;
}

int pt_capture_fd(struct capture *c) { return c->fd; }
int pt_capture_source_changed(struct capture *c)
{
    struct v4l2_event event;
    int result = call(c->fd, VIDIOC_DQEVENT, &event);
    if (result == -EAGAIN || result == -EINVAL || result == -ENOTTY) return 0;
    if (result) return result;
    return event.type == V4L2_EVENT_SOURCE_CHANGE ? 1 : 0;
}
unsigned pt_capture_info(struct capture *c, unsigned field)
{
    const unsigned info[] = {c->count, c->width, c->height, c->pitch, c->size,
                             c->colorspace, c->quantization, c->rate};
    return field < sizeof(info) / sizeof(info[0]) ? info[field] : 0;
}
int pt_capture_export(struct capture *c, unsigned index) { return index < c->count ? c->exports[index] : -1; }
unsigned pt_capture_length(struct capture *c, unsigned index) { return index < c->count ? c->lengths[index] : 0; }

/* One framebuffer owns one PRIME handle and keeps the supplied dma-buf open.
 * Caller retains this object across errors after a real atomic commit attempt.
 */
struct scanout { int drm_fd, dma_fd, fence_fd, submitted; uint32_t fb, handle; };

int pt_scanout_create(int drm_fd, int dma_fd, unsigned width, unsigned height,
                      unsigned pitch, unsigned uv_offset, struct scanout **output)
{
    struct scanout *s = calloc(1, sizeof(*s));
    uint32_t handles[4] = {0}, pitches[4] = {pitch, pitch}, offsets[4] = {0, uv_offset};
    int result;
    *output = NULL;
    if (!s) return -ENOMEM;
    s->drm_fd = drm_fd; s->fence_fd = -1;
    s->dma_fd = fcntl(dma_fd, F_DUPFD_CLOEXEC, 0);
    if (s->dma_fd < 0) { result = -errno; goto fail; }
    if (drmPrimeFDToHandle(drm_fd, s->dma_fd, &s->handle)) { result = -errno; goto fail; }
    handles[0] = handles[1] = s->handle;
    if (drmModeAddFB2(drm_fd, width, height, DRM_FORMAT_NV12, handles, pitches, offsets, &s->fb, 0)) {
        result = -errno; goto fail;
    }
    *output = s;
    return 0;
fail:
    if (s->handle) drmCloseBufferHandle(drm_fd, s->handle);
    if (s->dma_fd >= 0) close(s->dma_fd);
    free(s);
    return result;
}

static int object_property(drmModeAtomicReq *request, int fd, uint32_t plane, uint32_t type,
                    const char *name, uint64_t value)
{
    drmModeObjectProperties *properties = drmModeObjectGetProperties(fd, plane, type);
    int result = -ENOENT;
    if (!properties) return -errno;
    for (unsigned i = 0; i < properties->count_props; i++) {
        drmModePropertyRes *p = drmModeGetProperty(fd, properties->props[i]);
        if (!p) continue;
        if (!strcmp(p->name, name)) {
            result = drmModeAtomicAddProperty(request, plane, p->prop_id, value) < 0 ? -errno : 0;
            drmModeFreeProperty(p);
            break;
        }
        drmModeFreeProperty(p);
    }
    drmModeFreeObjectProperties(properties);
    return result;
}

static int property(drmModeAtomicReq *request, int fd, uint32_t plane,
                    const char *name, uint64_t value)
{
    return object_property(request, fd, plane, DRM_MODE_OBJECT_PLANE, name, value);
}

int pt_scanout_commit(struct scanout *s, uint32_t plane, uint32_t crtc,
                      unsigned width, unsigned height, int test_only)
{
    const char *names[] = {"FB_ID", "CRTC_ID", "SRC_X", "SRC_Y", "SRC_W", "SRC_H",
                           "CRTC_X", "CRTC_Y", "CRTC_W", "CRTC_H"};
    uint64_t values[] = {s->fb, crtc, 0, 0, (uint64_t)width << 16, (uint64_t)height << 16,
                         0, 0, width, height};
    drmModeAtomicReq *request = drmModeAtomicAlloc();
    int result = 0;
    if (!request) return -ENOMEM;
    if (s->submitted) { drmModeAtomicFree(request); return -EBUSY; }
    for (unsigned i = 0; i < sizeof(names) / sizeof(names[0]); i++)
        if ((result = property(request, s->drm_fd, plane, names[i], values[i]))) goto done;
    if (!test_only) s->submitted = 1; /* An ioctl error is not DMA-stop evidence. */
    if (drmModeAtomicCommit(s->drm_fd, request,
                            test_only ? DRM_MODE_ATOMIC_TEST_ONLY : DRM_MODE_ATOMIC_NONBLOCK, NULL)) {
        result = -errno;
        goto done;
    }
    if (!test_only) {
        /* WRITE direction includes every existing reader fence, including the
         * T7 driver's extra scan-period fence. OUT_FENCE/page-flip is insufficient.
         */
        struct dma_buf_export_sync_file sync = {.flags = DMA_BUF_SYNC_WRITE, .fd = -1};
        result = call(s->dma_fd, DMA_BUF_IOCTL_EXPORT_SYNC_FILE, &sync);
        if (!result) s->fence_fd = sync.fd;
    }
done:
    drmModeAtomicFree(request);
    return result;
}

int pt_scanout_retired(struct scanout *s)
{
    struct pollfd p = {.fd = s->fence_fd, .events = POLLIN};
    if (!s->submitted) return 1;
    if (s->fence_fd < 0) return 0;
    int result = poll(&p, 1, 0);
    if (result < 0) return -errno;
    return result && (p.revents & POLLIN) ? 1 : 0;
}

int pt_scanout_destroy(struct scanout *s)
{
    if (pt_scanout_retired(s) != 1) return -EBUSY;
    if (drmModeRmFB(s->drm_fd, s->fb)) return -errno;
    drmCloseBufferHandle(s->drm_fd, s->handle);
    close(s->dma_fd);
    if (s->fence_fd >= 0) close(s->fence_fd);
    free(s);
    return 0;
}

int pt_reader_fence(int dma_fd)
{
    struct dma_buf_export_sync_file sync = {.flags = DMA_BUF_SYNC_WRITE, .fd = -1};
    int result = call(dma_fd, DMA_BUF_IOCTL_EXPORT_SYNC_FILE, &sync);
    return result ? result : sync.fd;
}

int pt_plane_disable(int fd, unsigned plane)
{
    drmModeAtomicReq *request = drmModeAtomicAlloc();
    if (!request) return -ENOMEM;
    int result = property(request, fd, plane, "FB_ID", 0);
    if (!result) result = property(request, fd, plane, "CRTC_ID", 0);
    if (!result && drmModeAtomicCommit(fd, request, 0, NULL)) result = -errno;
    drmModeAtomicFree(request);
    return result;
}

static int mode_matches(const drmModeModeInfo *mode, unsigned width, unsigned height, unsigned rate)
{
    uint64_t total = (uint64_t)mode->htotal * mode->vtotal;
    if (!total || (mode->flags & DRM_MODE_FLAG_INTERLACE)) return 0;
    uint64_t actual = (uint64_t)mode->clock * 1000000 / total;
    return mode->hdisplay == width && mode->vdisplay == height &&
        (actual > rate ? actual - rate : rate - actual) <= 20;
}

int pt_mode_supported(int fd, unsigned connector, unsigned width, unsigned height, unsigned rate)
{
    drmModeConnector *sink = drmModeGetConnectorCurrent(fd, connector);
    if (!sink) return -errno;
    int found = 0;
    if (sink->connection == DRM_MODE_CONNECTED)
        for (int i = 0; i < sink->count_modes; i++)
            found |= mode_matches(&sink->modes[i], width, height, rate);
    drmModeFreeConnector(sink);
    return found;
}

uint64_t pt_connector_signature(int fd, unsigned connector)
{
    drmModeConnector *sink = drmModeGetConnectorCurrent(fd, connector);
    if (!sink) return 0;
    uint64_t hash = sink->connection;
    for (int i = 0; i < sink->count_props; i++) {
        drmModePropertyRes *p = drmModeGetProperty(fd,sink->props[i]);
        if (p && !strcmp(p->name,"EDID") && sink->prop_values[i]) {
            drmModePropertyBlobRes *b = drmModeGetPropertyBlob(fd,sink->prop_values[i]);
            if (b) {
                const unsigned char *data = b->data;
                for (unsigned j = 0; j < b->length; j++) hash = (hash ^ data[j]) * 1099511628211ULL;
                drmModeFreePropertyBlob(b);
            }
        }
        if (p) drmModeFreeProperty(p);
    }
    drmModeFreeConnector(sink);
    return hash;
}

int pt_capture_rate(struct capture *c)
{
    struct v4l2_dv_timings t = {0};
    int result = call(c->fd, VIDIOC_QUERY_DV_TIMINGS, &t);
    if (result) return result;
    uint64_t h = (uint64_t)t.bt.width + t.bt.hfrontporch + t.bt.hsync + t.bt.hbackporch;
    uint64_t v = (uint64_t)t.bt.height + t.bt.vfrontporch + t.bt.vsync + t.bt.vbackporch;
    if (!h || !v) return -ENOLINK;
    return t.bt.pixelclock * 100 / (h * v);
}

int pt_modeset_rate(int fd, unsigned connector, unsigned crtc, unsigned width, unsigned height, unsigned rate)
{
    if (drmSetClientCap(fd, DRM_CLIENT_CAP_ATOMIC, 1)) return -errno;
    drmModeConnector *sink = drmModeGetConnector(fd, connector);
    if (!sink) return -errno;
    int result = -ENOLINK;
    if (sink->connection != DRM_MODE_CONNECTED) goto done;
    for (int i = 0; i < sink->count_modes; i++) {
        drmModeModeInfo *mode = &sink->modes[i];
        if (!mode_matches(mode, width, height, rate)) continue;
        uint32_t blob;
        if (drmModeCreatePropertyBlob(fd, mode, sizeof(*mode), &blob)) { result = -errno; break; }
        drmModeAtomicReq *request = drmModeAtomicAlloc();
        if (!request) { drmModeDestroyPropertyBlob(fd, blob); result = -ENOMEM; break; }
        result = object_property(request, fd, connector, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID", crtc);
        if (!result) result = object_property(request, fd, crtc, DRM_MODE_OBJECT_CRTC, "MODE_ID", blob);
        if (!result) result = object_property(request, fd, crtc, DRM_MODE_OBJECT_CRTC, "ACTIVE", 1);
        if (!result && drmModeAtomicCommit(fd, request,
                DRM_MODE_ATOMIC_TEST_ONLY | DRM_MODE_ATOMIC_ALLOW_MODESET, NULL)) result = -errno;
        if (!result && drmModeAtomicCommit(fd, request, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL)) result = -errno;
        drmModeAtomicFree(request);
        drmModeDestroyPropertyBlob(fd, blob);
        break;
    }
done:
    drmModeFreeConnector(sink);
    return result;
}

int pt_modeset(int fd, unsigned connector, unsigned crtc, unsigned width, unsigned height)
{ return pt_modeset_rate(fd, connector, crtc, width, height, 60000); }
