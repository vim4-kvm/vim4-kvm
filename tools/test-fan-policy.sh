#!/bin/sh
# Exercise the actual kernel interpolation and ramp helpers without hardware.
set -eu
source_file=${1:?usage: test-fan-policy.sh /path/to/linux/drivers/misc/khadas-mcu.c}
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT HUP INT TERM
{
    printf '#include <assert.h>\n'
    printf 'struct mcu_fan_data { int trig_temp_level0, trig_temp_level1, trig_temp_level2; };\n'
    sed -n '/^#define MCU_FAN_AUTO_/p' "$source_file"
    sed -n '/^static int mcu_fan_lerp/,/^static int mcu_fan_speed_percent_set/{ /^static int mcu_fan_speed_percent_set/!p; }' "$source_file"
    cat <<'C'
int main(void)
{
    struct mcu_fan_data fan = {60, 80, 100};
    int previous = 0;
    for (int temp = 0; temp <= 130; temp++) {
        int speed = mcu_fan_auto_speed_percent(&fan, temp);
        assert(speed >= previous && speed <= 100);
        if (temp < 45) assert(speed == 0);
        if (temp >= 100) assert(speed == 100);
        previous = speed;
    }
    for (int current = 0; current <= 100; current++) {
        assert(mcu_fan_limit_speed_change(current, 100) == 100);
        assert(mcu_fan_limit_speed_change(current, 0) == 0);
        for (int target = 1; target < 100; target++) {
            int next = mcu_fan_limit_speed_change(current, target);
            assert(next >= 0 && next <= 100);
            if (current != 0) {
                assert(next - current <= 5 && current - next <= 5);
                assert((next >= current && next <= target) ||
                       (next <= current && next >= target));
            }
        }
    }
    return 0;
}
C
} > "$test_dir/policy.c"
${CC:-cc} -Wall -Wextra -Werror "$test_dir/policy.c" -o "$test_dir/policy"
"$test_dir/policy"
echo 'Fan policy tests passed'
