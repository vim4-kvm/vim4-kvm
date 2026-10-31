# HDR2 PQ diagnostics and integrated HLG candidate

Apply the three mail patches in filename order with `git am` in a new kernel
worktree based on `f71b5c6289cb3254690e57292327e73514f0715f`.
They reproduce `vim4-hdr2-pq@11f3239b7c849` in
`~/src/linux-7.3-hdr2-pq` on the build VM. They have not been pushed or sent.

- `0001-pq-shadow-diagnostics.patch`: `eb156b545c8a2`, the PQ-only diagnostic
  module used in the SDR board window. It does not change colour processing.
- `0002-integrated-hlg.patch`: `bbf9ff89b284d`, the HLG candidate reconciled with
  the PQ shadow bookkeeping. This replaces, rather than follows, the standalone
  [HLG mail patch](../hdr2-hlg/README.md). The original HLG worktree is untouched.
- `0003-select-crc32.patch`: `11f3239b7c849`, declares the CRC32 dependency
  for configurations other than the already enabled uhd3 configuration.

`hdr_status` is a read-only debugfs diagnostic, not a colour-control ABI. Its
`profile_programmed` and `last_programmed_*` fields refer **only to the PQ
gain/OETF writer**. They do not report HLG programming. Configured CRCs use
little-endian u32 port samples, with OETF samples truncated by two bits. Neither
configured nor last-programmed shadow CRCs are hardware LUT readback or proof
that the pixels were transformed correctly. Non-streaming reads skip MMIO.

Run from the kernel worktree:

```sh
python3 drivers/media/platform/amlogic/t7-hdmirx/test_hdr_crc.py
python3 drivers/media/platform/amlogic/t7-hdmirx/test_hlg.py \
  "$HOME/src/linux-native-hdr-5.15/common_drivers/drivers/media/enhancement/amvecm/set_hdr2_v0.c"
```

The merged RX/VDIN modules passed W=1, sparse C=2 and BTF generation against a
private copy of the uhd3 configuration, symbols and vmlinux. This is a directory
module build, not a fresh merged Image/dtbs/all-modules build. Do not mix the
merged modules with the board-tested PQ-only payload: HLG adds an RX export and
requires matching modules. Build a distinct complete candidate before the next
HLG board window. No production kernel configuration was edited.

Board limitations, source status, CRCs, artifacts and rollback checks are in the
[PQ window record](../../docs/bringup/2026-10-30-hdr2-pq-window.md).
