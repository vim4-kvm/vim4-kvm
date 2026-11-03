"""Release identity for the next package; accepted releases keep their own receipts."""
import datetime
import re
import sys
import tomllib
from pathlib import Path


def build_contract(lock):
    package = lock['package']
    if not re.fullmatch(r'\d{8}', package['date']):
        raise ValueError('package.date must use YYYYMMDD')
    day = datetime.datetime.strptime(package['date'], '%Y%m%d').strftime('%Y%m%d')
    number = package['build']
    if number < 1:
        raise ValueError('package.build must be at least 1')
    localversion = '-vim4-' + day + ('' if number == 1 else '.' + str(number))
    version = lock['kernel']['upstream_tag'].removeprefix('v')
    release = version + localversion
    if package['tag'] != 'v' + release:
        raise ValueError('package.tag must match the dated release')
    return dict(release=release, localversion=localversion, tag=package['tag'],
                date=day, config_path=package['config_path'], config_sha256=package['config_sha256'],
                base_modules=package['base_modules'], external_modules=package['external_modules'])


if __name__ == '__main__':
    contract = build_contract(tomllib.loads(Path(sys.argv[1]).read_text()))
    print(contract['release'], contract['localversion'], contract['config_path'], contract['config_sha256'])
