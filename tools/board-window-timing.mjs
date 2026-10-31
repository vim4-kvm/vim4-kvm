// Timing boundary separated from browser transport for deterministic replay.
export async function measureDecoded(sample, seconds, {
  now = () => performance.now(), sleep = ms => new Promise(r => setTimeout(r, ms)),
  readyTimeoutMs = 60000,
} = {}) {
  const readyDeadline = now() + readyTimeoutMs;
  let first;
  while (now() < readyDeadline) {
    first = await sample();
    if (first?.framesDecoded > 0) break;
    await sleep(50);
  }
  if (!(first?.framesDecoded > 0)) throw new Error('No actual decoded frame before readiness deadline');
  const started = now(), samples = [{ elapsedMs: 0, ...first }];
  while (now() - started < seconds * 1000) {
    await sleep(Math.min(50, seconds * 1000 - (now() - started)));
    const stat = await sample();
    if (!stat || stat.ssrc !== first.ssrc || stat.id !== first.id || stat.codec !== first.codec ||
        stat.framesDecoded < samples.at(-1).framesDecoded) {
      throw new Error('Video stream changed; discard measurement');
    }
    samples.push({ elapsedMs: now() - started, ...stat });
  }
  const last = samples.at(-1);
  if (last.framesDecoded <= first.framesDecoded) throw new Error('Decoded frames stopped');
  return { intervalMs: 50, elapsedMs: now() - started, samples,
    fps: (last.framesDecoded - first.framesDecoded) * 1000 / last.elapsedMs };
}
