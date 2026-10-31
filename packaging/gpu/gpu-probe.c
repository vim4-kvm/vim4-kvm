/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <fcntl.h>
#include <gbm.h>
#include <libdrm/drm.h>
#include <linux/videodev2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

static int fail(const char *stage)
{
 int saved_errno = errno;
 const char *loader = dlerror();
 fprintf(stderr, "%s failed: errno=%d (%s), EGL=0x%x GL=0x%x dlerror=%s\n",
         stage, saved_errno, strerror(saved_errno), eglGetError(), glGetError(),
         loader ? loader : "none");
 return 2;
}

static void origin(const char *name, const void *symbol)
{
 Dl_info info;
 fprintf(stderr, "%s provider=%s\n", name,
         dladdr(symbol, &info) ? info.dli_fname : "unknown");
}

static double now(void)
{
 struct timespec t;
 clock_gettime(CLOCK_MONOTONIC, &t);
 return t.tv_sec + t.tv_nsec / 1e9;
}

static int wave5_import(int dma, uint32_t stride, uint32_t uv_offset, off_t bytes)
{
 const char *device = getenv("GPU_WAVE5_DEVICE");
 if (!device) return 0;
 int fd = open(device, O_RDWR | O_NONBLOCK | O_CLOEXEC);
 if (fd < 0) return fail("open Wave5");
 int result = 2;
 struct v4l2_capability cap = {0};
 if (ioctl(fd, VIDIOC_QUERYCAP, &cap) || strncmp((char *)cap.driver, "wave5", 5)) {
  fail("expected Wave5 QUERYCAP"); goto done;
 }
 struct v4l2_format capture = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE};
 capture.fmt.pix_mp.width = 256; capture.fmt.pix_mp.height = 256;
 capture.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_H264;
 if (ioctl(fd, VIDIOC_S_FMT, &capture)) { fail("Wave5 capture S_FMT"); goto done; }
 struct v4l2_format raw = {.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE};
 raw.fmt.pix_mp.width = 256; raw.fmt.pix_mp.height = 256;
 raw.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_NV12;
 raw.fmt.pix_mp.num_planes = 1;
 raw.fmt.pix_mp.plane_fmt[0].bytesperline = stride;
 if (ioctl(fd, VIDIOC_S_FMT, &raw)) { fail("Wave5 raw S_FMT"); goto done; }
 if (raw.fmt.pix_mp.pixelformat != V4L2_PIX_FMT_NV12 || raw.fmt.pix_mp.num_planes != 1 ||
     raw.fmt.pix_mp.width != 256 || raw.fmt.pix_mp.height != 256 ||
     raw.fmt.pix_mp.plane_fmt[0].bytesperline != stride || uv_offset != stride * 256 ||
     bytes < raw.fmt.pix_mp.plane_fmt[0].sizeimage) {
  fprintf(stderr, "Wave5 negotiated layout differs from GBM metadata; refusing import\n"); goto done;
 }
 struct v4l2_requestbuffers request = {.count = 1, .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE,
                                     .memory = V4L2_MEMORY_DMABUF};
 if (ioctl(fd, VIDIOC_REQBUFS, &request)) { fail("Wave5 REQBUFS"); goto done; }
 struct v4l2_plane plane = {.bytesused = raw.fmt.pix_mp.plane_fmt[0].sizeimage,
                           .length = (uint32_t)bytes, .m.fd = dma};
 struct v4l2_buffer buffer = {.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE,
                             .memory = V4L2_MEMORY_DMABUF, .index = 0,
                             .length = 1, .m.planes = &plane};
 if (ioctl(fd, VIDIOC_QBUF, &buffer)) { fail("Wave5 DMABUF QBUF"); goto done; }
 puts("GBM NV12 BO accepted by Wave5 DMABUF QBUF; no STREAMON/encoded output tested");
 result = 0;
done:
 close(fd);
 return result;
}

