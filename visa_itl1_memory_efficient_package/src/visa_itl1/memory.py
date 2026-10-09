import os,gc,pandas as pd
try: import psutil
except ImportError: psutil=None
def enable_copy_on_write():
 try: pd.options.mode.copy_on_write=True
 except Exception: pass
def report(label,**frames):
 rss=psutil.Process(os.getpid()).memory_info().rss/1024**3 if psutil else None
 return pd.DataFrame([{"stage":label,"object":n,"rows":len(f),"dataframe_gb":f.memory_usage(index=True,deep=True).sum()/1024**3,"process_rss_gb":rss} for n,f in frames.items()])
def collect(): gc.collect()
