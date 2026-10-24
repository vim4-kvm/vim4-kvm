/* SPDX-License-Identifier: MIT
 * Exclusive board measurement; caller owns board/heavy locks and services.
 * Build: cc -O2 -Wall -Wextra -Werror display-color.c -o display-color \
 *           $(pkg-config --cflags --libs libdrm)
 * tx CARD W H HZ rgb|444|420 full|limited PATTERN.ppm READY.json
 * capture VIDEO W H HZ OUTPUT_PREFIX (three uncompressed frames and metadata)
 * TX holds the dumb buffer until SIGTERM; capture never opens an encoder.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>

static volatile sig_atomic_t stop;

static void require(int condition, const char *message)
{
    if (!condition) {
        fprintf(stderr, "%s: %s\n", message, strerror(errno));
        exit(1);
    }
}

static void stopped(int sig)
{
    (void)sig;
    stop = 1;
}

static unsigned int number(const char *value)
{
    char *end;
    unsigned long n = strtoul(value, &end, 10);
    require(*value && !*end && n > 0 && n <= 65535, "invalid positive integer");
    return n;
}

static uint32_t property(int fd, uint32_t id, uint32_t type, const char *name,
                         uint64_t *value)
{
    drmModeObjectPropertiesPtr props = drmModeObjectGetProperties(fd, id, type);
    uint32_t result = 0;
    require(props != NULL, "object properties");
    for (uint32_t i = 0; i < props->count_props; i++) {
        drmModePropertyPtr p = drmModeGetProperty(fd, props->props[i]);
        require(p != NULL, "property description");
        if (!strcmp(p->name, name)) {
            result = p->prop_id;
            if (value) *value = props->prop_values[i];
        }
        drmModeFreeProperty(p);
    }
    drmModeFreeObjectProperties(props);
    return result;
}

static void add(int fd, drmModeAtomicReqPtr req, uint32_t id, uint32_t type,
                const char *name, uint64_t value)
{
    uint32_t p = property(fd, id, type, name, NULL);
    require(p != 0, name);
    require(drmModeAtomicAddProperty(req, id, p, value) >= 0, "add atomic property");
}

static uint64_t enum_value(int fd, uint32_t id, const char *name, const char *choice)
{
    uint32_t p = property(fd, id, DRM_MODE_OBJECT_CONNECTOR, name, NULL);
    drmModePropertyPtr prop = drmModeGetProperty(fd, p);
    require(prop != NULL, name);
    uint64_t result = UINT64_MAX;
    for (int i = 0; i < prop->count_enums; i++)
        if (!strcmp(prop->enums[i].name, choice)) result = prop->enums[i].value;
    drmModeFreeProperty(prop);
    require(result != UINT64_MAX, choice);
    return result;
}

static int transmit(char **args, int vendor)
{
    int fd = open(args[0], O_RDWR | O_CLOEXEC);
    require(fd >= 0, "open DRM card");
    require(drmSetClientCap(fd, DRM_CLIENT_CAP_ATOMIC, 1) == 0, "atomic KMS");
    drmModeResPtr res = drmModeGetResources(fd);
    require(res != NULL, "DRM resources");
    drmModeConnectorPtr conn = NULL;
    for (int i = 0; i < res->count_connectors; i++) {
        drmModeConnectorPtr c = drmModeGetConnector(fd, res->connectors[i]);
        if (c && c->connector_type == DRM_MODE_CONNECTOR_HDMIA &&
            c->connection == DRM_MODE_CONNECTED) { conn = c; break; }
        if (c) drmModeFreeConnector(c);
    }
    require(conn != NULL, "connected HDMI connector");
    unsigned int width = number(args[1]), height = number(args[2]), hz = number(args[3]);
    drmModeModeInfo *mode = NULL;
    for (int i = 0; i < conn->count_modes; i++) {
        drmModeModeInfo *m = &conn->modes[i];
        uint64_t rate = (uint64_t)m->clock * 1000;
        uint64_t wanted = (uint64_t)m->htotal * m->vtotal * hz;
        if (m->hdisplay == width && m->vdisplay == height &&
            !(m->flags & DRM_MODE_FLAG_INTERLACE) && rate == wanted) { mode = m; break; }
    }
    require(mode != NULL, "exact progressive integer-Hz EDID mode");
    uint32_t crtc = 0, crtc_index = 0;
    for (int i = 0; i < conn->count_encoders && !crtc; i++) {
        drmModeEncoderPtr enc = drmModeGetEncoder(fd, conn->encoders[i]);
        if (!enc) continue;
        for (int j = 0; j < res->count_crtcs; j++)
            if (enc->possible_crtcs & (1U << j)) {
                crtc = res->crtcs[j]; crtc_index = j; break;
            }
        drmModeFreeEncoder(enc);
    }
    require(crtc != 0, "possible CRTC");
    drmModePlaneResPtr planes = drmModeGetPlaneResources(fd);
    require(planes != NULL, "plane resources");
    uint32_t primary = 0;
    for (uint32_t i = 0; i < planes->count_planes; i++) {
        drmModePlanePtr p = drmModeGetPlane(fd, planes->planes[i]);
        uint64_t type = UINT64_MAX;
        require(p != NULL, "plane description");
        property(fd, p->plane_id, DRM_MODE_OBJECT_PLANE, "type", &type);
        if ((p->possible_crtcs & (1U << crtc_index)) && type == DRM_PLANE_TYPE_PRIMARY)
            primary = p->plane_id;
        drmModeFreePlane(p);
    }
    require(primary != 0, "primary plane");
    struct drm_mode_create_dumb dumb = {.width=width, .height=height, .bpp=32};
    require(ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &dumb) == 0, "create dumb buffer");
    struct drm_mode_map_dumb map = {.handle=dumb.handle};
    require(ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map) == 0, "map dumb offset");
    uint8_t *pixels = mmap(NULL, dumb.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map.offset);
    require(pixels != MAP_FAILED, "map dumb buffer");
    FILE *ppm = fopen(args[6], "rb");
    unsigned int pw = 0, ph = 0;
    require(ppm && fscanf(ppm, "P6\n%u %u\n255", &pw, &ph) == 2 &&
            fgetc(ppm) == '\n' && pw == width && ph == height, "PPM geometry/header");
    for (unsigned int y = 0; y < height; y++) {
        uint32_t *row = (uint32_t *)(pixels + y * dumb.pitch);
        for (unsigned int x = 0; x < width; x++) {
            unsigned char rgb[3];
            require(fread(rgb, 1, 3, ppm) == 3, "read PPM pixels");
            row[x] = rgb[0] << 16 | rgb[1] << 8 | rgb[2];
        }
    }
    fclose(ppm);
    uint32_t handles[4] = {dumb.handle}, pitches[4] = {dumb.pitch}, offsets[4] = {0};
    uint32_t fb, blob;
    require(drmModeAddFB2(fd, width, height, DRM_FORMAT_XRGB8888,
                         handles, pitches, offsets, &fb, 0) == 0, "add framebuffer");
    require(drmModeCreatePropertyBlob(fd, mode, sizeof(*mode), &blob) == 0, "mode blob");
    const char *format = !strcmp(args[4], "rgb") ? "RGB" :
                         !strcmp(args[4], "444") ? "YUV 4:4:4" :
                         !strcmp(args[4], "420") ? "YUV 4:2:0" : NULL;
    require(format != NULL && (vendor ? !strcmp(args[5], "native") :
            (!strcmp(args[5], "full") || !strcmp(args[5], "limited"))),
            "format/range");
    drmModeAtomicReqPtr req = drmModeAtomicAlloc();
    require(req != NULL, "atomic request");
    add(fd, req, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID", crtc);
    if (vendor) {
        add(fd, req, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "color_depth", 8);
        add(fd, req, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "color_space",
            enum_value(fd, conn->connector_id, "color_space",
                       !strcmp(args[4], "rgb") ? "RGB" : args[4]));
    } else {
        add(fd, req, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "max bpc", 8);
        add(fd, req, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "color format",
            enum_value(fd, conn->connector_id, "color format", format));
        add(fd, req, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "Broadcast RGB",
            !strcmp(args[5], "full") ? 1 : 2);
    }
    add(fd, req, crtc, DRM_MODE_OBJECT_CRTC, "MODE_ID", blob);
    add(fd, req, crtc, DRM_MODE_OBJECT_CRTC, "ACTIVE", 1);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "FB_ID", fb);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "CRTC_ID", crtc);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "SRC_X", 0);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "SRC_Y", 0);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "SRC_W", width << 16);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "SRC_H", height << 16);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "CRTC_X", 0);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "CRTC_Y", 0);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "CRTC_W", width);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "CRTC_H", height);
    require(drmModeAtomicCommit(fd, req, DRM_MODE_ATOMIC_TEST_ONLY |
                               DRM_MODE_ATOMIC_ALLOW_MODESET, NULL) == 0, "atomic TEST_ONLY");
    require(drmModeAtomicCommit(fd, req, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL) == 0,
            "atomic modeset");
    FILE *ready = fopen(args[7], "wx");
    require(ready != NULL, "new ready file");
    fprintf(ready, "{\"connector\":%u,\"crtc\":%u,\"plane\":%u,\"fb\":%u,"
            "\"width\":%u,\"height\":%u,\"clock_khz\":%u,\"pitch\":%u}\n",
            conn->connector_id, crtc, primary, fb, width, height, mode->clock, dumb.pitch);
    require(fclose(ready) == 0, "close ready file");
    while (!stop) {
        struct timespec delay = {.tv_nsec=100000000};
        nanosleep(&delay, NULL);
    }
    drmModeAtomicFree(req);
    req = drmModeAtomicAlloc();
    require(req != NULL, "disable request");
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "FB_ID", 0);
    add(fd, req, primary, DRM_MODE_OBJECT_PLANE, "CRTC_ID", 0);
    add(fd, req, crtc, DRM_MODE_OBJECT_CRTC, "ACTIVE", 0);
    add(fd, req, crtc, DRM_MODE_OBJECT_CRTC, "MODE_ID", 0);
    add(fd, req, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID", 0);
    require(drmModeAtomicCommit(fd, req, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL) == 0,
            "atomic disable");
    drmModeAtomicFree(req);
    require(drmModeRmFB(fd, fb) == 0, "remove framebuffer");
    drmModeDestroyPropertyBlob(fd, blob);
    munmap(pixels, dumb.size);
    struct drm_mode_destroy_dumb destroy = {.handle=dumb.handle};
    require(ioctl(fd, DRM_IOCTL_MODE_DESTROY_DUMB, &destroy) == 0, "destroy dumb buffer");
    drmModeFreePlaneResources(planes);
    drmModeFreeConnector(conn);
    drmModeFreeResources(res);
    close(fd);
    return 0;
}

static int capture(char **args)
{
    int fd = open(args[0], O_RDWR | O_NONBLOCK | O_CLOEXEC);
    require(fd >= 0, "open capture");
    struct v4l2_format format = {.type=V4L2_BUF_TYPE_VIDEO_CAPTURE};
    format.fmt.pix.width = number(args[1]);
    format.fmt.pix.height = number(args[2]);
    format.fmt.pix.pixelformat = V4L2_PIX_FMT_NV12;
    format.fmt.pix.field = V4L2_FIELD_NONE;
    struct v4l2_dv_timings timings = {0};
    int stable = 0;
    for (int attempt = 0; attempt < 100 && stable < 2 && !stop; attempt++) {
        memset(&timings, 0, sizeof(timings));
        if (ioctl(fd, VIDIOC_QUERY_DV_TIMINGS, &timings) == 0 &&
            timings.type == V4L2_DV_BT_656_1120 && !timings.bt.interlaced &&
            timings.bt.width == format.fmt.pix.width && timings.bt.height == format.fmt.pix.height) {
            uint64_t total = (uint64_t)(timings.bt.width + timings.bt.hfrontporch +
                timings.bt.hsync + timings.bt.hbackporch) *
                (timings.bt.height + timings.bt.vfrontporch + timings.bt.vsync + timings.bt.vbackporch);
            uint64_t wanted = total * number(args[3]);
            uint64_t error = timings.bt.pixelclock > wanted ? timings.bt.pixelclock - wanted :
                             wanted - timings.bt.pixelclock;
            stable = wanted && error * 200 <= wanted ? stable + 1 : 0;
        } else {
            stable = 0;
        }
        struct timespec delay = {.tv_nsec=100000000};
        nanosleep(&delay, NULL);
    }
    require(stable == 2 && !stop, "native RX DV timings/rate did not qualify");
    require(ioctl(fd, VIDIOC_S_FMT, &format) == 0, "capture S_FMT");
    struct v4l2_pix_format *f = &format.fmt.pix;
    require(f->width == number(args[1]) && f->height == number(args[2]) &&
            f->pixelformat == V4L2_PIX_FMT_NV12 && f->bytesperline >= f->width,
            "capture must be native NV12 geometry");
    struct v4l2_requestbuffers req = {.count=4, .type=format.type, .memory=V4L2_MEMORY_MMAP};
    require(ioctl(fd, VIDIOC_REQBUFS, &req) == 0 && req.count == 4, "capture REQBUFS");
    void *data[4]; size_t length[4];
    for (unsigned int i = 0; i < 4; i++) {
        struct v4l2_buffer b = {.index=i, .type=format.type, .memory=req.memory};
        require(ioctl(fd, VIDIOC_QUERYBUF, &b) == 0, "capture QUERYBUF");
        length[i] = b.length;
        data[i] = mmap(NULL, b.length, PROT_READ, MAP_SHARED, fd, b.m.offset);
        require(data[i] != MAP_FAILED, "capture mmap");
        require(ioctl(fd, VIDIOC_QBUF, &b) == 0, "capture QBUF");
    }
    require(ioctl(fd, VIDIOC_STREAMON, &format.type) == 0, "capture STREAMON");
    char path[4096];
    require(snprintf(path, sizeof(path), "%s.json", args[4]) < (int)sizeof(path), "metadata path");
    FILE *meta = fopen(path, "wx");
    require(meta != NULL, "new capture metadata");
    fprintf(meta, "{\"width\":%u,\"height\":%u,\"stride\":%u,\"sizeimage\":%u,"
            "\"format\":\"NV12\",\"uv_offset\":%u,\"colorspace\":%u,"
            "\"ycbcr_enc\":%u,\"quantization\":%u,\"rx_pixelclock\":%llu,\"frames\":[",
            f->width, f->height, f->bytesperline, f->sizeimage,
            f->bytesperline * ((f->height + 15) & ~15U),
            f->colorspace, f->ycbcr_enc, f->quantization, (unsigned long long)timings.bt.pixelclock);
    uint32_t previous = 0;
    for (unsigned int i = 0; i < 11 && !stop; i++) {
        struct pollfd pollfd = {.fd=fd, .events=POLLIN};
        require(poll(&pollfd, 1, 10000) > 0 && (pollfd.revents & POLLIN), "capture poll");
        struct v4l2_buffer b = {.type=format.type, .memory=req.memory};
        require(ioctl(fd, VIDIOC_DQBUF, &b) == 0 && b.index < 4, "capture DQBUF");
        require(!(b.flags & V4L2_BUF_FLAG_ERROR) && b.bytesused >= f->sizeimage &&
                b.bytesused <= length[b.index] && (!i || b.sequence > previous),
                "capture completeness/sequence");
        previous = b.sequence;
        if (i >= 8) {
            require(snprintf(path, sizeof(path), "%s-%u.raw", args[4], i-8) <
                    (int)sizeof(path), "raw path");
            FILE *raw = fopen(path, "wx");
            require(raw != NULL, "new raw frame");
            require(fwrite(data[b.index], 1, b.bytesused, raw) == b.bytesused &&
                    fclose(raw) == 0, "write raw frame");
            fprintf(meta, "%s{\"index\":%u,\"sequence\":%u,\"timestamp_us\":%lld,"
                    "\"bytesused\":%u}", i==8?"":",", i-8, b.sequence,
                    (long long)b.timestamp.tv_sec*1000000+b.timestamp.tv_usec, b.bytesused);
        }
        require(ioctl(fd, VIDIOC_QBUF, &b) == 0, "capture requeue");
    }
    require(!stop, "capture interrupted");
    fprintf(meta, "]}\n");
    require(fclose(meta) == 0, "close capture metadata");
    require(ioctl(fd, VIDIOC_STREAMOFF, &format.type) == 0, "capture STREAMOFF");
    for (unsigned int i = 0; i < 4; i++) munmap(data[i], length[i]);
    req.count = 0;
    require(ioctl(fd, VIDIOC_REQBUFS, &req) == 0, "capture release buffers");
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    signal(SIGTERM, stopped);
    signal(SIGINT, stopped);
    if (argc == 10 && !strcmp(argv[1], "tx")) return transmit(argv+2, 0);
    if (argc == 10 && !strcmp(argv[1], "tx-vendor")) return transmit(argv+2, 1);
    if (argc == 7 && !strcmp(argv[1], "capture")) return capture(argv+2);
    fprintf(stderr, "See display-color.c for tx/capture arguments\n");
    return 2;
}
