/* SPDX-License-Identifier: GPL-2.0 */
/* Copyright (C) 2017 Amlogic, Inc. All rights reserved. */
static void mali_decide_next_status(int utilization_pp, int* next_fs_idx,
		int* pp_change_flag)
{
	u32 mali_up_limit, decided_fs_idx;
	u32 ld_left, ld_right;
	u32 ld_up, ld_down;
	u32 change_mode;

	*pp_change_flag = 0;
	change_mode = 0;

	scalingdbg(5, "line(%d), scaling_mode=%d, MALI_TURBO_MODE=%d, turbo=%d, maxclk=%d\n",
			__LINE__,  scaling_mode, MALI_TURBO_MODE,
		    pmali_plat->turbo_clock, pmali_plat->scale_info.maxclk);

	mali_up_limit = (scaling_mode ==  MALI_TURBO_MODE) ?
		pmali_plat->turbo_clock : pmali_plat->scale_info.maxclk;
	decided_fs_idx = currentStep;

	ld_up = pmali_plat->dvfs_table[currentStep].upthreshold;
	ld_down = pmali_plat->dvfs_table[currentStep].downthreshold;

	scalingdbg(2, "utilization=%d,  ld_up=%d\n ", utilization_pp,  ld_up);
	if (utilization_pp >= ld_up) { /* go up */

		scalingdbg(2, "currentStep=%d,  mali_up_limit=%d\n ", currentStep, mali_up_limit);
		if (currentStep < mali_up_limit) {
			change_mode = 1;
			if ((currentStep < pmali_plat->def_clock) && (utilization_pp > pmali_plat->bst_gpu))
				decided_fs_idx = pmali_plat->def_clock;
			else
				decided_fs_idx++;
		}
		if ((utilization_pp >= ld_up) &&
				(num_cores_enabled < pmali_plat->scale_info.maxpp)) {
			if ((num_cores_enabled < pmali_plat->sc_mpp) && (utilization_pp >= pmali_plat->bst_pp)) {
				*pp_change_flag = 1;
				change_mode = 1;
			} else if (change_mode == 0) {
				*pp_change_flag = 2;
				change_mode = 1;
			}
		}
#if LOG_MALI_SCALING
		scalingdbg(2, "[nexting..] [LD:%d]-> FS[CRNT:%d LMT:%d NEXT:%d] PP[NUM:%d LMT:%d MD:%d][F:%d]\n",
				utilization_pp, currentStep, mali_up_limit, decided_fs_idx,
				num_cores_enabled, pmali_plat->scale_info.maxpp, *pp_change_flag, change_mode);
#endif
	} else if (utilization_pp <= ld_down) { /* go down */
		if (mali_stay_count > 0) {
			*next_fs_idx = decided_fs_idx;
			mali_stay_count--;
			return;
		}

		if (num_cores_enabled > pmali_plat->sc_mpp) {
			change_mode = 1;
			if (utilization_pp <= ld_down) {
				ld_left = utilization_pp * num_cores_enabled;
				ld_right = (pmali_plat->dvfs_table[currentStep].upthreshold) *
					(num_cores_enabled - 1);
				if (ld_left < ld_right) {
					change_mode = 2;
				}
			}
		} else if (currentStep > pmali_plat->scale_info.minclk) {
			change_mode = 1;
		} else if (num_cores_enabled > 1) { /* decrease PPS */
			if (utilization_pp <= ld_down) {
				ld_left = utilization_pp * num_cores_enabled;
				ld_right = (pmali_plat->dvfs_table[currentStep].upthreshold) *
					(num_cores_enabled - 1);
				scalingdbg(2, "ld_left=%d, ld_right=%d\n", ld_left, ld_right);
				if (ld_left < ld_right) {
					change_mode = 2;
				}
			}
		}

		if (change_mode == 1) {
			decided_fs_idx--;
		} else if (change_mode == 2) { /* decrease PPS */
			*pp_change_flag = -1;
		}
	} else {
		mali_stay_count = pmali_plat->dvfs_table[currentStep].keep_count;
		scalingdbg(1, "reset to %d, decided_fs_idx=%d, mali_stay_count=%d\n",
				currentStep, decided_fs_idx, mali_stay_count);
	}

	if (decided_fs_idx < 0 ) {
		printk("gpu debug, next index below 0\n");
		decided_fs_idx = 0;
	}
	if (decided_fs_idx > pmali_plat->scale_info.maxclk) {
		decided_fs_idx = pmali_plat->scale_info.maxclk;
		printk("gpu debug, next index above max-1, set to %d\n", decided_fs_idx);
	}

	if (change_mode)
		mali_stay_count = pmali_plat->dvfs_table[decided_fs_idx].keep_count;

	*next_fs_idx = decided_fs_idx;
	scalingdbg(1, "mali_stay_count=%d\n", mali_stay_count);
}
