#!/bin/sh
# USB-C OTG gadget for the KVM target:
#   hidg0 keyboard (boot protocol, LED output)
#   hidg1 absolute mouse (0..32767)
#   hidg2 relative mouse (boot protocol, for BIOS/UEFI)
#   ncm   network (macOS/Linux/Windows 10+ native)
#
# Usage: kvm-gadget.sh start|stop     (vim4-kvm-gadget.service)
set -eu

G=/sys/kernel/config/usb_gadget/kvm
UDC=$(ls /sys/class/udc | head -1)

hid() { # name protocol subclass report_length descriptor-hex
	mkdir -p $G/functions/hid.$1
	echo $2 > $G/functions/hid.$1/protocol
	echo $3 > $G/functions/hid.$1/subclass
	echo $4 > $G/functions/hid.$1/report_length
	printf '%b' "$(echo "$5" | sed 's/../\\x&/g')" > $G/functions/hid.$1/report_desc
	ln -s $G/functions/hid.$1 $G/configs/c.1/
}

stop() {
	[ -d $G ] || return 0
	echo "" > $G/UDC 2>/dev/null || true
	find $G/configs/c.1 -maxdepth 1 -type l -exec rm {} \;
	rmdir $G/configs/c.1/strings/0x409 $G/configs/c.1 2>/dev/null || true
	for f in $G/functions/*; do [ -d "$f" ] && rmdir "$f"; done
	rmdir $G/strings/0x409 $G 2>/dev/null || true
}

start() {
	modprobe libcomposite 2>/dev/null || true
	# the stock adb+rndis gadget holds the UDC
	K=/sys/kernel/config/usb_gadget/khadas
	[ -d $K ] && echo "" > $K/UDC 2>/dev/null || true
	pkill -x adbd 2>/dev/null || true
	stop

	SERIAL=$(grep Serial /proc/cpu_chipid | grep -o -P '.{0,12}$')
	# drop the first octet, the 12:/02: prefixes make host/dev addresses
	MAC=$(echo "$SERIAL" | sed 's/\(..\)/:\1/g' | cut -b 4-)

	mkdir -p $G
	echo 0x1d6b > $G/idVendor   # Linux Foundation
	echo 0x0104 > $G/idProduct  # Multifunction Composite Gadget
	echo 0x0100 > $G/bcdDevice
	echo 0x0200 > $G/bcdUSB
	# IAD device class, needed for NCM on Windows
	echo 0xEF > $G/bDeviceClass
	echo 0x02 > $G/bDeviceSubClass
	echo 0x01 > $G/bDeviceProtocol

	mkdir -p $G/strings/0x409
	echo "$SERIAL" > $G/strings/0x409/serialnumber
	echo "vim4-kvm" > $G/strings/0x409/manufacturer
	echo "vim4-kvm Composite Device" > $G/strings/0x409/product

	mkdir -p $G/configs/c.1/strings/0x409
	echo "HID + NCM" > $G/configs/c.1/strings/0x409/configuration
	echo 0x80 > $G/configs/c.1/bmAttributes
	echo 250 > $G/configs/c.1/MaxPower

	# keyboard: modifiers, reserved, 5 LED outputs, 6 keys
	hid keyboard 1 1 8 05010906a101050719e029e71500250175019508810295017508810195057501050819012905910295017503910195067508150026ff000507190029ff008100c0
	# absolute pointer: 5 buttons, X/Y 0..32767, wheel
	hid mouse_abs 0 0 6 05010902a1010901a100050919012905150025019505750181029501750381010501093016000026ff7f751095018102093116000026ff7f75109501810209381581257f750895018106c0c0
	# relative mouse: 5 buttons, X/Y -127..127, wheel
	hid mouse_rel 2 1 4 05010902a1010901a100050919012905150025019505750181029501750381010501093009311581257f75089502810609381581257f750895018106c0c0

	mkdir -p $G/functions/ncm.usb0
	echo "12$MAC" > $G/functions/ncm.usb0/host_addr
	echo "02$MAC" > $G/functions/ncm.usb0/dev_addr
	ln -s $G/functions/ncm.usb0 $G/configs/c.1/

	echo "$UDC" > $G/UDC
}

case ${1:-start} in
start) start ;;
stop) stop ;;
*) echo "usage: $0 start|stop" >&2; exit 1 ;;
esac
