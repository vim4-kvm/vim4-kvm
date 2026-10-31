# Ordinary HLG capture candidate

`0001-hlg-capture.patch` is a local mail patch against Linux
`f71b5c6289cb3254690e57292327e73514f0715f`. It has not been sent or pushed.
Apply in a separate review worktree with `git am`; do not apply it directly
over the concurrently edited PQ worktree without reconciling the profile and
lease interfaces. No source files from that worktree were copied here.

The kernel commit and build/test evidence are recorded in
[HLG implementation](../../docs/hdr2-hlg.md). Host checks live in the patch as
`drivers/media/platform/amlogic/t7-hdmirx/test_hlg.py`; run with the optional
fixed vendor `set_hdr2_v0.c` path to compare all table values, otherwise it
checks the sealed table hashes and encoded port words.

No installation, board access, EDID changes, or HLG hardware validation have
been performed. Merge with PQ, validate output colour signalling, then use
the unified hardware checklist before enabling the candidate for users.
