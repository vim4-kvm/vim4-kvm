/* Boot-time FUSB302B handoff for VIM4: advertise a 5V USB-capable sink.
 * Requires U-Boot to have initialized the attached sink/PD PHY.
 * This bounded bootstrap is not a general Type-C connection manager.
 * Do not run alongside a kernel TCPM driver or another PD controller.
 */
#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <limits.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/file.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define ADDR 0x22
#define R_SWITCHES1 0x03
#define R_CONTROL0 0x06
#define R_CONTROL1 0x07
#define R_STATUS0A 0x3c
#define R_INTA 0x3e
#define R_INTB 0x3f
#define R_STATUS0 0x40
#define R_STATUS1 0x41
#define R_INT 0x42
#define R_FIFO 0x43

#define SOP1 0x12
#define SOP2 0x13
#define PACKSYM 0x80
#define JAMCRC 0xff
#define EOP 0x14
#define TXOFF 0xfe
#define TXON 0xa1

static int fd;
static int txid;
static int contract_ready;
static unsigned requested_ma;
static uint32_t requested_rdo;
#define LOG(...) do { printf(__VA_ARGS__); fflush(stdout); } while (0)

/* Adapter numbers differ between kernels. Match the board's AO-A controller,
 * never probe unrelated I2C buses or take ownership from a kernel driver.
 */
static int controller_bus(const char *pattern)
{
	glob_t paths = { 0 };
	int bus = -1;
	if (glob(pattern, 0, NULL, &paths) != 0) {
		globfree(&paths);
		return -1;
	}
	for (size_t i = 0; i < paths.gl_pathc; i++) {
		char resolved[PATH_MAX];
		const char *path = paths.gl_pathv[i];
		if (!realpath(path, resolved) ||
		    (!strstr(resolved, "/bus@fe000000/i2c@76000") &&
		     !strstr(resolved, "/apb4@fe000000/i2c@76000")))
			continue;
		const char *name = NULL, *part = path;
		while ((part = strstr(part, "/i2c-")) != NULL) {
			name = part++;
		}
		int candidate;
		if (!name || sscanf(name, "/i2c-%d/device/of_node", &candidate) != 1 || candidate < 0)
			continue;
		if (bus >= 0) { bus = -1; break; }
		bus = candidate;
	}
	globfree(&paths);
	return bus;
}

static void fail(const char *message)
{
	fprintf(stderr, "%s\n", message);
	exit(EXIT_FAILURE);
}

static int rd(uint8_t reg, uint8_t *buf, int n)
{
	struct i2c_msg m[2] = {
		{ ADDR, 0, 1, &reg },
		{ ADDR, I2C_M_RD, n, buf },
	};
	struct i2c_rdwr_ioctl_data d = { m, 2 };
	int result = ioctl(fd, I2C_RDWR, &d);
	if (result != 2) { perror("I2C read"); exit(EXIT_FAILURE); }
	return result;
}

static uint8_t rd1(uint8_t reg)
{
	uint8_t v = 0;
	rd(reg, &v, 1);
	return v;
}

static int wr(uint8_t reg, const uint8_t *buf, int n)
{
	uint8_t b[64];
	struct i2c_msg m = { ADDR, 0, n + 1, b };
	struct i2c_rdwr_ioctl_data d = { &m, 1 };
	b[0] = reg;
	memcpy(b + 1, buf, n);
	int result = ioctl(fd, I2C_RDWR, &d);
	if (result != 1) { perror("I2C write"); exit(EXIT_FAILURE); }
	return result;
}

static void wr1(uint8_t reg, uint8_t v) { wr(reg, &v, 1); }

static double now_ms(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec * 1e3 + t.tv_nsec / 1e6;
}

static int send(uint16_t hdr, const uint32_t *obj, int n)
{
	uint8_t b[48];
	int i = 0, k;
	double t0;

	wr1(R_CONTROL0, rd1(R_CONTROL0) | 0x40); /* TX_FLUSH */
	rd1(R_INTA);
	b[i++] = SOP1; b[i++] = SOP1; b[i++] = SOP1; b[i++] = SOP2;
	b[i++] = PACKSYM | (2 + 4 * n);
	b[i++] = hdr & 0xff; b[i++] = hdr >> 8;
	for (k = 0; k < n; k++) {
		b[i++] = obj[k]; b[i++] = obj[k] >> 8;
		b[i++] = obj[k] >> 16; b[i++] = obj[k] >> 24;
	}
	b[i++] = JAMCRC; b[i++] = EOP; b[i++] = TXOFF; b[i++] = TXON;
	wr(R_FIFO, b, i);
	t0 = now_ms();
	while (now_ms() - t0 < 20) {
		uint8_t a = rd1(R_INTA);
		if (a & 0x04) return 0;	/* I_TXSENT: GoodCRC received */
		if (a & 0x10) return -1;	/* I_RETRYFAIL */
		usleep(500);
	}
	return -2;
}

