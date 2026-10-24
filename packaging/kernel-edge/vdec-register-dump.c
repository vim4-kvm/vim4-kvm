/* SPDX-License-Identifier: MIT */
/* A read-only T7 snapshot reader. Invoke under the board and heavy locks. */
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static bool allowed(uint64_t addr)
{
	if (addr & 3)
		return false;
	if (addr >= 0xfe000000 && addr < 0xfe002000)
		return true; /* The complete CLKCTRL aperture, including reserved words. */
	if ((addr >= 0xfe00c040 && addr <= 0xfe00c0a4) ||
	    addr == 0xfe00c000 || addr == 0xfe00c004 ||
	    addr == 0xfe00c010 || addr == 0xfe00c014 ||
	    addr == 0xfe00c020 || addr == 0xfe00c024 ||
	    addr == 0xfe00c030 || addr == 0xfe00c034)
		return true;
	if ((addr >= 0xfe010280 && addr <= 0xfe01029c) ||
	    (addr >= 0xfe010300 && addr <= 0xfe01037c) ||
	    addr == 0xfe010500 || addr == 0xfe010520 || addr == 0xfe010524)
		return true;
	if ((addr >= 0xfe034380 && addr <= 0xfe03439c) ||
	    (addr >= 0xfe036380 && addr <= 0xfe03639c))
		return true; /* Vendor dmc_t7.c's protection-control read list. */
	return addr == 0xfe32fc00 || addr == 0xfe32fc04 || addr == 0xfe32fcc0;
}

int main(int argc, char **argv)
{
	bool vendor;
	FILE *plan;
	int fd;
	char line[128];
	unsigned int count = 0;
	unsigned int planned = 0;
	long page_size = sysconf(_SC_PAGESIZE);

	if (argc != 3 || (strcmp(argv[1], "--devmem") && strcmp(argv[1], "--vendor-paddr"))) {
		fprintf(stderr, "usage: %s --devmem|--vendor-paddr addresses.txt\n", argv[0]);
		return 2;
	}
	vendor = !strcmp(argv[1], "--vendor-paddr");
	plan = fopen(argv[2], "r");
	if (!plan) {
		perror("plan");
		return 1;
	}
	/* Validate the entire plan before opening either hardware interface. */
	while (fgets(line, sizeof(line), plan)) {
		char *end;
		uint64_t addr = strtoull(line, &end, 0);
		if (!allowed(addr) || (*end != '\n' && *end != '\0')) {
			fprintf(stderr, "refusing address line: %s", line);
			return 2;
		}
		planned++;
	}
	if (ferror(plan) || !planned || page_size <= 0)
		return 1;
	rewind(plan);
	fd = open(vendor ? "/sys/kernel/debug/aml_reg/paddr" : "/dev/mem",
		  vendor ? O_WRONLY | O_CLOEXEC : O_RDONLY | O_SYNC | O_CLOEXEC);
	if (fd < 0) {
		perror("physical read interface");
		return 1;
	}
	setvbuf(stdout, NULL, _IOLBF, 0);
	while (fgets(line, sizeof(line), plan)) {
		uint64_t addr = strtoull(line, NULL, 0);
		uint32_t value;

		printf("{\"begin\":\"0x%08" PRIx64 "\"}\n", addr);
		if (vendor) {
			char request[32], result[80];
			uint64_t echoed;
			int len = snprintf(request, sizeof(request), "%" PRIx64, addr);
			int read_fd;
			ssize_t got;
			/* One token caches an address; never supply a hardware write value. */
			if (write(fd, request, len) != len)
				return 1;
			/* debugfs need not implement llseek; use a fresh read offset. */
			read_fd = open("/sys/kernel/debug/aml_reg/paddr", O_RDONLY | O_CLOEXEC);
			if (read_fd < 0)
				return 1;
			got = read(read_fd, result, sizeof(result) - 1);
			if (close(read_fd))
				return 1;
			if (got <= 0)
				return 1;
			result[got] = 0;
			if (sscanf(result, "[0x%" SCNx64 "] = 0x%" SCNx32, &echoed, &value) != 2 ||
			    echoed != addr)
				return 1;
		} else {
			uint64_t base = addr / page_size * page_size;
			void *map = mmap(NULL, page_size, PROT_READ, MAP_SHARED, fd, base);
			if (map == MAP_FAILED) {
				perror("read-only mmap");
				return 1;
			}
			/* Exactly one aligned 32-bit load, no speculative bulk copy. */
			value = *(volatile const uint32_t *)((const char *)map + addr - base);
			if (munmap(map, page_size))
				return 1;
		}
		printf("{\"address\":\"0x%08" PRIx64 "\",\"value\":\"0x%08" PRIx32 "\"}\n", addr, value);
		count++;
	}
	if (ferror(plan) || close(fd) || fclose(plan))
		return 1;
	printf("{\"complete\":%u}\n", count);
	return 0;
}
