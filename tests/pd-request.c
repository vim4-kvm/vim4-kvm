/* Run on Linux: cc -Wall -Wextra -Werror tests/pd-request.c -o /tmp/pd-test && /tmp/pd-test */
#define main pd_program_main
#include "../tools/usb-pd-init.c"
#undef main
#include <assert.h>
#include <sys/wait.h>

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
