"""Differential regression against the GPL vendor DVFS state machine."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('cc'), 'requires host C compiler')
class GovernorTest(unittest.TestCase):
    def test_vendor_load_frequency_and_logical_pp_decisions(self):
        source = (ROOT / 'packaging/kbase/dvfs/governor_vim4.c').read_text()
        arrays = '\n'.join(line for line in source.splitlines() if line.startswith(
            ('static unsigned int keep_count', 'static unsigned int boost_',
             'static unsigned int up_threshold', 'static unsigned int down_threshold')))
        policy = 'struct vim4_state {' + source.split('struct vim4_state {', 1)[1]
        policy = policy.split('static int vim4_event', 1)[0]
        vendor = (ROOT / 'tests/fixtures/kbase-vendor-scaling.c').read_text()
        model = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
typedef uint64_t u64;
typedef unsigned int u32;
#define max_t(t,a,b) ((t)(a) > (t)(b) ? (t)(a) : (t)(b))
#define div64_u64(a,b) ((a)/(b))
#define scalingdbg(...) ((void)0)
#define printk(...) ((void)0)
#define MALI_TURBO_MODE 3
static unsigned scaling_mode=1,currentStep,num_cores_enabled,mali_stay_count;
struct threshold { unsigned upthreshold,downthreshold,keep_count; };
struct platform {
 unsigned turbo_clock,def_clock,bst_gpu,bst_pp,sc_mpp;
 struct {unsigned maxclk,minclk,maxpp;} scale_info;
 struct threshold *dvfs_table;
};
static struct platform *pmali_plat;
struct devfreq_dev_status { unsigned long busy_time,total_time,current_frequency; };
struct devfreq { void *governor_data; struct devfreq_dev_status last_status; unsigned long *freq_table; };
static int devfreq_update_stats(struct devfreq *df) { (void)df; return 0; }
'''
        exercise = r'''
int main(void) {
 unsigned long table[]={250,400,500,666,800},reverse[]={800,666,500,400,250},next;
 struct threshold thresholds[5];
 for(unsigned i=0;i<5;i++) thresholds[i]=(struct threshold){up_threshold[i],down_threshold[i],5};
 struct platform plat={.def_clock=4,.bst_gpu=210,.bst_pp=160,.sc_mpp=1,
  .scale_info={.maxclk=4,.minclk=0,.maxpp=4},.dvfs_table=thresholds};
 pmali_plat=&plat;
 for(unsigned order=0;order<2;order++)
 for(unsigned level=0;level<5;level++)
 for(unsigned pp=1;pp<=4;pp++)
 for(unsigned hold=0;hold<=5;hold++)
 for(unsigned percent=0;percent<=100;percent++) {
  struct vim4_state state={.hold=hold,.logical_pp=pp};
  struct devfreq df={.governor_data=&state,.freq_table=order?reverse:table,
   .last_status={.busy_time=percent,.total_time=100,.current_frequency=table[level]}};
  currentStep=level;num_cores_enabled=pp;mali_stay_count=hold;
  int index,change;
  mali_decide_next_status(percent*255/100,&index,&change);
  if(change==1) num_cores_enabled=plat.sc_mpp;
  else if(change==2) num_cores_enabled++;
  else if(change==-1) num_cores_enabled--;
  assert(!vim4_target(&df,&next));
  assert(next==table[index]);assert(state.hold==mali_stay_count);
  assert(state.logical_pp==num_cores_enabled);
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / 'policy.c'
            executable = Path(directory) / 'policy'
            program.write_text(model + arrays + '\n' + policy + vendor + exercise)
            subprocess.run(['cc', '-std=c11', str(program), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
