# Independent capture broker: ownership core

`service.py` owns the V4L2 queue and serves versioned seqpacket/SCM_RIGHTS
clients. `devices.c` supplies actual Linux V4L2 and DRM calls; `devices.py`
binds them. `leases.py` tracks ownership and `ipc.py` transports exported fds.
This is an experimental implementation, not a hardware-qualified service.

The intended owner is a persistent board service, rather than a KVM application's
pipeline. Its local KMS subscriber exists whenever manager requests passthrough;
remote subscribers can come and go without stopping capture or local scanout.
Every call runs on the service's single event loop. Explicit display mode requires
connector/CRTC/plane IDs and a connected 60Hz mode. Automatic hotplug/source-change,
HDR mapping readback and production capability qualification remain incomplete;
manager deliberately reports unsupported. The unit is opt-in and not installed.

Adapter contract:

1. Allocate one VDIN pool, export each buffer once and retain those fds. Call
   `begin_generation` with actual allocation sizes. A pool over 192 MiB is rejected.
2. Admit a local display subscriber and bounded encoding subscribers. Each requires
   its in-flight limit plus one latest-pending slot; two capture working slots stay
   reserved. This conservative bound counts consumers independently even when they
   share frames. Existing One-KVM's 12-lease budget therefore cannot simply be added
   to display leases in a 16-buffer pool: its queue/pool budget needs adjustment
   and measurement before the adapter can be enabled.
3. On valid, completed DQBUF, publish a `Frame` carrying its actual stride, UV
   offset, colorimetry and generation. Invalid/ERROR buffers must never be published.
   Take a subscriber's latest frame only when ready to submit it. Pending replacements
   drop references without touching an active hardware reader.
4. After take, the adapter owns the returned lease until a real reader completion
   boundary. Encoder input completion can retire its lease. For KMS use the actual
   VD1 reader retirement fence, including its extra scan period; atomic ioctl return,
   latch/OUT_FENCE or ordinary page-flip alone cannot retire it. Rejected submissions
   may retire only after proving the device never acquired that frame.
5. Drain `take_recyclable()` and QBUF only keys from the still-running capture
   generation. Subscriber disconnect removes pending references but preserves active
   leases; closing a socket or fd is not evidence of hardware retirement. A reader
   process crash requires adapter-owned fence or completion evidence. If uncertain,
   `pin_fault` prevents recycling until reboot; no automatic fake completion exists.
6. On source change, stop distribution, blank/retire readers and stop VDIN. Drain
   retired old-generation keys by releasing the old pool after STREAMOFF, not by
   queuing them into a new fd. New generation admission refuses outstanding leases
   and undrained recycling records. Subscribers can remain registered across this
   transition. Generation must advance and duplicate/late lease retirement fails.

The broker does not infer signal health from pixels or clients. Manager preferences,
HDR pixel-domain selection, source/sink qualification, KMS TEST_ONLY and PCM ownership
remain separate work. No performance or hardware correctness claim follows from the
ownership tests.

Run the deterministic core tests from the main repository:

```sh
python3 -m unittest discover -s tests -p test_passthrough_broker.py
```

Build the Linux library with GStreamer-independent libdrm development files:

```sh
cc -shared -fPIC -O2 -Wall -Wextra -Werror devices.c -o libpassthrough73.so $(pkg-config --cflags --libs libdrm)
```

An installer must copy the Python directory and library to
`/usr/lib/vim4-kvm/passthrough73`, install the unit, and explicitly provision
`/etc/vim4-kvm/broker.env` with `BROKER_CAPTURE` pointing at the qualified VDIN node.
None of those operations is performed by this repository's offline tests.
The default unit serves capture clients only; display requires explicit CLI IDs.
One-KVM enables its AppSrc input only with `VIM4_BROKER_SOCKET` set to capture.sock.
No fallback may open a second capture queue if that connection fails.

AudioOwner implements bounded PCM queues and an in-place RX recovery callback;
actual ALSA opens, TX continuous-silence configuration and clock drift correction
are still adapter work. No audio playback is performed by the tests.
