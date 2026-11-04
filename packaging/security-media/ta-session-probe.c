// SPDX-License-Identifier: MIT
/* Default to session checks; key loading must be requested explicitly. */
#include <stdio.h>
#include <string.h>
#include <tee_client_api.h>

static int load_tx_key(TEEC_Session *session, uint32_t key_type)
{
	TEEC_Operation operation = { 0 };
	TEEC_Result result;
	uint32_t origin = 0;

	operation.paramTypes = TEEC_PARAM_TYPES(TEEC_VALUE_INPUT, TEEC_NONE,
					       TEEC_NONE, TEEC_NONE);
	operation.params[0].value.a = key_type;
	/* Command 3 loads an existing provisioned key inside the secure world. */
	result = TEEC_InvokeCommand(session, 3, &operation, &origin);
	printf("load HDCP TX %s key: result=0x%08x origin=%u\n",
	       key_type == 1 ? "1.4" : "2.2", result, origin);
	return result == TEEC_SUCCESS ? 0 : 1;
}

int main(int argc, char **argv)
{
	const TEEC_UUID hdcp = {
		0xff2a4bea, 0xef6d, 0x11e6,
		{ 0x89, 0xcc, 0xd4, 0xae, 0x52, 0xa7, 0xb3, 0xb3 }
	};
	TEEC_Context context;
	TEEC_Session session;
	TEEC_Result result;
	uint32_t origin = 0;
	int failed = 0;
	int load_keys = argc == 2 && !strcmp(argv[1], "--load-tx-keys");

	if (argc != 1 && !load_keys) {
		fprintf(stderr, "Usage: %s [--load-tx-keys]\n", argv[0]);
		return 2;
	}

	result = TEEC_InitializeContext(NULL, &context);
	if (result != TEEC_SUCCESS) {
		fprintf(stderr, "initialize: result=0x%08x\n", result);
		return 1;
	}
	result = TEEC_OpenSession(&context, &session, &hdcp,
				  TEEC_LOGIN_PUBLIC, NULL, NULL, &origin);
	printf("open HDCP TA: result=0x%08x origin=%u\n", result, origin);
	if (result == TEEC_SUCCESS) {
		if (load_keys) {
			failed |= load_tx_key(&session, 2);
			failed |= load_tx_key(&session, 1);
		}
		TEEC_CloseSession(&session);
	}
	TEEC_FinalizeContext(&context);
	return result == TEEC_SUCCESS && !failed ? 0 : 1;
}