static int export_bo(struct gbm_device *gbm, const char *drm_device)
{
 const char *mode = getenv("GPU_GBM_EXPORT");
 uint32_t flags = GBM_BO_USE_RENDERING;
 uint32_t format = GBM_FORMAT_ARGB8888;
 if (!strcmp(mode, "linear")) flags |= GBM_BO_USE_LINEAR;
 else if (!strcmp(mode, "scanout")) { flags = GBM_BO_USE_SCANOUT; format = GBM_FORMAT_XRGB8888; }
 else if (!strcmp(mode, "nv12")) format = GBM_FORMAT_NV12;
 fprintf(stderr, "GBM export format=%#x flags=%#x\n", format, flags);
 struct gbm_bo *bo = gbm_bo_create(gbm, 256, 256, format, flags);
 if (!bo) return fail("gbm_bo_create(export smoke)");
 int fd = gbm_bo_get_fd(bo);
 if (fd < 0 && !strcmp(mode, "nv12")) {
  int (*plane_fd)(struct gbm_bo *, int) = dlsym(RTLD_DEFAULT, "gbm_bo_get_fd_for_plane");
  if (plane_fd) fd = plane_fd(bo, 0);
 }
 if (fd < 0) { gbm_bo_destroy(bo); return fail("gbm_bo_get_fd"); }
 if (!strcmp(mode, "nv12")) {
  int (*planes)(struct gbm_bo *) = dlsym(RTLD_DEFAULT, "gbm_bo_get_plane_count");
  uint64_t (*modifier)(struct gbm_bo *) = dlsym(RTLD_DEFAULT, "gbm_bo_get_modifier");
  uint32_t (*offset)(struct gbm_bo *, int) = dlsym(RTLD_DEFAULT, "gbm_bo_get_offset");
  uint32_t (*stride)(struct gbm_bo *, int) = dlsym(RTLD_DEFAULT, "gbm_bo_get_stride_for_plane");
  printf("NV12 BO bytes=%lld metadata_api=%s\n", (long long)lseek(fd, 0, SEEK_END),
         planes && modifier && offset && stride ? "available" : "incomplete");
  if (planes && modifier && offset && stride) {
   int count = planes(bo);
   printf("NV12 BO planes=%d modifier=%llu\n", count, (unsigned long long)modifier(bo));
   if (count < 1 || count > 4) { close(fd); gbm_bo_destroy(bo); return fail("GBM plane count"); }
   for (int plane = 0; plane < count; plane++)
    printf("plane=%d offset=%u stride=%u\n", plane, offset(bo, plane), stride(bo, plane));
   if (getenv("GPU_WAVE5_DEVICE")) {
    int (*plane_fd)(struct gbm_bo *, int) = dlsym(RTLD_DEFAULT, "gbm_bo_get_fd_for_plane");
    off_t bytes = lseek(fd, 0, SEEK_END);
    if (!plane_fd || count != 2 || modifier(bo) != 0 || offset(bo, 0) != 0 ||
        stride(bo, 0) != stride(bo, 1) || bytes <= 0 || bytes > UINT32_MAX) {
     fprintf(stderr, "NV12 linear single-buffer layout not established\n"); close(fd); gbm_bo_destroy(bo); return 2;
    }
    int y = plane_fd(bo, 0), uv = plane_fd(bo, 1);
    struct stat base_stat, y_stat, uv_stat;
    int same = y >= 0 && uv >= 0 && !fstat(fd, &base_stat) && !fstat(y, &y_stat) && !fstat(uv, &uv_stat) &&
               base_stat.st_dev == y_stat.st_dev && base_stat.st_ino == y_stat.st_ino &&
               base_stat.st_dev == uv_stat.st_dev && base_stat.st_ino == uv_stat.st_ino;
    if (y >= 0) close(y);
    if (uv >= 0) close(uv);
    if (!same) { fprintf(stderr, "NV12 planes do not identify the same DMA buffer\n"); close(fd); gbm_bo_destroy(bo); return 2; }
    int imported = wave5_import(fd, stride(bo, 0), offset(bo, 1), bytes);
    if (imported) { close(fd); gbm_bo_destroy(bo); return imported; }
   }
  } else if (getenv("GPU_WAVE5_DEVICE")) {
   fprintf(stderr, "NV12 metadata incomplete; refusing Wave5 layout guess\n"); close(fd); gbm_bo_destroy(bo); return 2;
  }
 }
 /* A separate DRM file owns the imported handle independently of GBM. */
 int importer = open(drm_device, O_RDWR | O_CLOEXEC);
 if (importer < 0) { close(fd); gbm_bo_destroy(bo); return fail("open display importer"); }
 struct drm_prime_handle prime = { .fd = fd };
 int result = ioctl(importer, DRM_IOCTL_PRIME_FD_TO_HANDLE, &prime);
 if (result) result = fail("display DRM PRIME_FD_TO_HANDLE");
 else {
  printf("GBM BO exported/imported to display DRM: handle=%u stride=%u; no scanout/encoder tested\n",
         prime.handle, gbm_bo_get_stride(bo));
  struct drm_gem_close release = { .handle = prime.handle };
  if (ioctl(importer, DRM_IOCTL_GEM_CLOSE, &release)) result = fail("DRM GEM_CLOSE");
 }
 close(importer); close(fd); gbm_bo_destroy(bo);
 return result;
}

