/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include <EGL/egl.h>
#include <GLES3/gl31.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void require(int ok, const char *why)
{
    if (!ok) { fprintf(stderr, "%s\n", why); exit(1); }
}
static unsigned dimension(const char *s)
{
    char *end;
    unsigned long value = strtoul(s, &end, 10);
    require(*s && !*end && value >= 2 && value <= 4096 && !(value % 2), "invalid even dimension");
    return value;
}
static double now(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}
int main(int argc, char **argv)
{
    require(argc == 8, "usage: hdr-probe shader iw ih ow oh input.p010 output.nv12");
    unsigned iw=dimension(argv[2]), ih=dimension(argv[3]);
    unsigned ow=dimension(argv[4]), oh=dimension(argv[5]);
    require(!(ow%4) && ow<=iw && oh<=ih && ih<=2160, "output width must be multiple of 4; downscale only; max height 2160");
    size_t in_bytes=(size_t)iw*ih*3, out_bytes=(size_t)ow*oh*3/2;
    FILE *f=fopen(argv[6],"rb"); require(f!=NULL,"open P010 input failed");
    void *input=malloc(in_bytes); require(input!=NULL,"input allocation failed");
    require(fread(input,1,in_bytes,f)==in_bytes && fgetc(f)==EOF,"P010 size mismatch"); fclose(f);
    f=fopen(argv[1],"rb"); require(f!=NULL,"open shader failed");
    char shader[16384]; size_t n=fread(shader,1,sizeof(shader)-1,f);
    require(fgetc(f)==EOF,"shader too large"); shader[n]=0; fclose(f);
    EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY);
    require(eglInitialize(display,NULL,NULL),"EGL initialization failed");
    require(eglBindAPI(EGL_OPENGL_ES_API),"EGL bind API failed");
    EGLint attrs[]={EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_NONE};
    EGLConfig config; EGLint count;
    require(eglChooseConfig(display,attrs,&config,1,&count) && count,"no ES3 config");
    EGLint context_attrs[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};
    EGLContext ctx=eglCreateContext(display,config,EGL_NO_CONTEXT,context_attrs);
    require(ctx!=EGL_NO_CONTEXT && eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,ctx),"surfaceless ES3 context failed");
    const char *renderer=(const char *)glGetString(GL_RENDERER);
    printf("renderer=%s version=%s\n",renderer,glGetString(GL_VERSION));
    require(strstr(renderer,"Mali-G52") || getenv("GPU_HDR_ALLOW_SOFTWARE"),"expected Mali-G52; software allowed only for offline validation");
    GLint limit; glGetIntegerv(GL_MAX_SHADER_STORAGE_BLOCK_SIZE,&limit);
    require(in_bytes<=(size_t)limit && out_bytes<=(size_t)limit,"SSBO limit exceeded");
    GLuint cs=glCreateShader(GL_COMPUTE_SHADER); const char *source=shader;
    glShaderSource(cs,1,&source,NULL); glCompileShader(cs);
    GLint ok; char log[8192]; glGetShaderiv(cs,GL_COMPILE_STATUS,&ok);
    glGetShaderInfoLog(cs,sizeof(log),NULL,log); require(ok,log);
    GLuint program=glCreateProgram(); glAttachShader(program,cs); glLinkProgram(program);
    glGetProgramiv(program,GL_LINK_STATUS,&ok); glGetProgramInfoLog(program,sizeof(log),NULL,log); require(ok,log);
    glUseProgram(program);
    glUniform2i(glGetUniformLocation(program,"input_size"),(GLint)iw,(GLint)ih);
    glUniform2i(glGetUniformLocation(program,"output_size"),(GLint)ow,(GLint)oh);
    GLuint buffers[2]; glGenBuffers(2,buffers);
    for (unsigned i=0;i<2;i++) {
        glBindBuffer(GL_SHADER_STORAGE_BUFFER,buffers[i]);
        glBufferData(GL_SHADER_STORAGE_BUFFER,i?out_bytes:in_bytes,i?NULL:input,GL_DYNAMIC_COPY);
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER,i,buffers[i]);
    }
    free(input);
    const char *setting=getenv("GPU_HDR_FRAMES"); char *end=NULL;
    long frames=setting?strtol(setting,&end,10):1;
    require(frames>=1 && frames<=600 && (!setting || (*setting && !*end)),"invalid GPU_HDR_FRAMES (1..600)");
    double start=0, maximum=0;
    for (long i=-3;i<frames;i++) {
        if (!i) start=now();
        double a=now();
        glDispatchCompute((ow/4+7)/8,(oh/2+7)/8,1);
        glMemoryBarrier(GL_BUFFER_UPDATE_BARRIER_BIT); glFinish();
        double elapsed=now()-a;
        if (i>=0 && elapsed>maximum) maximum=elapsed;
    }
    printf("frames=%ld mean_ms=%.6f max_ms=%.6f input=%ux%u output=%ux%u\n",
           frames,(now()-start)*1000/frames,maximum*1000,iw,ih,ow,oh);
    glBindBuffer(GL_SHADER_STORAGE_BUFFER,buffers[1]);
    void *output=glMapBufferRange(GL_SHADER_STORAGE_BUFFER,0,out_bytes,GL_MAP_READ_BIT);
    require(output!=NULL && glGetError()==GL_NO_ERROR,"GPU execution/map failed");
    f=fopen(argv[7],"wb"); require(f!=NULL,"open output failed");
    require(fwrite(output,1,out_bytes,f)==out_bytes,"short NV12 write"); require(!fclose(f),"close output failed");
    require(glUnmapBuffer(GL_SHADER_STORAGE_BUFFER),"unmap failed");
    glDeleteBuffers(2,buffers); glDeleteProgram(program); glDeleteShader(cs);
    eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);
    eglDestroyContext(display,ctx); eglTerminate(display);
    return 0;
}
