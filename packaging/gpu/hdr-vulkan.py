#!/usr/bin/env python3
"""Generate the Vulkan dialect from the single canonical GLES colour shader."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()
uniform = 'uniform ivec2 input_size, output_size;'
if source.count('#version 310 es') != 1 or source.count(uniform) != 1:
    raise ValueError('Unexpected shader parameter contract')
source = source.replace('#version 310 es', '#version 450')
source = source.replace(uniform,
    'layout(push_constant) uniform Params { ivec2 input_size; ivec2 output_size; };')
Path(sys.argv[2]).write_text(source)
