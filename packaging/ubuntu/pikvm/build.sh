#!/bin/sh
set -eu
for name in kvmd ustreamer vim4-manager packaging tools; do
    mkdir -p "/work/$name"
    rsync -a --exclude=.git --exclude=node_modules --exclude=build --exclude=dist \
        --exclude=__pycache__ "/src/$name/" "/work/$name/"
done
cp /src/workspace.toml /work/workspace.toml
sh /work/packaging/ubuntu/pikvm/build-janus.sh
export PATH=/opt/vim4-pikvm/python/bin:$PATH
cd /work/ustreamer
make -j8 WITH_VIM4=1 WITH_JANUS=1 WITH_PYTHON=1 PY=python3.14
python3.14 -m pip install --no-deps --no-index python/dist/*.whl
cd /work/kvmd
python3.14 -m build --wheel --no-isolation
python3.14 -m pip install --no-deps --no-index dist/*.whl
python3 -m unittest discover -s deploy/vim4 -p 'test_*.py'
visudo -cf deploy/vim4/vim4-pikvm-media.sudoers
cd /work
mkdir -p build
python3 tools/workspace.py build manager
python3 packaging/ubuntu/pikvm/package.py "$PACKAGE_VERSION" /out
