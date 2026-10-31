"""Run the actual policy against idle, sustained and intermittent load histories."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('cc'), 'requires host C compiler')
class GovernorTest(unittest.TestCase):
    def test_frequency_steps_and_low_load_hold(self):
        source = (ROOT / 'packaging/kbase/dvfs/governor_vim4.c').read_text()
        state = 'struct vim4_state {' + source.split('struct vim4_state {', 1)[1]
        state = state.split('static int vim4_event', 1)[0]
        arrays = '\n'.join(line for line in source.splitlines()
                           if line.startswith(('static unsigned int keep_count',
                                               'static unsigned int up_threshold',
                                               'static unsigned int down_threshold')))
        model = r'''
#include <assert.h>
#include <stdint.h>
typedef uint64_t u64;
#define max_t(t,a,b) ((t)(a) > (t)(b) ? (t)(a) : (t)(b))
#define div64_u64(a,b) ((a)/(b))
struct devfreq_dev_status { unsigned long busy_time, total_time, current_frequency; };
struct devfreq { void *governor_data; struct devfreq_dev_status last_status; unsigned long *freq_table; };
static int devfreq_update_stats(struct devfreq *df) { (void)df; return 0; }
'''
        exercise = r'''
int main(void) {
    unsigned long table[] = {250, 400, 500, 666, 800}, next;
    struct vim4_state state = {0};
    struct devfreq df = {.governor_data=&state, .freq_table=table,
        .last_status={.busy_time=100, .total_time=100, .current_frequency=250}};
    for (unsigned int i=1; i<5; i++) {
        assert(!vim4_target(&df, &next));
        assert(next == table[i]); df.last_status.current_frequency=next;
    }
    assert(!vim4_target(&df, &next) && next==800);
    df.last_status.busy_time=0;
    for (unsigned int i=0; i<5; i++) {
        assert(!vim4_target(&df, &next)); assert(next==800);
    }
    assert(!vim4_target(&df, &next) && next==666);
    df.last_status.current_frequency=666;
    /* A mid-band sample refreshes the hold count. */
    df.last_status.busy_time=40;
    assert(!vim4_target(&df, &next) && next==666);
    assert(state.hold==5);
    df.last_status.busy_time=0;
    for (unsigned int i=0; i<24; i++) {
        assert(!vim4_target(&df, &next));
        df.last_status.current_frequency=next;
    }
    assert(next==250);
    assert(!vim4_target(&df, &next) && next==250);
    /* r44 actually supplies its OPP table in descending order. */
    unsigned long descending[] = {800, 666, 500, 400, 250};
    df.freq_table=descending; df.last_status.busy_time=100;
    for (unsigned int i=1; i<5; i++) {
        assert(!vim4_target(&df, &next));
        assert(next==table[i]); df.last_status.current_frequency=next;
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / 'policy.c'
            executable = Path(directory) / 'policy'
            program.write_text(model + arrays + '\n' + state + exercise)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(program), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
