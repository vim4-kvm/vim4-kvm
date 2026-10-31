# HDR2 PQ diagnostics and integrated HLG candidate

Apply the first four mail patches in filename order with `git am` in a new kernel
worktree based on `f71b5c6289cb3254690e57292327e73514f0715f`.
They reproduce `vim4-hdr2-pq@58b7ecfeb6838` in
`~/src/linux-7.3-hdr2-pq` on the build VM. They have not been pushed or sent.

- `0001-pq-shadow-diagnostics.patch`: `eb156b545c8a2`, the PQ-only diagnostic
  module used in the SDR board window. It does not change colour processing.
- `0002-integrated-hlg.patch`: `bbf9ff89b284d`, the HLG candidate reconciled with
  the PQ shadow bookkeeping. This replaces, rather than follows, the standalone
  [HLG mail patch](../hdr2-hlg/README.md). The original HLG worktree is untouched.
- `0003-select-crc32.patch`: `11f3239b7c849`, declares the CRC32 dependency
  for configurations other than the already enabled uhd3 configuration.
- `0004-unified-output-transfer.patch`: `58b7ecfeb6838`, shares the product
  sRGB OETF with HLG and reports the mapped NV12 transfer accurately.

`hdr_status` is a read-only debugfs diagnostic, not a colour-control ABI. Its
`profile_programmed` and `last_programmed_*` fields refer **only to the PQ
gain/OETF writer**. They do not report HLG programming. Configured CRCs use
little-endian u32 port samples, with OETF samples truncated by two bits. Neither
configured nor last-programmed shadow CRCs are hardware LUT readback or proof
that the pixels were transformed correctly. Non-streaming reads skip MMIO.

Run from the kernel worktree:

```sh
python3 drivers/media/platform/amlogic/t7-hdmirx/test_hdr_crc.py
python3 drivers/media/platform/amlogic/t7-hdmirx/test_color.py
python3 drivers/media/platform/amlogic/t7-hdmirx/test_hlg.py \
  "$HOME/src/linux-native-hdr-5.15/common_drivers/drivers/media/enhancement/amvecm/set_hdr2_v0.c"
```

The earlier merged RX/VDIN modules passed W=1, sparse C=2 and BTF generation against a
private copy of the uhd3 configuration, symbols and vmlinux. This is a directory
module build, not a fresh merged Image/dtbs/all-modules build. Do not mix the
merged modules with the board-tested PQ-only payload: HLG adds an RX export and
requires matching modules. The subsequent complete hdr2a1 build and its output
contract are tracked in the [unified candidate](../../docs/hdr2-unified-candidate.md).
No production kernel configuration was edited.

The subsequent `0005-ethernet-alias.patch` is the isolated network change
(`vim4-hdr2-network@3c993b4adeec3`, based on the board-tested PQ diagnostic).
It also applies after the four integration patches. It does not by itself
override the bootloader's placeholder MAC: record `/sys/class/net/eth0/address`
on 5.15, then pass that value and the candidate build ID to `ram_command.py`.
The printed command only sets U-Boot RAM environment; never add saveenv.
The a2 board record explains why the MAC/alias pair is required.

`build-gst.sh NEW_WORK_DIR` builds the pinned private plugin with the existing
ordered six V4L2 patches, then applies `gstreamer-srgb-probe.patch`. It requires
Meson, Ninja and GStreamer/udev development packages. `test_gst_color.py` executes
the actual caps probe with accepting, canonicalizing and rejecting devices;
both single-plane and multiplanar interfaces are checked. Point the test process
at the resulting private directory via GST_PLUGIN_PATH and a private registry.
Do not replace the system plugin. No new kernel-edge configuration is involved.

`chart.html` is a static grayscale/colour-gradient target. `compare_frames.py`
compares complete visible NV21/NV12 frames, handles vendor tail padding and
requires equal whole-frame counts. Browser overlays and the pointer must still
be controlled; statistics alone do not establish absolute colour accuracy.

Board limitations, source status, CRCs, artifacts and rollback checks are in the
[PQ window record](../../docs/bringup/2026-10-30-hdr2-pq-window.md).

After the complete build succeeds, seal a new private stage and archive (VM only):

```sh
python3 package.py "$HOME/src/linux-7.3-hdr2-pq" \
  "$HOME/build/hdr2-combined" "$HOME/build/hdr2-combined-stage"
```

This runs modules_install/depmod in the new stage, removes build/source symlinks,
copies Image/config/System.map/DTBs, and records a SHA256 manifest. Existing
stages and archives are refused. It neither installs to the VM rootfs nor
contacts a board. Retain vmlinux in the output directory for matching BTF.