/* Returns header, fills obj; -1 on timeout */
static int recv(uint32_t *obj, int *n, int timeout_ms)
{
	double t0 = now_ms();
	while (now_ms() - t0 < timeout_ms) {
		uint8_t tok, h[2], d[28 + 4];
		uint16_t hdr;
		int cnt, k;

		if (rd1(R_STATUS1) & 0x20) { /* RX_EMPTY */
			usleep(500);
			continue;
		}
		rd(R_FIFO, &tok, 1);
		rd(R_FIFO, h, 2);
		hdr = h[0] | h[1] << 8;
		cnt = (hdr >> 12) & 7;
		rd(R_FIFO, d, cnt * 4 + 4);
		for (k = 0; k < cnt; k++)
			obj[k] = d[4*k] | d[4*k+1] << 8 | d[4*k+2] << 16 | (uint32_t)d[4*k+3] << 24;
		*n = cnt;
		if ((tok & 0xe0) != 0xe0) /* not SOP */
			continue;
		return hdr;
	}
	return -1;
}

static uint16_t mkhdr(int type, int id, int n)
{
	/* sink, UFP, PD 2.0 */
	return (type & 0x1f) | (1 << 6) | ((id & 7) << 9) | ((n & 7) << 12);
}

static void reply(int type, const uint32_t *o, int n)
{
	int r = send(mkhdr(type, txid, n), o, n);
	if (r) fail("PD transmit failed; refusing automatic renegotiation retries");
	txid++;
	LOG("  -> %s %d n %d tx %d\n", n ? "data" : "ctrl", type, n, r);
}

/* Answer what the source asks after the contract, for @secs seconds */
static uint32_t request_5v(uint32_t pdo)
{
	uint32_t current = pdo & 0x3ff;
	if ((pdo >> 30) != 0 || ((pdo >> 10) & 0x3ff) != 100 || !current)
		fail("First source PDO must be fixed 5V with nonzero current");
	if (current > 300) current = 300; /* Board policy: at most 3A. */
	requested_ma = current * 10;
	requested_rdo = (1u << 28) | (1u << 25) | (1u << 24) | (current << 10) | current;
	return requested_rdo;
}

/* Share the atomic writer with firmware history. A storage/helper failure
 * must never turn a completed contract into another negotiation attempt.
 */
static void remember_contract(const char *python, const char *module, uint32_t rdo)
{
	char value[9];
	int status;
	snprintf(value, sizeof(value), "%08x", rdo);
	pid_t child = fork();
	if (child == 0) {
		execl(python, python, module, "--remember-linux", value, (char *)NULL);
		_exit(127);
	}
	if (child > 0) {
		pid_t waited;
		do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
		if (waited == child && WIFEXITED(status) && WEXITSTATUS(status) == 0)
			return;
	}
	fprintf(stderr, "PD contract history unavailable; completed contract retained\n");
}

static void serve(int secs)
{
	double t0 = now_ms();
	uint32_t o[8];
	int n, h;

	while (now_ms() - t0 < secs * 1000.0) {
		uint8_t a = rd1(R_INTA);
		if (a & 0x01) fail("Source sent a hard reset; boot-time handoff aborted");
		h = recv(o, &n, 50);
		if (h < 0) continue;
		int type = h & 0x1f;
		LOG("%.0f rx hdr %04x %s %d n %d%s", now_ms() - t0, h, n ? "data" : "ctrl", type, n, n ? " :" : "");
		for (int k = 0; k < n; k++) LOG(" %08x", o[k]);
		LOG("\n");
		if (!n) {
			switch (type) {
			case 1: case 3: break;	/* GoodCRC/Accept */
			case 6: contract_ready = 1; break; /* PS_RDY */
			case 4: case 12: fail("Source rejected or deferred the request"); break;
			case 8: {	/* Get_Sink_Cap */
				uint32_t p = (1u << 26) | (100u << 10) | 300;	/* 5V 3A usbcomm */
				reply(4, &p, 1); break; }
			case 13: txid = 0; contract_ready = 0; reply(3, NULL, 0); break;
			default: reply(4, NULL, 0); break;	/* Reject */
			}
		} else if (type == 1) {	/* Source_Capabilities again */
			uint32_t rdo = request_5v(o[0]);
			contract_ready = 0;
			reply(2, &rdo, 1);
		} else if (type == 15 && (o[0] & 0x8000) && !(o[0] & 0xc0)) {
			/* No alternate modes or certified PD identity to advertise. */
			uint32_t nak = o[0] | 0x80;
			reply(15, &nak, 1);
		}
	}
	if (!contract_ready) fail("No completed PD contract");
	LOG("PD bootstrap complete; USB-capable 5V contract established\n");
}

