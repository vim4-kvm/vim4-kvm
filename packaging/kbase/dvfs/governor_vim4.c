// SPDX-License-Identifier: GPL-2.0
/* T7 frequency steps expressed through devfreq, including thermal QoS caps. */
#include <linux/devfreq.h>
#include <linux/devfreq-governor.h>
#include <linux/math64.h>
#include <linux/module.h>
#include <linux/slab.h>

static unsigned int period_ms = 100;
module_param(period_ms, uint, 0444);
MODULE_PARM_DESC(period_ms, "T7 GPU load sampling period in milliseconds");
static unsigned int keep_count = 5;
static unsigned int boost_level = 4;
static unsigned int boost_threshold = 210;
module_param(boost_level, uint, 0444);
module_param(boost_threshold, uint, 0444);
MODULE_PARM_DESC(boost_level, "Vendor live DT def_clk fallback, ascending OPP index");
MODULE_PARM_DESC(boost_threshold, "Vendor burst jump threshold on 0..255 scale");
module_param(keep_count, uint, 0444);
MODULE_PARM_DESC(keep_count, "Low-load samples to hold after a frequency change");
static unsigned int up_threshold[5] = { 76, 120, 120, 120, 255 };
static unsigned int down_threshold[5] = { 0, 80, 80, 80, 80 };
module_param_array(up_threshold, uint, NULL, 0444);
module_param_array(down_threshold, uint, NULL, 0444);
MODULE_PARM_DESC(up_threshold, "Ascending OPP up thresholds on vendor 0..255 scale");
MODULE_PARM_DESC(down_threshold, "Ascending OPP down thresholds on vendor 0..255 scale");

struct vim4_state {
	unsigned int hold;
	/* Vendor PP setters are hardware no-ops, but this count affects DVFS. */
	unsigned int logical_pp;
};

static unsigned long vim4_frequency(struct devfreq *df, unsigned int level)
{
	/* r44 supplies descending entries; devfreq also accepts ascending OPPs. */
	if (df->freq_table[0] > df->freq_table[4])
		level = 4 - level;
	return df->freq_table[level];
}

static int vim4_target(struct devfreq *df, unsigned long *frequency)
{
	struct vim4_state *state = df->governor_data;
	struct devfreq_dev_status *status;
	unsigned int level = 0, next, load;
	bool changed = false;
	int err = devfreq_update_stats(df);

	if (err)
		return err;
	status = &df->last_status;
	/* Match kbase's integer percent followed by the platform's 255 scale. */
	load = div64_u64((u64)status->busy_time * 100,
			 max_t(u64, status->total_time, 1)) * 255 / 100;
	while (level < 4 && vim4_frequency(df, level) < status->current_frequency)
		level++;
	next = level;
	if (load >= up_threshold[level]) {
		if (level < 4) {
			next = level < boost_level && load > boost_threshold ?
				boost_level : level + 1;
			changed = true;
		}
		if (state->logical_pp < 4 && !changed) {
			state->logical_pp++;
			changed = true;
		}
	} else if (load <= down_threshold[level]) {
		if (state->hold)
			state->hold--;
		else if (state->logical_pp > 1 &&
			 load * state->logical_pp <
			 up_threshold[level] * (state->logical_pp - 1)) {
			state->logical_pp--;
			changed = true;
		} else if (level) {
			next--;
			changed = true;
		}
	} else {
		state->hold = keep_count;
	}
	if (changed)
		state->hold = keep_count;
	*frequency = vim4_frequency(df, next);
	return 0;
}

static int vim4_event(struct devfreq *df, unsigned int event, void *data)
{
	switch (event) {
	case DEVFREQ_GOV_START:
		if (df->max_state != 5)
			return -EINVAL;
		df->governor_data = kzalloc_obj(struct vim4_state);
		if (!df->governor_data)
			return -ENOMEM;
		((struct vim4_state *)df->governor_data)->logical_pp = 1;
		df->profile->polling_ms = period_ms;
		/*
		 * Vendor metrics use a periodic hrtimer even when CPUs are idle.
		 * Deferrable polling can leave a short burst with stale idle stats.
		 */
		df->profile->timer = DEVFREQ_TIMER_DELAYED;
		devfreq_monitor_start(df);
		break;
	case DEVFREQ_GOV_STOP:
		devfreq_monitor_stop(df);
		kfree(df->governor_data);
		df->governor_data = NULL;
		break;
	case DEVFREQ_GOV_UPDATE_INTERVAL:
		devfreq_update_interval(df, data);
		break;
	case DEVFREQ_GOV_SUSPEND:
		devfreq_monitor_suspend(df);
		break;
	case DEVFREQ_GOV_RESUME:
		devfreq_monitor_resume(df);
		break;
	}
	return 0;
}

static struct devfreq_governor vim4_governor = {
	.name = "vim4",
	.attrs = DEVFREQ_GOV_ATTR_POLLING_INTERVAL | DEVFREQ_GOV_ATTR_TIMER,
	.get_target_freq = vim4_target,
	.event_handler = vim4_event,
};

static int __init vim4_governor_init(void)
{
	unsigned int i;

	if (!period_ms || boost_level > 4 || boost_threshold > 255)
		return -EINVAL;
	for (i = 0; i < 5; i++)
		if (up_threshold[i] > 255 || down_threshold[i] > up_threshold[i])
			return -EINVAL;
	return devfreq_add_governor(&vim4_governor);
}
module_init(vim4_governor_init);

static void __exit vim4_governor_exit(void)
{
	devfreq_remove_governor(&vim4_governor);
}
module_exit(vim4_governor_exit);
MODULE_DESCRIPTION("VIM4 T7 five-step GPU devfreq policy");
MODULE_LICENSE("GPL");
