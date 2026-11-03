import subprocess
import tomllib
from pathlib import Path

recipe = Path("/recipe/kernel")
for patch in tomllib.loads((recipe / "sources.toml").read_text())["gstreamer"]["patches"]:
    subprocess.run(["patch", "--forward", "-p1", "-i", recipe / patch], check=True)