int main(int argc, char **argv)
{
	int status_only = argc == 2 && !strcmp(argv[1], "--status");
	if (argc != 1 && !status_only) { fprintf(stderr, "Usage: %s [--status]\n", argv[0]); return 2; }
	uint32_t obj[8], caps[8];
	int n, ncaps = 0, id, h, r, k;

	setvbuf(stdout, NULL, _IONBF, 0);
	int lock = open("/run/vim4-kvm-pd.lock", O_CREAT | O_RDWR | O_CLOEXEC, 0600);
	if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) fail("Cannot lock PD controller");
	int bus = controller_bus("/sys/class/i2c-dev/i2c-*/device/of_node");
	if (bus < 0) fail("Cannot identify VIM4 PD I2C controller");
	char driver[128], device[64];
	snprintf(driver, sizeof(driver), "/sys/bus/i2c/devices/%d-0022/driver", bus);
	if (access(driver, F_OK) == 0)
		fail("PD controller already owned by a kernel driver");
	snprintf(device, sizeof(device), "/dev/i2c-%d", bus);
	fd = open(device, O_RDWR | O_CLOEXEC);
	if (fd < 0) { perror("i2c"); return 1; }
	if (rd1(0x01) != 0x91) fail("Unexpected FUSB302B device ID");
	if (status_only) {
		/* STATUS0 is non-destructive. Do not read interrupt registers/FIFO,
		 * change the measurement mux, or send PD traffic during monitoring.
		 * VBUSOK is a threshold indication, not a voltage/current reading.
		 */
		printf("{\"vbusPresent\":%s}\n", rd1(R_STATUS0) & 0x80 ? "true" : "false");
		return 0;
	}
	if ((rd1(R_SWITCHES1) & 0xf7) != 0x45 &&
	    (rd1(R_SWITCHES1) & 0xf7) != 0x46)
		fail("Expected U-Boot initialized PD2 sink/UFP with automatic GoodCRC");
	LOG("devid %02x sw1 %02x st0 %02x st1 %02x\n", rd1(0x01),
	       rd1(R_SWITCHES1), rd1(R_STATUS0), rd1(R_STATUS1));

	/* drain anything left in RX */
	double drain_until = now_ms() + 100;
	while (now_ms() < drain_until && recv(obj, &n, 1) >= 0) {}

	for (id = 0; id < 8 && !ncaps; id++) {
		r = send(mkhdr(7 /* Get_Source_Cap */, id, 0), NULL, 0);
		if (r) { LOG("Get_Source_Cap id %d: tx %d\n", id, r); continue; }
		double until = now_ms() + 100;
		while (now_ms() < until && (h = recv(obj, &n, 30)) >= 0) {
			LOG("rx type %d n %d id %d\n", h & 0x1f, n, (h >> 9) & 7);
			if (n && (h & 0x1f) == 1) {
				memcpy(caps, obj, n * 4);
				ncaps = n;
				break;
			}
		}
		if (!ncaps)
			LOG("id %d: no Source_Capabilities\n", id);
	}
	if (!ncaps) fail("No Source_Capabilities; leaving the existing power configuration alone");

	txid = id;
	{
		/* fixed 5V PDO #1, full current, USB comm capable + no USB suspend */
		uint32_t rdo = request_5v(caps[0]);

		r = send(mkhdr(2 /* Request */, txid++, 1), &rdo, 1);
		LOG("Request rdo %08x: tx %d\n", rdo, r);
		if (r) fail("Initial request failed");
		serve(20);
		LOG("PD contract at bootstrap: 5000mV %umA\n", requested_ma);
	}

	for (k = 0; k < ncaps; k++)
		LOG("PDO%d %08x type %u %umV %umA%s%s\n", k + 1, caps[k], caps[k] >> 30,
		       ((caps[k] >> 10) & 0x3ff) * 50, (caps[k] & 0x3ff) * 10,
		       caps[k] & (1u << 26) ? " usbcomm" : "",
		       caps[k] & (1u << 25) ? " drswap" : "");
	remember_contract("/usr/bin/python3", "/usr/lib/vim4-kvm/python/vim4pd.py", requested_rdo);
	return 0;
}
