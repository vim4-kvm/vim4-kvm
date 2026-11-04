#!/usr/bin/env python3
"""Generate H.264 motion fixtures and compare captured I420 frames offline.

Requires FFmpeg with libx264 and ffprobe. Neither operation accesses a board.
References are decoded from the actual compressed files, so encoder versions
may change fixture bytes without weakening the pixel comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


CASES = (
    ("baseline", 640, 368, 32, "baseline", "Constrained Baseline",
     "cabac=0:bframes=0:ref=2:8x8dct=0"),
    ("main", 640, 368, 64, "main", "Main",
     "cabac=1:bframes=2:ref=3:8x8dct=0:weightp=2"),
    ("high", 640, 368, 64, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1:weightp=2"),
    ("1080p", 1920, 1080, 16, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1"),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def frame_hashes(raw, frame_size):
    return [sha256(raw[i:i + frame_size])
            for i in range(0, len(raw), frame_size)]


def generate(output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "ffmpeg": subprocess.check_output(
            ["ffmpeg", "-version"], text=True).splitlines()[0],
        "cases": [],
    }
    for name, width, height, count, profile, actual_profile, params in CASES:
        clip = output / (name + ".h264")
        # QP22 exercises negative PPS QP/chroma offsets. QP26 would hide
        # firmware parameter-table signed-code regressions.
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", f"testsrc2=size={width}x{height}:rate=30",
            "-frames:v", str(count), "-an", "-c:v", "libx264", "-threads", "1",
            "-preset", "medium", "-qp", "22", "-profile:v", profile,
            "-x264-params", params + ":keyint=16:min-keyint=16:scenecut=0:slices=1",
            "-f", "h264", str(clip),
        ], check=True)
        streams = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-show_streams",
            "-of", "json", str(clip),
        ]))["streams"]
        if len(streams) != 1:
            raise ValueError(f"{name}: expected one video stream")
        stream = streams[0]
        actual = (stream["profile"], stream["width"], stream["height"],
                  stream["pix_fmt"], int(stream["nb_read_frames"]))
        if actual != (actual_profile, width, height, "yuv420p", count):
            raise ValueError(f"{name}: unexpected encoded properties {actual}")
        raw = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(clip), "-threads", "1",
            "-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1",
        ])
        frame_size = width * height * 3 // 2
        if len(raw) != frame_size * count:
            raise ValueError(f"{name}: software reference frame count mismatch")
        manifest["cases"].append(dict(
            name=name, width=width, height=height, frames=count,
            frame_size=frame_size, profile=profile,
            compressed_sha256=sha256(clip.read_bytes()),
            decoded_sha256=sha256(raw), frame_sha256=frame_hashes(raw, frame_size),
        ))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return 0


def compare(fixtures, name, captured):
    manifest = json.loads((fixtures / "manifest.json").read_text())
    case = next((c for c in manifest["cases"] if c["name"] == name), None)
    if case is None:
        raise ValueError(f"unknown fixture: {name}")
    if sha256((fixtures / (name + ".h264")).read_bytes()) != case["compressed_sha256"]:
        raise ValueError(f"{name}: compressed fixture changed")
    raw = captured.read_bytes()
    hashes = frame_hashes(raw, case["frame_size"])
    expected = case["frame_sha256"]
    mismatch = next((i for i in range(max(len(hashes), len(expected)))
                     if i >= len(hashes) or i >= len(expected)
                     or hashes[i] != expected[i]), None)
    exact = len(raw) == case["frames"] * case["frame_size"] and mismatch is None
    print(json.dumps(dict(
        name=name, bytes=len(raw), complete_frames=len(raw) // case["frame_size"],
        expected_frames=case["frames"], first_mismatch=mismatch,
        exact=exact, all_zero=bool(raw) and not any(raw),
    ), indent=2))
    return 0 if exact else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate_parser = commands.add_parser("generate", help="create a new fixture directory")
    generate_parser.add_argument("output", type=Path)
    compare_parser = commands.add_parser("compare", help="compare one captured I420 stream")
    compare_parser.add_argument("fixtures", type=Path)
    compare_parser.add_argument("name")
    compare_parser.add_argument("captured", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        return generate(args.output)
    return compare(args.fixtures, args.name, args.captured)


if __name__ == "__main__":
    raise SystemExit(main())
