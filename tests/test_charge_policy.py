"""Simulate policy trajectories, restart state and invalid sensor/temperature inputs."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('charge',Path(__file__).resolve().parents[1]/'runtime/support/v30-charge-limit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
state=None;thermal=False
trajectory=[(74,'auto'),(76,'auto'),(79,'auto'),(80,'inhibit-charge'),(79,'inhibit-charge'),(76,'inhibit-charge'),(75,'auto')]
for cap,expected in trajectory:
 state,thermal,_=m.decide(cap,250,'Good',state,thermal);assert state==expected,(cap,state)
assert m.decide(78,250,'Good','inhibit-charge',False)[0]=='inhibit-charge'
assert m.decide(78,250,'Good',None,False)[0]=='inhibit-charge'
state,thermal,_=m.decide(60,400,'Good','auto',False)
assert state=='inhibit-charge' and thermal
assert m.decide(60,380,'Good',state,thermal)[0]=='inhibit-charge'
assert m.decide(60,370,'Good',state,thermal)[0]=='auto'
assert m.decide(60,50,'Good','auto',False)[0]=='inhibit-charge'
assert m.decide(60,60,'Good','inhibit-charge',True)[0]=='inhibit-charge'
assert m.decide(60,70,'Good','inhibit-charge',True)[0]=='auto'
for cap,temp,health in [(-1,250,'Good'),(101,250,'Good'),(60,1001,'Good'),(60,250,'Overheat')]:
 assert m.decide(cap,temp,health,'auto',False)[0]=='inhibit-charge'
print('PASS: 75/80 hysteresis, restart retention, missing-state conservative default, warm/cold recovery, invalid sensors and charger-health failures')
