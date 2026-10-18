#!/usr/bin/env python3
"""Migrate only the web entry point owned by the VIM4 manager gateway."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile


def migrate(content, application):
    if application == 'jetkvm':
        config = json.loads(content)
        if not isinstance(config, dict):
            raise ValueError('JetKVM config must be a JSON object')
        config.update(local_loopback_only=True, localAuthMode='noPassword', tls_mode='')
        return json.dumps(config, indent=2) + '\n'

    if application != 'pikvm':
        raise ValueError('Unknown application')

    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    yaml = YAML()
    yaml.preserve_quotes = True
    config = yaml.load(content)
    if config is None:
        config = CommentedMap()
        if content:
            config.yaml_set_start_comment(content)
    if not isinstance(config, dict):
        raise ValueError('Application config must be a YAML mapping')

    def mapping(parent, key):
        if key not in parent or parent[key] is None:
            parent[key] = CommentedMap()
        if not isinstance(parent[key], dict):
            raise ValueError(f'{key} must be a YAML mapping')
        return parent[key]

    mapping(mapping(config, 'kvmd'), 'auth')['enabled'] = False
    output = io.StringIO()
    yaml.dump(config, output)
    return output.getvalue()


def migrate_file(path, application):
    path = Path(path)
    content = path.read_text()
    updated = migrate(content, application)
    if updated != content:
        metadata = path.stat()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as target:
                temporary = target.name
                target.write(updated)
                target.flush()
                os.fchown(target.fileno(), metadata.st_uid, metadata.st_gid)
                os.fchmod(target.fileno(), metadata.st_mode & 0o7777)
                os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


if __name__ == '__main__':
    migrate_file(sys.argv[2], sys.argv[1])
