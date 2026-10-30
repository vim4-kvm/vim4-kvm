/* SPDX-License-Identifier: MIT */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

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
 const EGLint surface_attrs[] = {EGL_WIDTH, 512, EGL_HEIGHT, 512, EGL_NONE};
 const EGLint context_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
 EGLDisplay display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
 EGLConfig config;
 EGLint count, major, minor;
 if (!eglInitialize(display, &major, &minor)) { fprintf(stderr, "eglInitialize: 0x%x\n", eglGetError()); return 2; }
 printf("EGL %d.%d vendor=%s extensions=%s\n", major, minor, eglQueryString(display, EGL_VENDOR), eglQueryString(display, EGL_EXTENSIONS));
 if (!eglBindAPI(EGL_OPENGL_ES_API) || !eglChooseConfig(display, config_attrs, &config, 1, &count) || count != 1) return 2;
 EGLSurface surface = eglCreatePbufferSurface(display, config, surface_attrs);
 EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attrs);
 if (!eglMakeCurrent(display, surface, surface, context)) return 2;
 printf("GL vendor=%s renderer=%s version=%s extensions=%s\n", glGetString(GL_VENDOR), glGetString(GL_RENDERER), glGetString(GL_VERSION), glGetString(GL_EXTENSIONS));
 GLuint program = glCreateProgram();
 glAttachShader(program, shader(GL_VERTEX_SHADER, "attribute vec2 position;void main(){gl_Position=vec4(position,0.,1.);}"));
 glAttachShader(program, shader(GL_FRAGMENT_SHADER, "precision highp float;void main(){vec2 p=gl_FragCoord.xy/512.;float v=p.x;for(int i=0;i<128;i++)v=fract(v*1.01+p.y*0.01);gl_FragColor=vec4(v,p.y,0.5,1.);}"));
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
 unsigned frames = 0;
 double start = now(), seconds = argc > 1 ? atof(argv[1]) : 10;
 do { glDrawArrays(GL_TRIANGLES, 0, 3); glFinish(); frames++; } while (now() - start < seconds);
 unsigned char pixel[4];
 glReadPixels(256, 256, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
 GLenum error = glGetError();
 printf("size=512x512 frames=%u seconds=%.6f pixel=%u,%u,%u,%u gl_error=%u\n", frames, now()-start, pixel[0], pixel[1], pixel[2], pixel[3], error);
 eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
 eglDestroyContext(display, context); eglDestroySurface(display, surface); eglTerminate(display);
 return error != GL_NO_ERROR || pixel[1] < 120 || pixel[1] > 136 || pixel[2] < 120 || pixel[2] > 136;
}
