# Sent on SSH stdin after the first boot with the new manager and kernel.
import json
from pathlib import Path
import re
import subprocess

config=Path('/etc/default/vim4-kvm-fan')
assert (config.read_bytes().hex() if config.exists() else None)==saved_config_hex
if saved_config_hex is None:
    low,mid,high=60,80,100
else:
    values=dict(row.split('=',1) for row in bytes.fromhex(saved_config_hex).decode().splitlines() if row.startswith('FAN_TRIGGER_'))
    low,mid,high=[int(values['FAN_TRIGGER_'+key]) for key in ('LOW','MID','HIGH')]
low,mid,high=low*1000,mid*1000,high*1000
expected=([low-15000+i*2500 for i in range(6)]+[low+(mid-low)*i//4 for i in range(4)]+[mid+(high-mid)*i//4 for i in range(5)])
thermal=Path('/sys/class/thermal')
fan=next(p for p in thermal.glob('cooling_device*') if (p/'type').read_text().strip()=='khadas-mcu-fan')
tables={}
for zone in thermal.glob('thermal_zone*'):
    kind=(zone/'type').read_text().strip()
    if kind not in ('a73-thermal','a53-thermal','gpu-thermal','nna-thermal','vpu-thermal','hevc-thermal'):continue
    ids=sorted({int(Path(str(p)+'_trip_point').read_text()) for p in zone.glob('cdev*') if p.is_symlink() and p.resolve()==fan.resolve()})
    assert len(ids)==15
    table=[int((zone/f'trip_point_{i}_temp').read_text()) for i in ids]
    assert table==expected,(kind,table,expected)
    if saved_config_hex is None:
        dt=Path('/sys/firmware/devicetree/base/thermal-zones')/kind/'trips'
        defaults=sorted(int.from_bytes((p/'temperature').read_bytes(),'big') for p in dt.iterdir() if (p/'type').read_bytes().rstrip(b'\0')==b'active')
        assert defaults==table,(kind,defaults,table)
    tables[kind]=table
assert len(tables)==6
pre=subprocess.check_output(['systemctl','show','vim4-manager','-p','ExecStartPre','--value'],text=True)
assert re.search(r'fan-restore[^}]*code=exited[^}]*status=0(?:\s|;)',pre),pre
journal=subprocess.check_output(['journalctl','-b','-u','vim4-manager','--no-pager','-o','cat'],text=True)
assert not re.search(r'Traceback|partially applied|not applied|Failed',journal),journal
print(json.dumps(dict(passed=True,saved_config_present=saved_config_hex is not None,trip_count=90,zones=tables,exec_start_pre=pre,journal=journal)))

