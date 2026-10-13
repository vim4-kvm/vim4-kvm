/* Link-only ABI for checking the appliance Go target on an ARM64 builder.
 * Every entry aborts: executing hardware calls is not a simulated test pass.
 * This library is never included in a component package.
 */
#include "kvm_vision.h"

void kvmv_init(uint8_t value) { (void)value; abort(); }
void kvmv_deinit(void) { abort(); }
void set_venc_auto_recyc(uint8_t value) { (void)value; abort(); }
int kvmv_read_img(uint16_t w, uint16_t h, uint8_t type, uint16_t quality,
                 uint8_t **data, uint32_t *size) {
    (void)w; (void)h; (void)type; (void)quality; (void)data; (void)size;
    abort();
}
int free_kvmv_data(uint8_t **data) { (void)data; abort(); }
void free_all_kvmv_data(void) { abort(); }
void set_h264_gop(uint8_t value) { (void)value; abort(); }
void set_frame_detact(uint8_t value) { (void)value; abort(); }
uint8_t kvmv_hdmi_control(uint8_t value) { (void)value; abort(); }
uint8_t kvmv_hdmi_signal_active(void) { abort(); }
