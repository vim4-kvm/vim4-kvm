# HDR2 PQ diagnostics and integrated HLG candidate

Apply the mail patches in numeric order with `git am` in a new kernel
worktree based on `f71b5c6289cb3254690e57292327e73514f0715f`.
The current candidate is `vim4-hdr2-pq@851153f2f529f` in
`~/src/linux-7.3-hdr2-pq` on the build VM. It has not been proposed upstream.

- `0001-pq-shadow-diagnostics.patch`: `eb156b545c8a2`, the PQ-only diagnostic
  module used in the SDR board window. It does not change colour processing.
- `0002-integrated-hlg.patch`: `bbf9ff89b284d`, the HLG candidate reconciled with
  the PQ shadow bookkeeping. This replaces, rather than follows, the standalone
  [HLG mail patch](../hdr2-hlg/README.md). The original HLG worktree is untouched.
- `0003-select-crc32.patch`: `11f3239b7c849`, declares the CRC32 dependency
  for configurations other than the already enabled uhd3 configuration.
- `0004-unified-output-transfer.patch`: `58b7ecfeb6838`, shares the product
  sRGB OETF with HLG; its transfer-label policy is superseded by 0007.
- `0006-wave5-color-vui.patch`: `f1005476aa891`, OUTPUT colour fields to
  coherent AVC/HEVC VUI RBSP; independent SPS parsing and close-failure tests.
- `0007-precise-gamut-video-contract.patch`: `4dba1218cdf05`, precise PQ gamut,
  signed standalone PQ/HLG pre-offset and the existing product's 709 video tuple.
- `0008-capture-pool-budget.patch`: `7c9284da44273`, total capture allocation
  bound including CREATE_BUFS, with actual writer/queue regression tests.
- `0009-buffer-retirement-trace.patch`: `450100ce27911`, direct capture epochs,
  DMA-buf provenance and Wave5 submit/complete events.
- `0010-host-lifecycle-fixtures.patch`: `7614e04a56408`, HLG policy and debugfs
  extraction fixes in existing host fixtures.
- `0011-capture-byte-budget.patch`: `5f420235fff62`, replace the six-buffer
  limit with a 192 MiB total allocation budget, including CREATE_BUFS.
- `0012-allocator-dma-identity.patch`: `7551908e3116b`, correlate independent
  exports by their shared vb2 allocator and normalized direct DMA address.
- `0013-vb2-base-layout.patch`: `851153f2f529f`, keep vb2 at offset zero;
  compile-time assertion and a host replay of the invalid a3 layout.

Apply 0001 through 0013 in numeric order (0005 is described below).
The [a3 decision and next window](../../docs/hdr2a3-offline.md) supersede the a1
transfer-13 policy. A complete a3 archive has now been sealed and booted; see the
[a3 window](../../docs/bringup/2026-10-30-hdr2a3-window.md). Subsequent
[a5 acceptance](../../docs/bringup/2026-10-30-hdr2a5-window.md) passes PQ retirement
and product DMA recovery. The [integration proposal](../../docs/hdr2-dma-contract.md)
still requires user review before merging into main or the formal kernel.

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
python3 drivers/media/platform/amlogic/t7-hdmirx/test_hdr_resources.py
python3 drivers/media/platform/chips-media/wave5/test_vui.py
python3 drivers/media/platform/chips-media/wave5/test_encoder_cleanup.py
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

The builder also applies `gstreamer-encoded-size.patch` and executes
`test_gst_size.py` against the real patched function. For fixed encoder
dimensions it requests coded buffers for that size, preserving decoder
resolution-change headroom and driver-returned sizes. This addresses the a2
32 MiB-per-coded-buffer CMA pressure; a clean boot still has to prove zero WARNs.

`check_retirement.py TRACE` joins both kernel trace events by shared allocator
identity **and** normalized physical address. Repeated EXPBUF calls create new
inodes, so inode equality is not a valid join. It rejects unknown/IOMMU mappings
(physical address zero) rather than assuming bus addresses share a domain.
It reports per-generation tickets/retirement and encoder submissions and rejects
stale submissions, early reuse, retained faults, missing epochs and trace loss.
QBUF is immediate reuse and is forbidden during encoding. `buf_cleanup` instead
releases the capture queue's reference; an imported DMA-buf can legitimately keep
that allocation alive. In that case retirement remains outstanding until the
actual Wave5 completion/cancellation. A new generation still requires every old
ticket retired and every encoder job finished. No submitted job is discarded to
make a trace pass.
Record from before STREAMON through complete encoder drain/capture cleanup;
the a3 checklist details the isolated trace instance. It does not prove user FD
closure or cover buffers copied into unrelated allocations.

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

`trial-init.c` is the static PID 1 for the HDR trial payload. Compile it with
`-DRELEASE=\"PRIVATE_RELEASE\"`. It validates the running release, build ID and
root-owned payload before binding matching modules and private runtime files.
The application/plugin targets are the paths used by the actual `one-kvm`
service, not the alternate edge executable. Verify `/proc/MainPID/exe` and the
mapped plugin hash before measuring. All binds disappear on reboot; the default
boot files remain unchanged.
