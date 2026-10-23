/* SPDX-License-Identifier: GPL-2.0-only */
/* Static PID 1 for a RAM-selected display trial; never changes boot files. */
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

#define RELEASE "7.3.0-vim4kvm-uhd1+"
#define MODULES "/lib/modules/" RELEASE
#define TRIAL_ROOT "/var/lib/vim4-kvm/display-m1/"

static uint32_t little32(const unsigned char *p)
{
	return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 |
	       (uint32_t)p[3] << 24;
}

static bool matches_build(const unsigned char *notes, size_t size, const char *id)
{
	static const char hex[] = "0123456789abcdef";
	size_t offset = 0;
	unsigned int found = 0;

	while (size - offset >= 12) {
		uint32_t name = little32(notes + offset);
		uint32_t desc = little32(notes + offset + 4);
		uint32_t type = little32(notes + offset + 8);
		size_t padded_name = ((uint64_t)name + 3) & ~3ULL;
		size_t padded_desc = ((uint64_t)desc + 3) & ~3ULL;

		offset += 12;
		if (padded_name > size - offset)
			return false;
		if (padded_desc > size - offset - padded_name)
			return false;
		if (name == 4 && !memcmp(notes + offset, "GNU\0", 4) && type == 3) {
			if (desc != 20 || found++)
				return false;
			for (unsigned int i = 0; i < desc; i++) {
				unsigned char value = notes[offset + padded_name + i];

				if (id[2 * i] != hex[value >> 4] ||
				    id[2 * i + 1] != hex[value & 15])
					return false;
			}
		}
		offset += padded_name + padded_desc;
	}
	return found == 1 && offset == size;
}

static bool trusted_directory(const char *path, struct stat *info)
{
	return !stat(path, info) && S_ISDIR(info->st_mode) &&
	       info->st_uid == 0 && !(info->st_mode & 022);
}

int main(void)
{
	unsigned char notes[65536];
	char executable[1024], source[1200], id[41];
	struct stat source_info, target_info;
	struct utsname kernel;
	ssize_t length, size;
	char *directory;
	const char *step = "mount proc";
	int fd;

	if (getpid() != 1)
		return 2;
	/* Root storage and its drivers are built in, as in the baseline no-initrd boot. */
	if (mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) &&
	    errno != EBUSY)
		goto fail;
	step = "mount sysfs";
	if (mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) &&
	    errno != EBUSY)
		goto fail;
	step = "kernel release";
	if (uname(&kernel) || strcmp(kernel.release, RELEASE))
		goto fail;
	step = "executable path";
	length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
	if (length <= 0 || length >= (ssize_t)sizeof(executable) - 1)
		goto fail;
	executable[length] = '\0';
	if (strncmp(executable, TRIAL_ROOT, strlen(TRIAL_ROOT)))
		goto fail;
	directory = executable + strlen(TRIAL_ROOT);
	if (strlen(directory) != 45 || strcmp(directory + 40, "/init"))
		goto fail;
	memcpy(id, directory, 40);
	id[40] = '\0';
	for (unsigned int i = 0; i < 40; i++)
		if (!((id[i] >= '0' && id[i] <= '9') || (id[i] >= 'a' && id[i] <= 'f')))
			goto fail;
	step = "kernel build ID";
	fd = open("/sys/kernel/notes", O_RDONLY | O_CLOEXEC);
	if (fd < 0)
		goto fail;
	size = read(fd, notes, sizeof(notes));
	close(fd);
	if (size <= 0 || size == (ssize_t)sizeof(notes) || !matches_build(notes, size, id))
		goto fail;
	/* Separate storage, same release: existing KVM launchers remain applicable. */
	*strrchr(executable, '/') = '\0';
	step = "candidate directory";
	if (!trusted_directory(executable, &source_info))
		goto fail;
	if (snprintf(source, sizeof(source), "%s/modules/%s", executable, RELEASE) >=
	    (int)sizeof(source))
		goto fail;
	step = "module directories";
	/* The existing mountpoint can retain a package builder's numeric owner.
	 * Only the private source supplies modules; validate its ownership strictly.
	 */
	if (!trusted_directory(source, &source_info) ||
	    stat(MODULES, &target_info) || !S_ISDIR(target_info.st_mode) ||
	    (source_info.st_dev == target_info.st_dev && source_info.st_ino == target_info.st_ino))
		goto fail;
	step = "bind modules";
	if (mount(source, MODULES, NULL, MS_BIND, NULL))
		goto fail;
	step = "read-only modules";
	if (mount(NULL, MODULES, NULL, MS_BIND | MS_REMOUNT | MS_RDONLY, NULL))
		goto fail;
	puts("DISPLAY_ONCE: matching modules mounted; starting systemd");
	fflush(stdout);
	step = "exec systemd";
	execl("/sbin/init", "/sbin/init", (char *)NULL);
fail:
	/* No candidate userspace with baseline modules; the default boot is untouched. */
	fprintf(stderr, "DISPLAY_ONCE: %s failed (errno=%d); reboot to the retained baseline\n",
		step, errno);
	reboot(RB_AUTOBOOT);
	return 1;
}
