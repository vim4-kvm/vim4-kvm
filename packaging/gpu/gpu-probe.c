/* SPDX-License-Identifier: MIT */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <fcntl.h>
#include <gbm.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static double now(void)
{
 struct timespec t;
 clock_gettime(CLOCK_MONOTONIC, &t);
 return t.tv_sec + t.tv_nsec / 1e9;
}

static GLuint shader(GLenum type, const char *source)
{
 GLuint s = glCreateShader(type);
 GLint ok;
 glShaderSource(s, 1, &source, NULL);
 glCompileShader(s);
 glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
 if (!ok) { char log[2048]; glGetShaderInfoLog(s, sizeof(log), NULL, log); fprintf(stderr, "%s\n", log); exit(2); }
 return s;
}

int main(int argc, char **argv)
{
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
  if (drm_fd < 0 || !(gbm = gbm_create_device(drm_fd))) return 2;
  PFNEGLGETPLATFORMDISPLAYEXTPROC get_display = (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
  if (!get_display) return 2;
  display = get_display(EGL_PLATFORM_GBM_KHR, gbm, NULL);
 }
 EGLConfig config;
 EGLint count, major, minor;
 if (!eglInitialize(display, &major, &minor)) { fprintf(stderr, "eglInitialize: 0x%x\n", eglGetError()); return 2; }
 printf("EGL %d.%d vendor=%s extensions=%s\n", major, minor, eglQueryString(display, EGL_VENDOR), eglQueryString(display, EGL_EXTENSIONS));
 if (!eglBindAPI(EGL_OPENGL_ES_API) || !eglChooseConfig(display, gbm ? gbm_attrs : config_attrs, &config, 1, &count) || count != 1) return 2;
 EGLSurface surface = gbm ? EGL_NO_SURFACE : eglCreatePbufferSurface(display, config, surface_attrs);
 EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attrs);
 if (!eglMakeCurrent(display, surface, surface, context)) return 2;
 printf("GL vendor=%s renderer=%s version=%s extensions=%s\n", glGetString(GL_VENDOR), glGetString(GL_RENDERER), glGetString(GL_VERSION), glGetString(GL_EXTENSIONS));
 GLuint framebuffer = 0, texture = 0;
 if (gbm) {
  /* GBM configs need not support pbuffers; render into a fixed-size FBO. */
  glGenTextures(1, &texture); glBindTexture(GL_TEXTURE_2D, texture);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 512, 512, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
  glGenFramebuffers(1, &framebuffer); glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
  glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
  if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) return 2;
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
 if (!ok) return 2;
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
  if (!gen_query || !begin_query || !end_query || !query_result || !delete_query) return 2;
  gen_query(1, &query);
  /* Discard disjoint events during context creation and warmup. */
  GLint initial_disjoint = 0;
  glGetIntegerv(GL_GPU_DISJOINT_EXT, &initial_disjoint);
  printf("gpu_initial_disjoint=%d\n", initial_disjoint);
 }
 double draw_seconds = 0, finish_seconds = 0;
 struct timespec cpu_start, cpu_end;
 clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &cpu_start);
 double start = now(), seconds = argc > 1 ? atof(argv[1]) : 10;
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
 if (gbm) gbm_device_destroy(gbm);
 if (drm_fd >= 0) close(drm_fd);
 return error != GL_NO_ERROR || pixel[1] < 120 || pixel[1] > 136 || pixel[2] < 120 || pixel[2] > 136;
}
