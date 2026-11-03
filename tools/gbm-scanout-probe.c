/* SPDX-License-Identifier: MIT
 * Exclusive, current-mode-only scanout. Does not steal DRM master or send HID.
 * cc -Wall -Wextra -Werror $(pkg-config --cflags libdrm) gbm-scanout-probe.c -lgbm -ldrm -ldl -o gbm-scanout-probe
 */
#define _POSIX_C_SOURCE 200809L
#include <gbm.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>
#include <linux/dma-buf.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopped;
static void stop(int sig) { (void)sig; stopped = 1; }
#define CHECK(test, why) do { if (!(test)) { perror(why); goto cleanup; } } while (0)

int main(int argc, char **argv)
{
    int fd = -1, exporter = -1, dma = -1, result = 2, changed = 0, master = 0;
    uint32_t connector = 0, fb = 0, handle = 0;
    drmModeRes *resources = NULL;
    drmModeCrtc *saved = NULL;
    struct gbm_device *gbm = NULL;
    struct gbm_bo *bo = NULL;
    void *pixels = MAP_FAILED;
    size_t length = 0;
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (argc != 2) { fprintf(stderr, "Usage: gbm-scanout-probe /dev/dri/cardN\n"); return 2; }
    signal(SIGTERM, stop); signal(SIGINT, stop);
    fd = open(argv[1], O_RDWR | O_CLOEXEC);
    CHECK(fd >= 0, "open display");
    resources = drmModeGetResources(fd);
    CHECK(resources, "DRM resources");
    for (int i = 0; i < resources->count_connectors; i++) {
        drmModeConnector *c = drmModeGetConnector(fd, resources->connectors[i]);
        if (!c) continue;
        drmModeEncoder *e = c->encoder_id ? drmModeGetEncoder(fd, c->encoder_id) : NULL;
        if (c->connection == DRM_MODE_CONNECTED && e && e->crtc_id) {
            if (connector) { fprintf(stderr, "Multiple active connectors: cannot restore safely\n"); drmModeFreeEncoder(e); drmModeFreeConnector(c); goto cleanup; }
            connector = c->connector_id;
            saved = drmModeGetCrtc(fd, e->crtc_id);
        }
        if (e) drmModeFreeEncoder(e);
        drmModeFreeConnector(c);
    }
    if (!connector || !saved || !saved->mode_valid || !saved->buffer_id) {
        fprintf(stderr, "No active connector/CRTC/framebuffer to preserve\n"); goto cleanup;
    }
    CHECK(drmSetMaster(fd) == 0, "DRM master unavailable; no stealing");
    master = 1;
    exporter = open(argv[1], O_RDWR | O_CLOEXEC);
    CHECK(exporter >= 0, "open exporter");
    gbm = gbm_create_device(exporter);
    CHECK(gbm, "GBM device");
    bo = gbm_bo_create(gbm, saved->mode.hdisplay, saved->mode.vdisplay,
                       GBM_FORMAT_XRGB8888, GBM_BO_USE_SCANOUT);
    CHECK(bo, "GBM scanout BO");
    uint64_t (*modifier)(struct gbm_bo *) = dlsym(RTLD_DEFAULT, "gbm_bo_get_modifier");
    int (*planes)(struct gbm_bo *) = dlsym(RTLD_DEFAULT, "gbm_bo_get_plane_count");
    uint32_t (*offset)(struct gbm_bo *, int) = dlsym(RTLD_DEFAULT, "gbm_bo_get_offset");
    if (!modifier || !planes || !offset || planes(bo) != 1 || modifier(bo) != DRM_FORMAT_MOD_LINEAR) {
        fprintf(stderr, "Linear single-plane layout not established; refusing layout guess\n"); goto cleanup;
    }
    dma = gbm_bo_get_fd(bo);
    CHECK(dma >= 0, "export BO");
    off_t size = lseek(dma, 0, SEEK_END);
    uint32_t stride = gbm_bo_get_stride(bo);
    uint32_t plane_offset = offset(bo, 0);
    CHECK(size > 0 && (uint64_t)size <= 512u * 1024 * 1024 &&
          stride >= (uint32_t)saved->mode.hdisplay * 4 &&
          (uint64_t)plane_offset + (uint64_t)stride * saved->mode.vdisplay <= (uint64_t)size, "BO bounds");
    length = (size_t)size;
    pixels = mmap(NULL, length, PROT_READ | PROT_WRITE, MAP_SHARED, dma, 0);
    CHECK(pixels != MAP_FAILED, "map BO");
    struct dma_buf_sync sync = {.flags = DMA_BUF_SYNC_START | DMA_BUF_SYNC_WRITE};
    CHECK(ioctl(dma, DMA_BUF_IOCTL_SYNC, &sync) == 0, "CPU access start");
    for (unsigned y = 0; y < saved->mode.vdisplay; y++) {
        uint32_t *row = (uint32_t *)((char *)pixels + plane_offset + y * stride);
        for (unsigned x = 0; x < saved->mode.hdisplay; x++) row[x] = 0x004080c0;
    }
    sync.flags = DMA_BUF_SYNC_END | DMA_BUF_SYNC_WRITE;
    CHECK(ioctl(dma, DMA_BUF_IOCTL_SYNC, &sync) == 0, "CPU access end");
    CHECK(drmPrimeFDToHandle(fd, dma, &handle) == 0, "display PRIME import");
    uint32_t handles[4] = {handle}, pitches[4] = {stride}, offsets[4] = {plane_offset};
    CHECK(drmModeAddFB2(fd, saved->mode.hdisplay, saved->mode.vdisplay,
                        DRM_FORMAT_XRGB8888, handles, pitches, offsets, &fb, 0) == 0, "AddFB2");
    CHECK(drmModeSetCrtc(fd, saved->crtc_id, fb, 0, 0, &connector, 1, &saved->mode) == 0, "current-mode scanout");
    changed = 1;
    printf("scanout committed connector=%u crtc=%u fb=%u mode=%ux%u stride=%u\n",
           connector, saved->crtc_id, fb, saved->mode.hdisplay, saved->mode.vdisplay, stride);
    for (int i = 0; i < 50 && !stopped; i++) { struct timespec delay = {0, 100000000}; nanosleep(&delay, NULL); }
    result = 0;
cleanup:
    if (changed && drmModeSetCrtc(fd, saved->crtc_id, saved->buffer_id, saved->x, saved->y,
                                 &connector, 1, &saved->mode)) {
        perror("restore original CRTC"); result = 3;
    } else if (changed) puts("original framebuffer/mode restored");
    if (fb) drmModeRmFB(fd, fb);
    if (handle) { struct drm_gem_close close_handle = {.handle = handle}; ioctl(fd, DRM_IOCTL_GEM_CLOSE, &close_handle); }
    if (pixels != MAP_FAILED) munmap(pixels, length);
    if (dma >= 0) close(dma);
    if (bo) gbm_bo_destroy(bo);
    if (gbm) gbm_device_destroy(gbm);
    if (exporter >= 0) close(exporter);
    if (saved) drmModeFreeCrtc(saved);
    if (resources) drmModeFreeResources(resources);
    if (master) drmDropMaster(fd);
    if (fd >= 0) close(fd);
    return result;
}
