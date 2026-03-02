import shutil
import statsmodels.api as sm

    # 1) Check the binary on PATH
for cand in ("x13as", "x13as.exe", "x13","x13as_ascii.exe"):
  p = shutil.which(cand)
  if p:
    print(f"Found X-13 binary on PATH: {p}")
    break
else:
  print("X-13 binary not found on PATH. If you're on macOS and conda x13as is unavailable,\
"
        "install via Homebrew: brew install x13; then re-open the terminal.")

# 2) Try a tiny run via statsmodels (will raise if unavailable)
try:
  from statsmodels.tsa.x13 import x13_arima_analysis
  import pandas as pd
  import numpy as np
  idx = pd.date_range("2018-01-31", periods=60, freq="M")
  y = pd.Series(np.random.default_rng(0).normal(0,1,len(idx)).cumsum()+100, index=idx)
  res = x13_arima_analysis(y, x12path=r"C:\\ONSapps\\My_Spyder\\Library\\bin\\x13as_ascii.exe", tmpdir=r"D:\x13tmp")
  print("statsmodels x13_arima_analysis() ran successfully.")
except Exception as e:
  print("statsmodels x13_arima_analysis() failed:", repr(e))
