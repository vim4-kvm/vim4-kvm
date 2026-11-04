#!/usr/bin/env python3
"""Generate H.264 or MPEG-2 motion fixtures and compare captured I420 frames offline.

Requires FFmpeg with libx264 and ffprobe. Neither operation accesses a board.
References are decoded from the actual compressed files, so encoder versions
may change fixture bytes without weakening the pixel comparison.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
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
    ("uhd", 3840, 2160, 16, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1"),
    ("4k-limit", 4096, 2304, 8, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1"),
    ("high-jvt", 640, 368, 16, "high", "High",
     "cabac=1:bframes=2:ref=3:8x8dct=1:cqm=jvt"),
)

MPEG2_CASES = (
    ("mpeg2-intra", 640, 368, 16, "main", "Main", ["-g", "1", "-bf", "0"]),
    ("mpeg2-ipb", 640, 368, 32, "main", "Main", ["-g", "12", "-bf", "2"]),
    ("mpeg2-matrix", 640, 368, 16, "main", "Main",
     ["-g", "12", "-bf", "2", "-intra_matrix",
      ",".join(str(8 + i % 17) for i in range(64)), "-inter_matrix",
      ",".join(str(16 + i % 13) for i in range(64))]),
    ("mpeg2-interlaced", 640, 368, 16, "main", "Main",
     ["-g", "12", "-bf", "2", "-flags", "+ildct+ilme", "-top", "1"]),
    ("mpeg2-1080p", 1920, 1080, 16, "main", "Main", ["-g", "12", "-bf", "2"]),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def frame_hashes(raw, frame_size):
    return [sha256(raw[i:i + frame_size])
            for i in range(0, len(raw), frame_size)]


def generate(output, codec="h264"):
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "codec": codec,
        "ffmpeg": subprocess.check_output(
            ["ffmpeg", "-version"], text=True).splitlines()[0],
        "cases": [],
    }
    cases = CASES if codec == "h264" else MPEG2_CASES
    extension = ".h264" if codec == "h264" else ".m2v"
    for name, width, height, count, profile, actual_profile, params in cases:
        clip = output / (name + extension)
        # QP22 exercises negative PPS QP/chroma offsets. QP26 would hide
        # firmware parameter-table signed-code regressions.
        encoder = (["-c:v", "libx264", "-preset", "medium", "-qp", "22",
                    "-profile:v", profile, "-x264-params",
                    params + ":keyint=16:min-keyint=16:scenecut=0:slices=1", "-f", "h264"]
                   if codec == "h264" else
                   ["-c:v", "mpeg2video", "-q:v", "4", *params, "-f", "mpeg2video"])
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", f"testsrc2=size={width}x{height}:rate=30",
            "-frames:v", str(count), "-an", "-threads", "1", *encoder, str(clip),
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
        expected_field_order = "tt" if name == "mpeg2-interlaced" else "progressive"
        if stream.get("field_order") != expected_field_order:
            raise ValueError(f"{name}: unexpected field order {stream.get('field_order')}")
        raw = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(clip), "-threads", "1",
            "-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1",
        ])
        frame_size = width * height * 3 // 2
        if len(raw) != frame_size * count:
            raise ValueError(f"{name}: software reference frame count mismatch")
        manifest["cases"].append(dict(
            name=name, width=width, height=height, frames=count,
            codec=codec, filename=clip.name, field_order=stream.get("field_order"),
            frame_size=frame_size, profile=profile,
            compressed_sha256=sha256(clip.read_bytes()),
            decoded_sha256=sha256(raw), frame_sha256=frame_hashes(raw, frame_size),
        ))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return 0


def pixel_errors(reference, captured, width, height):
    frame_size = width * height * 3 // 2
    if len(reference) != len(captured) or len(reference) % frame_size:
        raise ValueError("pixel measurement requires equal complete I420 frames")
    y_size = width * height
    planes = (("Y", 0, y_size), ("U", y_size, y_size * 5 // 4),
              ("V", y_size * 5 // 4, frame_size))
    frames = []
    for offset in range(0, len(reference), frame_size):
        result = {}
        for plane, start, end in planes:
            errors = Counter(a - b for a, b in zip(
                reference[offset + start:offset + end], captured[offset + start:offset + end]))
            count = end - start
            mse = sum(error * error * n for error, n in errors.items()) / count
            result[plane] = dict(
                max_absolute_error=max(abs(error) for error in errors),
                mean_error=sum(error * n for error, n in errors.items()) / count,
                exact_fraction=errors[0] / count,
                psnr_db=10 * math.log10(255 * 255 / mse) if mse else None,
            )
        frames.append(result)
    return frames


def compare(fixtures, name, captured, measure_error=False):
    manifest = json.loads((fixtures / "manifest.json").read_text())
    case = next((c for c in manifest["cases"] if c["name"] == name), None)
    if case is None:
        raise ValueError(f"unknown fixture: {name}")
    if sha256((fixtures / case.get("filename", name + ".h264")).read_bytes()) != case["compressed_sha256"]:
        raise ValueError(f"{name}: compressed fixture changed")
    raw = captured.read_bytes()
    hashes = frame_hashes(raw, case["frame_size"])
    expected = case["frame_sha256"]
    mismatch = next((i for i in range(max(len(hashes), len(expected)))
                     if i >= len(hashes) or i >= len(expected)
                     or hashes[i] != expected[i]), None)
    exact = len(raw) == case["frames"] * case["frame_size"] and mismatch is None
    result = dict(
        name=name, bytes=len(raw), complete_frames=len(raw) // case["frame_size"],
        expected_frames=case["frames"], first_mismatch=mismatch,
        exact=exact, all_zero=bool(raw) and not any(raw),
    )
    if measure_error:
        reference = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(fixtures / case.get("filename", name + ".h264")),
            "-threads", "1", "-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1",
        ])
        if sha256(reference) != case["decoded_sha256"]:
            raise ValueError("software reference differs from the fixture manifest")
        result["pixel_errors"] = pixel_errors(reference, raw, case["width"], case["height"])
    print(json.dumps(result, indent=2))
    return 0 if exact else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate_parser = commands.add_parser("generate", help="create a new fixture directory")
    generate_parser.add_argument("output", type=Path)
    generate_parser.add_argument("--codec", choices=("h264", "mpeg2"), default="h264")
    compare_parser = commands.add_parser("compare", help="compare one captured I420 stream")
    compare_parser.add_argument("fixtures", type=Path)
    compare_parser.add_argument("name")
    compare_parser.add_argument("captured", type=Path)
    compare_parser.add_argument("--measure-error", action="store_true",
                                help="report per-frame Y/U/V differences; exit still requires exact pixels")
    args = parser.parse_args()
    if args.command == "generate":
        return generate(args.output, args.codec)
    return compare(args.fixtures, args.name, args.captured, args.measure_error)


if __name__ == "__main__":
    raise SystemExit(main())
