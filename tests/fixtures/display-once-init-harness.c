/* Execute the real PID 1 with deterministic syscall failures; no real mounts. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <setjmp.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

static int mounts, fail_mount, executions, resets;
static bool wrong_id, wrong_release, unsafe_source, same_directory, invalid_target;
static jmp_buf executed;
#ifndef TRIAL_ROOT
#define TRIAL_ROOT "/var/lib/vim4-kvm/display-m1/"
#endif
static pid_t fake_pid(void) { return 1; }
static int fake_uname(struct utsname *value)
{
	strcpy(value->release, wrong_release ? "wrong" : "7.3.0-vim4kvm-uhd1+");
	return 0;
}
static ssize_t fake_link(const char *path, char *buffer, size_t size)
{
	const char *name = TRIAL_ROOT "1111111111111111111111111111111111111111/init";
	(void)path;
	assert(size > strlen(name));
	memcpy(buffer, name, strlen(name));
	return strlen(name);
}
static int fake_open(const char *path, int flags)
{
	assert(!strcmp(path, "/sys/kernel/notes") && (flags & O_CLOEXEC));
	return 42;
}
static ssize_t fake_read(int fd, void *buffer, size_t size)
{
	unsigned char notes[36] = { 4, 0, 0, 0, 20, 0, 0, 0, 3, 0, 0, 0, 'G', 'N', 'U', 0 };
	assert(fd == 42 && size >= sizeof(notes));
	memset(notes + 16, wrong_id ? 0x22 : 0x11, 20);
	memcpy(buffer, notes, sizeof(notes));
	return sizeof(notes);
}
static int fake_close(int fd) { assert(fd == 42); return 0; }
static int fake_stat(const char *path, struct stat *info)
{
	memset(info, 0, sizeof(*info));
	bool target = strstr(path, "/lib/modules/") != NULL;
	info->st_mode = (target && invalid_target ? S_IFREG : S_IFDIR) | 0555;
	/* Real baseline packages can preserve the Mac builder's UID 501. */
	info->st_uid = target ? 501 : unsafe_source;
	info->st_dev = 1;
	info->st_ino = strstr(path, "/lib/modules/") && !same_directory ? 2 : 1;
	return 0;
}
static int fake_mount(const char *source, const char *target, const char *type,
		      unsigned long flags, const void *data)
{
	(void)type; (void)data;
	mounts++;
	if (mounts == 3) {
		assert(strstr(source, "/modules/7.3.0-vim4kvm-uhd1+"));
		assert(!strcmp(target, "/lib/modules/7.3.0-vim4kvm-uhd1+"));
		assert(flags == MS_BIND);
	}
	if (mounts == 4)
		assert(flags == (MS_BIND | MS_REMOUNT | MS_RDONLY));
	errno = EIO;
	return mounts == fail_mount ? -1 : 0;
}
static int fake_exec(const char *path, const char *arg, ...)
{
	assert(mounts == 4 && !strcmp(path, "/sbin/init") && !strcmp(arg, path));
	executions++;
	longjmp(executed, 1);
}
static int fake_reboot(int command) { assert(command == RB_AUTOBOOT); resets++; return 0; }

#define getpid fake_pid
#define uname fake_uname
#define readlink fake_link
#define open fake_open
#define read fake_read
#define close fake_close
#define stat(path, info) fake_stat(path, info)
#define mount fake_mount
#define execl fake_exec
#define reboot fake_reboot
#define main trial_main
#include "../../packaging/kernel-edge/display-once-init.c"
#undef main

int main(void)
{
	for (int failure = 0; failure <= 9; failure++) {
		mounts = executions = resets = 0;
		fail_mount = failure <= 4 ? failure : 0;
		wrong_id = failure == 5;
		wrong_release = failure == 6;
		unsafe_source = failure == 7;
		same_directory = failure == 8;
		invalid_target = failure == 9;
		if (!setjmp(executed))
			assert(trial_main() == 1);
		assert(executions == (failure == 0));
		assert(resets == (failure != 0));
	}
	unsigned char truncated[12] = { 0xff, 0xff, 0xff, 0xff };
	assert(!matches_build(truncated, sizeof(truncated), "1111111111111111111111111111111111111111"));
	puts("PID1: build/release/ownership/alias checks and all four mount failures passed");
	return 0;
}
