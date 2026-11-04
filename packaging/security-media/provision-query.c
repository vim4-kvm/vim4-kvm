// SPDX-License-Identifier: MIT
/* Query only HDCP TX object metadata through the supplied vendor library. */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>

typedef int32_t (*query_fn)(uint8_t *, uint32_t, uint32_t, uint32_t *, uint32_t *);

int main(int argc, char **argv)
{
	const uint32_t types[] = { 0x31, 0x32 };
	const char *versions[] = { "1.4", "2.2" };
	void *library;
	query_fn query;
	int failed = 0;

	if (argc != 2) {
		fprintf(stderr, "Usage: %s /path/to/libprovision.so\n", argv[0]);
		return 2;
	}
	library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
	if (!library) {
		fprintf(stderr, "load library: %s\n", dlerror());
		return 1;
	}
	query = (query_fn)dlsym(library, "key_provision_query");
	if (!query) {
		fprintf(stderr, "query API: %s\n", dlerror());
		dlclose(library);
		return 1;
	}
	for (unsigned int i = 0; i < 2; i++) {
		uint32_t storage = 0, size = 0;
		uint32_t result = (uint32_t)query(NULL, 0, types[i], &storage, &size);

		printf("query HDCP TX %s: result=0x%08x", versions[i], result);
		if (!result)
			printf(" storage=0x%08x size=%u", storage, size);
		else
			failed = 1;
		putchar('\n');
	}
	dlclose(library);
	return failed;
}
