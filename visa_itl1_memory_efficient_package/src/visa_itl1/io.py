from pathlib import Path
import pandas as pd
def read_table(path):
 p=Path(path); return pd.read_csv(p,low_memory=False) if p.suffix.lower()==".csv" else pd.read_parquet(p)
def write_table(df,path):
 p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); df.to_csv(p,index=False) if p.suffix.lower()==".csv" else df.to_parquet(p,index=False)
