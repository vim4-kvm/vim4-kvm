/* SPDX-License-Identifier: MIT */
/* Offline loader check: take addresses, never initialize EGL or access a GPU. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int check(const char *library, const char *name, const char *expected)
{
	Dl_info info;
	char actual[PATH_MAX];
	void *handle = dlopen(library, RTLD_NOW | RTLD_LOCAL);
	void *symbol;
	int failed;

	if (!handle) {
		fprintf(stderr, "%s: %s\n", library, dlerror());
		return 1;
	}
	symbol = dlsym(handle, name);
	if (!symbol || !dladdr(symbol, &info) || !realpath(info.dli_fname, actual)) {
		dlclose(handle);
		return 1;
	}
	printf("%s: %s\n", name, actual);
	failed = strcmp(actual, expected) != 0;
	dlclose(handle);
	return failed;
}

int main(int argc, char **argv)
{
	char expected[PATH_MAX];
	int failed = 0;

	if (argc != 2 || !realpath(argv[1], expected))
		return 2;
	failed |= check("libEGL.so.1", "eglInitialize", expected);
	failed |= check("libEGL.so.1", "eglGetProcAddress", expected);
	failed |= check("libEGL.so.1", "eglMakeCurrent", expected);
	failed |= check("libGLESv2.so.2", "glGetString", expected);
	failed |= check("libgbm.so.1", "gbm_create_device", expected);
	return failed;
}
