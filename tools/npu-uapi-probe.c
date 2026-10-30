// SPDX-License-Identifier: GPL-2.0
/* Build with -I KERNEL/drivers/misc/adla/drv/uapi{,/linux}.
 * Run under a <=30s timeout and the board/media locks. No inference or MMIO.
 * Exercises driver-allocated physical import and PROFILE_CFG error rollback.
 */
#include <stdint.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/utsname.h>
#include <unistd.h>
#include "adlak_api.h"

int main(int argc, char **argv)
{
	struct adlak_buf_req original = { .bytes = 4096, .align_in_page = 1,
		.mem_type = 3, .mmap_en = 1 };
	struct adlak_extern_buf_info imported = {0};
	struct adlak_profile_cfg_desc profile = { .net_register_idx = -1 };
	struct adlak_context_attribute attribute = {0};
	int fd, status = 1;

	if (argc != 2 || (strcmp(argv[1], "attach") && strcmp(argv[1], "profile")))
		return 2;
	if (!strcmp(argv[1], "profile")) {
		struct utsname system;

		/* Vendor 5.15 leaves its context mutex locked on this error path. */
		if (uname(&system) || !strncmp(system.release, "5.15.", 5)) {
			fprintf(stderr, "negative PROFILE_CFG requires the corrected candidate driver\n");
			return 2;
		}
	}
	fd = open("/dev/adla0", O_RDWR | O_CLOEXEC);
	if (fd < 0)
		return 1;
	/* The SDK establishes its MMU context before the first allocation. */
	if (ioctl(fd, ADLAK_IOCTL_SET_CONTEXT_ATTRIBUTE, &attribute))
		goto out;
	if (!strcmp(argv[1], "profile")) {
		/* Missing network must fail and release the context mutex each time. */
		for (int i = 0; i < 2; i++)
			if (ioctl(fd, ADLAK_IOCTL_PROFILE_CFG, &profile) >= 0 || !profile.errcode)
				goto out;
		status = 0;
		goto out;
	}
	if (ioctl(fd, ADLAK_IOCTL_REQBUF, &original) || original.errcode ||
	    !original.ret_desc.phys_addr || !original.ret_desc.va_user)
		goto out;
	memset((void *)(uintptr_t)original.ret_desc.va_user, 0x5a, 4096);
	imported.buf_handle = original.ret_desc.phys_addr;
	imported.bytes = 4096;
	imported.mem_type = 3;
	imported.mmap_en = 1;
	if (ioctl(fd, ADLAK_IOCTL_ATTACH_EXTERN_BUF, &imported) || imported.errcode ||
	    !imported.ret_desc.va_user)
		goto free_original;
	status = memcmp((void *)(uintptr_t)original.ret_desc.va_user,
			(void *)(uintptr_t)imported.ret_desc.va_user, 4096) != 0;
	if (ioctl(fd, ADLAK_IOCTL_DETTACH_EXTERN_BUF, &imported.mem_handle))
		status = 1;
free_original:
	if (ioctl(fd, ADLAK_IOCTL_FREEBUF, &original.mem_handle))
		status = 1;
out:
	close(fd);
	printf("%s status=%d\n", argv[1], status);
	return status;
}
