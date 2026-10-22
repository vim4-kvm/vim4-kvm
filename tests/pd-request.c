/* Run on Linux: cc -Wall -Wextra -Werror tests/pd-request.c -o /tmp/pd-test && /tmp/pd-test */
#define main pd_program_main
#include "../tools/usb-pd-init.c"
#undef main
#include <assert.h>
#include <sys/wait.h>
#include <sys/stat.h>

static void adapter(const char *root, int bus, const char *node)
{
	char path[PATH_MAX];
	snprintf(path, sizeof(path), "%s/i2c-%d", root, bus);
	assert(mkdir(path, 0700) == 0);
	snprintf(path, sizeof(path), "%s/i2c-%d/device", root, bus);
	assert(mkdir(path, 0700) == 0);
	snprintf(path, sizeof(path), "%s/i2c-%d/device/of_node", root, bus);
	assert(symlink(node, path) == 0);
}

static void controller_discovery(void)
{
	char root[] = "/tmp/vim4-pd-test-XXXXXX";
	char parent[PATH_MAX], node[PATH_MAX], pattern[PATH_MAX];
	assert(mkdtemp(root));
	snprintf(parent, sizeof(parent), "%s/bus@fe000000", root);
	assert(mkdir(parent, 0700) == 0);
	snprintf(node, sizeof(node), "%s/bus@fe000000/i2c@76000", root);
	assert(mkdir(node, 0700) == 0);
	adapter(root, 6, parent); /* An unrelated adapter must never be probed. */
	adapter(root, 1, node);
	snprintf(pattern, sizeof(pattern), "%s/i2c-*/device/of_node", root);
	assert(controller_bus(pattern) == 1);
	adapter(root, 2, node);
	assert(controller_bus(pattern) == -1); /* Ambiguous hardware: fail closed. */
	for (int bus = 1; bus <= 6; bus++) {
		if (bus != 1 && bus != 2 && bus != 6) continue;
		snprintf(pattern, sizeof(pattern), "%s/i2c-%d/device/of_node", root, bus);
		assert(unlink(pattern) == 0);
		snprintf(pattern, sizeof(pattern), "%s/i2c-%d/device", root, bus);
		assert(rmdir(pattern) == 0);
		snprintf(pattern, sizeof(pattern), "%s/i2c-%d", root, bus);
		assert(rmdir(pattern) == 0);
	}
	assert(rmdir(node) == 0);
	assert(rmdir(parent) == 0);
	assert(rmdir(root) == 0);
}

static void rejected(uint32_t pdo)
{
	pid_t child = fork();
	assert(child >= 0);
	if (!child) { request_5v(pdo); _exit(0); }
	int status;
	assert(waitpid(child, &status, 0) == child);
	assert(WIFEXITED(status) && WEXITSTATUS(status) == EXIT_FAILURE);
}

int main(void)
{
	controller_discovery();
	/* Requests respect source current, cap at 3A, and advertise USB data. */
	assert(request_5v(0x3e019096) == 0x13025896);
	assert(request_5v(0x3e01912c) == 0x1304b12c);
	assert(request_5v((100u << 10) | 500) == 0x1304b12c);
	rejected((180u << 10) | 300); /* 9V must never be requested. */
	rejected((1u << 30) | (100u << 10) | 300);
	rejected(100u << 10); /* Zero current. */
	puts("PD request boundary tests passed");
	return 0;
}
