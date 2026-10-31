#!/usr/bin/env python3
"""Compile the actual runtime wrappers against strict host API models."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def check(source):
    driver = source / 'drivers/gpu/arm/midgard'
    for path in driver.rglob('*.c'):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
        if re.search(r'\b(?:hrtimer_(?:init|setup)(?:_on_stack)?|alloc_workqueue)\s*\(|\.function\s*=', text):
            raise ValueError(f'Unwrapped timer/workqueue API: {path}')
        if re.search(r'kbase_hrtimer_setup(?:_on_stack)?\s*\([^,]+,\s*(?:NULL|0)\s*,', text):
            raise ValueError(f'Timer callback must be provided at setup: {path}')
    header = (source / 'include/linux/version_compat_defs.h').read_text()
    block = header.split('/* KBASE_RUNTIME_COMPAT_BEGIN:')[1].split('*/', 1)[1]
    block = block.split('/* KBASE_RUNTIME_COMPAT_END */')[0]
    prefix = r'''
#include <assert.h>
#define KERNEL_VERSION(a,b,c) (((a)<<16)+((b)<<8)+(c))
#define WQ_UNBOUND 2
#define WQ_PERCPU 4
typedef int clockid_t;
enum hrtimer_restart { RESTART };
enum hrtimer_mode { REL };
struct hrtimer { enum hrtimer_restart (*function)(struct hrtimer *); };
static int stack;
static void hrtimer_setup(struct hrtimer *t, enum hrtimer_restart (*fn)(struct hrtimer *), clockid_t c, enum hrtimer_mode m) {
    assert(fn); assert(c == 1); assert(m == REL); t->function=fn;
}
#define hrtimer_setup_on_stack(t,f,c,m) (stack=1, hrtimer_setup(t,f,c,m))
#define hrtimer_init(t,c,m) ((void)(c), (void)(m), (t)->function=0)
#define hrtimer_init_on_stack(t,c,m) (stack=1, hrtimer_init(t,c,m))
'''
    suffix = r'''
static enum hrtimer_restart callback(struct hrtimer *t) { (void)t; return RESTART; }
int main(void) {
    struct hrtimer timer;
    kbase_hrtimer_setup(&timer, callback, 1, REL);
    assert(timer.function == callback && !stack);
    kbase_hrtimer_setup_on_stack(&timer, callback, 1, REL);
    assert(timer.function == callback && stack);
    assert(kbase_workqueue_flags(WQ_UNBOUND | 8) == (WQ_UNBOUND | 8));
#if LINUX_VERSION_CODE >= KERNEL_VERSION(7,3,0)
    assert(kbase_workqueue_flags(8) == (WQ_PERCPU | 8));
#else
    assert(kbase_workqueue_flags(8) == 8);
#endif
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='kbase-semantic-') as directory:
        root = Path(directory)
        program = root / 'check.c'
        # The old branch does not call hrtimer_setup; mark only the model unused.
        program.write_text(prefix.replace('static void hrtimer_setup', 'static void __attribute__((unused)) hrtimer_setup') + block + suffix)
        for version in ((5 << 16) + (15 << 8), (7 << 16) + (3 << 8)):
            executable = root / str(version)
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror',
                            '-DLINUX_VERSION_CODE=' + str(version), str(program),
                            '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
    print('Runtime wrappers: legacy/current host models and source API gate passed')
    check_t7_reset(driver)
    check_metrics_term(driver)


def check_metrics_term(driver):
    """Both enabled metrics configurations must stop the timer before release."""
    source = (driver / 'backend/gpu/mali_kbase_pm_metrics.c').read_text()
    function = 'void kbasep_pm_metrics_term' + source.split(
        'void kbasep_pm_metrics_term', 1)[1].split('\nKBASE_EXPORT_TEST_API', 1)[0]
    model = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#define MALI_USE_CSF 0
#define KBASE_DEBUG_ASSERT assert
#define TIMER_OFF 0
struct metrics { bool initialized; int timer_state, timer; };
struct kbase_device { struct { struct { struct metrics metrics; } backend; } pm; };
static struct metrics *owner;
static unsigned cancelled;
static void atomic_set(int *state, int value) { *state=value; }
static void hrtimer_cancel(int *timer) {
    assert(timer==&owner->timer);
    assert(!owner->initialized && owner->timer_state==TIMER_OFF);
    cancelled++;
}
'''
    exercise = r'''
int main(void) {
    struct kbase_device device = {0};
    owner=&device.pm.backend.metrics;
    owner->initialized=true; owner->timer_state=1;
    kbasep_pm_metrics_term(&device);
    assert(cancelled==1);
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='kbase-metrics-') as directory:
        program = Path(directory) / 'term.c'
        program.write_text(model + function + exercise)
        for configuration in ('CONFIG_MALI_DEVFREQ', 'CONFIG_MALI_MIDGARD_DVFS'):
            executable = Path(directory) / configuration
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-D' + configuration,
                            str(program), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


def check_t7_reset(driver):
    """Exercise the real quirk against a key-protected register model."""
    platform = (driver / 'platform/vim4/platform.c').read_text()
    function = 'void vim4_gpu_reset_complete' + platform.split(
        'void vim4_gpu_reset_complete', 1)[1].split('\nint kbase_platform_dvfs_event', 1)[0]
    model = r'''
#include <assert.h>
struct kbase_device { void *dev; };
#define GPU_CONTROL_REG(x) (x)
enum { PWR_KEY, PWR_OVERRIDE1 };
static unsigned int key, override;
static void kbase_reg_write(struct kbase_device *d, int reg, unsigned int value) {
    (void)d;
    if (reg == PWR_KEY) key = value;
    else { assert(key == 0x2968a819); override = value; key = 0; }
}
static unsigned int kbase_reg_read(struct kbase_device *d, int reg) {
    (void)d; assert(reg == PWR_OVERRIDE1); return override;
}
#define dev_info_once(d,fmt,value) ((void)(d), (void)(fmt), (void)(value))
'''
    exercise = r'''
int main(void) {
    struct kbase_device device = {0};
    for (int reset = 0; reset < 3; reset++) {
        key = override = 0;
        vim4_gpu_reset_complete(&device);
        assert(override == 0x200fff);
    }
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='kbase-reset-') as directory:
        program = Path(directory) / 'reset.c'
        executable = Path(directory) / 'reset'
        program.write_text(model + function + exercise)
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(program),
                        '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    print('T7 reset quirk: protected writes survive repeated reset model')


if __name__ == '__main__':
    check(Path(sys.argv[1]))
