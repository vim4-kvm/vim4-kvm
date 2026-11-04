// SPDX-License-Identifier: MIT
/* Check HDCP TA session compatibility without invoking a TA command. */
#include <stdio.h>
#include <tee_client_api.h>

int main(void)
{
	const TEEC_UUID hdcp = {
		0xff2a4bea, 0xef6d, 0x11e6,
		{ 0x89, 0xcc, 0xd4, 0xae, 0x52, 0xa7, 0xb3, 0xb3 }
	};
	TEEC_Context context;
	TEEC_Session session;
	TEEC_Result result;
	uint32_t origin = 0;

	result = TEEC_InitializeContext(NULL, &context);
	if (result != TEEC_SUCCESS) {
		fprintf(stderr, "initialize: result=0x%08x\n", result);
		return 1;
	}
	result = TEEC_OpenSession(&context, &session, &hdcp,
				  TEEC_LOGIN_PUBLIC, NULL, NULL, &origin);
	printf("open HDCP TA: result=0x%08x origin=%u\n", result, origin);
	if (result == TEEC_SUCCESS)
		TEEC_CloseSession(&session);
	TEEC_FinalizeContext(&context);
	return result == TEEC_SUCCESS ? 0 : 1;
}