static GLuint shader(GLenum type, const char *source)
{
 GLuint s = glCreateShader(type);
 GLint ok;
 glShaderSource(s, 1, &source, NULL);
 glCompileShader(s);
 glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
 if (!ok) { char log[2048]; glGetShaderInfoLog(s, sizeof(log), NULL, log); fprintf(stderr, "glCompileShader: %s\n", log); exit(fail("glCompileShader")); }
 return s;
}

int main(int argc, char **argv)
{
 char *end = NULL;
 double requested = argc > 1 ? strtod(argv[1], &end) : 10;
 if (argc > 3 || (argc > 1 && (!end || *end || end == argv[1] ||
     !(requested >= 0 && requested <= 60)))) {
  fprintf(stderr, "Usage: gpu-probe SECONDS[0..60] [DRM_DEVICE]\n");
  return 2;
 }
 fprintf(stderr, "uid=%u euid=%u LD_LIBRARY_PATH=%s\n", getuid(), geteuid(),
         getenv("LD_LIBRARY_PATH") ? getenv("LD_LIBRARY_PATH") : "(unset)");
 origin("eglInitialize", eglInitialize); origin("glGetString", glGetString);
 origin("gbm_create_device", gbm_create_device);
 const EGLint config_attrs[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE};
 const EGLint gbm_attrs[] = {EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE};
 const EGLint surface_attrs[] = {EGL_WIDTH, 512, EGL_HEIGHT, 512, EGL_NONE};
 const EGLint context_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
 EGLDisplay display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
 struct gbm_device *gbm = NULL;
 int drm_fd = -1;
 /* Some vendor libraries support GBM but not Mesa's surfaceless platform. */
 if (argc > 2) {
  drm_fd = open(argv[2], O_RDWR | O_CLOEXEC);
  if (drm_fd < 0) return fail("open DRM device");
  errno = 0;
  gbm = gbm_create_device(drm_fd);
  if (!gbm) return fail("gbm_create_device");
  PFNEGLGETPLATFORMDISPLAYEXTPROC get_display = (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
  if (!get_display) return fail("eglGetProcAddress(eglGetPlatformDisplayEXT)");
  display = get_display(EGL_PLATFORM_GBM_KHR, gbm, NULL);
  if (display == EGL_NO_DISPLAY) return fail("eglGetPlatformDisplayEXT");
 }
 EGLConfig config;
 EGLint count, major, minor;
 if (!eglInitialize(display, &major, &minor)) return fail("eglInitialize");
 printf("EGL %d.%d vendor=%s extensions=%s\n", major, minor, eglQueryString(display, EGL_VENDOR), eglQueryString(display, EGL_EXTENSIONS));
 if (!eglBindAPI(EGL_OPENGL_ES_API)) return fail("eglBindAPI");
 if (!eglChooseConfig(display, gbm ? gbm_attrs : config_attrs, &config, 1, &count)) return fail("eglChooseConfig");
 if (count != 1) return fail("eglChooseConfig(count != 1)");
 EGLSurface surface = gbm ? EGL_NO_SURFACE : eglCreatePbufferSurface(display, config, surface_attrs);
 EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attrs);
 if (!gbm && surface == EGL_NO_SURFACE) return fail("eglCreatePbufferSurface");
 if (context == EGL_NO_CONTEXT) return fail("eglCreateContext");
 if (!eglMakeCurrent(display, surface, surface, context)) return fail("eglMakeCurrent");
 printf("GL vendor=%s renderer=%s version=%s extensions=%s\n", glGetString(GL_VENDOR), glGetString(GL_RENDERER), glGetString(GL_VERSION), glGetString(GL_EXTENSIONS));
 GLuint framebuffer = 0, texture = 0;
 if (gbm) {
  /* GBM configs need not support pbuffers; render into a fixed-size FBO. */
  glGenTextures(1, &texture); glBindTexture(GL_TEXTURE_2D, texture);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 512, 512, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
  glGenFramebuffers(1, &framebuffer); glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
  glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
  if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) return fail("glCheckFramebufferStatus");
 }
 GLuint program = glCreateProgram();
 glAttachShader(program, shader(GL_VERTEX_SHADER, "attribute vec2 position;void main(){gl_Position=vec4(position,0.,1.);}"));
 const char *fragment = "precision highp float;void main(){vec2 p=gl_FragCoord.xy/512.;float v=p.x;for(int i=0;i<128;i++)v=fract(v*1.01+p.y*0.01);gl_FragColor=vec4(v,p.y,0.5,1.);}";
 char unrolled[8192] = "precision highp float;void main(){vec2 p=gl_FragCoord.xy/512.;float v=p.x;";
 if (getenv("GPU_UNROLL128")) {
  /* Diagnostic A/B: same 128 dependent operations, without a loop branch. */
  for (int i = 0; i < 128; i++) strcat(unrolled, "v=fract(v*1.01+p.y*0.01);");
  strcat(unrolled, "gl_FragColor=vec4(v,p.y,0.5,1.);}");
  fragment = unrolled;
 }
 glAttachShader(program, shader(GL_FRAGMENT_SHADER, fragment));
 printf("shader_variant=%s\n", getenv("GPU_UNROLL128") ? "explicit-128" : "loop-128");
 glBindAttribLocation(program, 0, "position");
 glLinkProgram(program);
 GLint ok;
 glGetProgramiv(program, GL_LINK_STATUS, &ok);
 if (!ok) {
  char log[2048]; glGetProgramInfoLog(program, sizeof(log), NULL, log);
  fprintf(stderr, "glLinkProgram: %s\n", log); return fail("glLinkProgram");
 }
 glUseProgram(program);
 const GLfloat vertices[] = {-1,-1,3,-1,-1,3};
 glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, vertices);
 glEnableVertexAttribArray(0);
 glViewport(0, 0, 512, 512);
 /* Exclude lazy compilation, first-use allocations and initial DVFS ramp. */
 double warmup = now();
 do { glDrawArrays(GL_TRIANGLES, 0, 3); glFinish(); } while (now() - warmup < 2.0);
 GLint red_bits, green_bits, blue_bits, alpha_bits;
 glGetIntegerv(GL_RED_BITS, &red_bits); glGetIntegerv(GL_GREEN_BITS, &green_bits);
 glGetIntegerv(GL_BLUE_BITS, &blue_bits); glGetIntegerv(GL_ALPHA_BITS, &alpha_bits);
 printf("surface=%s rgba_bits=%d,%d,%d,%d warmup_seconds=2 swap_calls=0\n",
        gbm ? "gbm-fbo" : "pbuffer", red_bits, green_bits, blue_bits, alpha_bits);
 unsigned frames = 0;
 PFNGLGENQUERIESEXTPROC gen_query = NULL;
 PFNGLBEGINQUERYEXTPROC begin_query = NULL;
 PFNGLENDQUERYEXTPROC end_query = NULL;
 PFNGLGETQUERYOBJECTUI64VEXTPROC query_result = NULL;
 PFNGLDELETEQUERIESEXTPROC delete_query = NULL;
 GLuint query = 0;
 unsigned long long gpu_ns = 0;
 if (getenv("GPU_TIMER_QUERY") && strstr((const char *)glGetString(GL_EXTENSIONS), "GL_EXT_disjoint_timer_query")) {
  gen_query = (PFNGLGENQUERIESEXTPROC)eglGetProcAddress("glGenQueriesEXT");
  begin_query = (PFNGLBEGINQUERYEXTPROC)eglGetProcAddress("glBeginQueryEXT");
  end_query = (PFNGLENDQUERYEXTPROC)eglGetProcAddress("glEndQueryEXT");
  query_result = (PFNGLGETQUERYOBJECTUI64VEXTPROC)eglGetProcAddress("glGetQueryObjectui64vEXT");
  delete_query = (PFNGLDELETEQUERIESEXTPROC)eglGetProcAddress("glDeleteQueriesEXT");
  if (!gen_query || !begin_query || !end_query || !query_result || !delete_query) return fail("timer query entrypoints");
  gen_query(1, &query);
  /* Discard disjoint events during context creation and warmup. */
  GLint initial_disjoint = 0;
  glGetIntegerv(GL_GPU_DISJOINT_EXT, &initial_disjoint);
  printf("gpu_initial_disjoint=%d\n", initial_disjoint);
 }
 double draw_seconds = 0, finish_seconds = 0;
 struct timespec cpu_start, cpu_end;
 clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &cpu_start);
 double start = now(), seconds = requested;
 do {
  if (query) begin_query(GL_TIME_ELAPSED_EXT, query);
  double a = now(); glDrawArrays(GL_TRIANGLES, 0, 3);
  double b = now();
  if (query) end_query(GL_TIME_ELAPSED_EXT);
  glFinish(); double c = now();
  if (query) { GLuint64EXT value; query_result(query, GL_QUERY_RESULT_EXT, &value); gpu_ns += value; }
  draw_seconds += b-a; finish_seconds += c-b; frames++;
 } while (now() - start < seconds);
 double elapsed = now() - start;
 clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &cpu_end);
 double read_start = now();
 unsigned char pixel[4];
 glReadPixels(256, 256, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
 double read_seconds = now() - read_start;
 const char *dump_path = getenv("GPU_DUMP_PATH");
 if (dump_path) {
  size_t bytes = 512u * 512u * 4u;
  unsigned char *pixels = malloc(bytes);
  if (!pixels) return fail("allocate pixel dump");
  glReadPixels(0, 0, 512, 512, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
  FILE *dump = fopen(dump_path, "wb");
  if (!dump) { free(pixels); return fail("open pixel dump"); }
  int failed = fwrite(pixels, 1, bytes, dump) != bytes;
  if (fclose(dump)) failed = 1;
  free(pixels);
  if (failed) return fail("write pixel dump");
 }
 GLenum error = glGetError();
 printf("size=512x512 frames=%u seconds=%.6f pixel=%u,%u,%u,%u gl_error=%u\n", frames, elapsed, pixel[0], pixel[1], pixel[2], pixel[3], error);
 printf("steady_seconds=%.9f draw_seconds=%.9f finish_seconds=%.9f readback_seconds=%.9f cpu_seconds=%.9f\n",
        elapsed, draw_seconds, finish_seconds, read_seconds,
        cpu_end.tv_sec-cpu_start.tv_sec+(cpu_end.tv_nsec-cpu_start.tv_nsec)/1e9);
 if (query) {
  GLint disjoint = 0; glGetIntegerv(GL_GPU_DISJOINT_EXT, &disjoint);
  printf("gpu_query_ns=%llu gpu_disjoint=%d timer_frames=%u\n", gpu_ns, disjoint, frames);
  delete_query(1, &query);
 }
 glDeleteFramebuffers(1, &framebuffer); glDeleteTextures(1, &texture);
 eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
 eglDestroyContext(display, context);
 if (surface != EGL_NO_SURFACE) eglDestroySurface(display, surface);
 eglTerminate(display);
 int export_result = gbm && getenv("GPU_GBM_EXPORT") ? export_bo(gbm, argv[2]) : 0;
 if (gbm) gbm_device_destroy(gbm);
 if (drm_fd >= 0) close(drm_fd);
 if (error != GL_NO_ERROR || pixel[1] < 120 || pixel[1] > 136 || pixel[2] < 120 || pixel[2] > 136)
  return fail("render pixel/GL validation");
 return export_result;
}
