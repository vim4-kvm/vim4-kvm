#!/usr/bin/env python3
"""Exercise actual V4L2 orphan/QBUF functions with a returning capture lease.

Usage: python3 test_gstreamer_orphan.py PATH/TO/gstv4l2bufferpool.c
No video device is opened. Requires a Linux C compiler and V4L2 headers.
The fake deactivation callback schedules the return exactly after stop(), the
interleaving which frame-rate-dependent board tests may otherwise miss.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def function(source, name):
    start = source.index('\n' + name + ' (') + 1
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


FIXTURE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <linux/videodev2.h>
typedef bool gboolean;
typedef int gint;
typedef unsigned int guint;
typedef uint32_t guint32;
typedef uint64_t guint64;
typedef uint64_t GstClockTime;
typedef int GstFlowReturn;
#define TRUE true
#define FALSE false
#define GST_FLOW_OK 0
#define GST_FLOW_ERROR -1
#define GST_FLOW_FLUSHING -2
#define BUFFER_STATE_QUEUED 2
#define GST_BUFFER_FLAG_TAG_MEMORY 1
#define GST_DEBUG_OBJECT(...) ((void)0)
#define GST_LOG_OBJECT(...) ((void)0)
#define GST_ERROR_OBJECT(...) ((void)0)
#define GST_V4L2_ALLOCATOR_CAN_ORPHAN_BUFS(a) ((a)->can_orphan)
#define GST_OBJECT_LOCK(p) lock(p)
#define GST_OBJECT_UNLOCK(p) unlock(p)
#define GST_BUFFER_TIMESTAMP_IS_VALID(b) false
#define GST_BUFFER_TIMESTAMP(b) 0
#define GST_TIME_TO_TIMEVAL(t,v) ((void)0)
#define GST_BUFFER_FLAG_SET(b,f) ((b)->flags |= (f))
#define g_atomic_int_or(p,v) atomic_or(p,v)
#define g_atomic_int_and(p,v) (*(p) &= (v))
#define g_atomic_int_inc(p) (++*(p))
#define g_atomic_int_add(p,v) (*(p) += (v))
#define g_cond_signal(p) ((void)0)
#define g_getenv getenv
typedef struct {unsigned flags;} GstBuffer;
typedef struct {struct v4l2_buffer buffer;} GstV4l2MemoryGroup;
typedef struct {bool can_orphan, fail; unsigned queued_refs;} Allocator;
typedef struct Pool GstV4l2BufferPool;
typedef struct Pool GstBufferPool;
typedef struct {GstBufferPool *pool; void *element; unsigned type;
                struct v4l2_format format;} GstV4l2Object;
struct Pool {GstV4l2Object *obj; Allocator *vallocator; bool orphaned, streaming,
             flushing, locked, active, empty; unsigned refs, returned;
             int buffer_state[32], num_queued, empty_cond; GstBuffer *buffers[32];};
#define GST_V4L2_BUFFER_POOL(p) (p)
static int atomic_or(int *p,int value) {int old=*p; *p |= value; return old;}
static void lock(GstBufferPool *p) {assert(!p->locked);p->locked=true;}
static void unlock(GstBufferPool *p) {assert(p->locked);p->locked=false;}
static GstBufferPool *gst_v4l2_object_get_buffer_pool(GstV4l2Object *obj) {
  if(obj->pool) obj->pool->refs++; return obj->pool;
}
static void gst_object_unref(GstBufferPool *pool) {assert(pool->refs);pool->refs--;}
static gboolean gst_v4l2_allocator_qbuf(Allocator *a,GstV4l2MemoryGroup *g) {
  (void)g; a->queued_refs++; return true;
}
static void gst_buffer_pool_set_flushing(GstBufferPool *pool,bool flushing) {
  assert(!pool->locked); pool->flushing=flushing;
}
static void gst_v4l2_buffer_pool_streamoff(GstBufferPool *pool) {
  if(!pool->streaming) return;
  pool->streaming=false;pool->vallocator->queued_refs=0;
}
static bool gst_v4l2_allocator_orphan(Allocator *a) {return !a->fail;}
static void gst_buffer_pool_set_active(GstBufferPool *pool,bool active);
/* ACTUAL FUNCTIONS */
static void gst_buffer_pool_set_active(GstBufferPool *pool,bool active) {
  assert(!pool->locked && !active);pool->active=active;
  if(!pool->orphaned) gst_v4l2_buffer_pool_streamoff(pool);
  /* An encoder returns a capture lease after stop() drained queued memory. */
  GstV4l2MemoryGroup group={0};GstBuffer buffer={0};
  if(!pool->returned++) gst_v4l2_buffer_pool_qbuf(pool,&buffer,&group,NULL);
}
static void run(bool fail) {
  Allocator allocator={.can_orphan=true,.fail=fail,.queued_refs=2};
  GstV4l2Object obj={.type=V4L2_BUF_TYPE_VIDEO_CAPTURE};
  GstBufferPool pool={.obj=&obj,.vallocator=&allocator,.streaming=true,
                     .active=true,.refs=1};
  obj.pool=&pool;obj.element=&pool;
  assert(gst_v4l2_buffer_pool_orphan(&obj) == !fail);
  if(!fail) {
    assert(obj.pool == NULL && pool.orphaned && pool.refs == 0);
    assert(allocator.queued_refs == 0 && "capture memory requeued after stop");
  } else {
    assert(obj.pool == &pool && !pool.orphaned && pool.refs == 1);
  }
  assert(!pool.streaming && !pool.active && !pool.locked);
}
int main(void) {
  unsetenv("GST_V4L2_FORCE_DRAIN");
  GstV4l2Object empty={0};assert(gst_v4l2_buffer_pool_orphan(&empty));
  Allocator allocator={0};GstV4l2Object obj={0};
  GstBufferPool pool={.obj=&obj,.vallocator=&allocator,.refs=1,.active=true};
  obj.pool=&pool;obj.element=&pool;
  assert(!gst_v4l2_buffer_pool_orphan(&obj));
  assert(pool.refs==1 && pool.active && !pool.returned);
  allocator.can_orphan=true;pool.orphaned=true;
  assert(!gst_v4l2_buffer_pool_orphan(&obj));
  assert(pool.refs==1 && pool.active && !pool.returned);
  pool.orphaned=false;setenv("GST_V4L2_FORCE_DRAIN","1",1);
  assert(!gst_v4l2_buffer_pool_orphan(&obj));
  assert(pool.refs==1 && pool.active && !pool.returned);
  unsetenv("GST_V4L2_FORCE_DRAIN");
  run(false);run(true);return 0;
}
'''


def main():
    source = Path(sys.argv[1]).read_text()
    functions = ('static GstFlowReturn\n' + function(source, 'gst_v4l2_buffer_pool_qbuf')
                 + '\nstatic gboolean\n' + function(source, 'gst_v4l2_buffer_pool_orphan'))
    fixture = FIXTURE.replace('/* ACTUAL FUNCTIONS */', functions)
    with tempfile.TemporaryDirectory() as directory:
        cfile = Path(directory) / 'orphan.c'
        binary = Path(directory) / 'orphan'
        cfile.write_text(fixture)
        subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra',
                        '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                        '-Wno-misleading-indentation', str(cfile), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('Late capture return and failed-orphan ownership checks passed')


if __name__ == '__main__':
    main()
