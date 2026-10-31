import subprocess,sys,time,json
p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"])
print(json.dumps({"event":"test_child","pid":p.pid}),flush=True)
time.sleep(20)
