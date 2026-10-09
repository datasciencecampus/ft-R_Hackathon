import pandas as pd
from .exceptions import SchemaError,GeographyError
def require_columns(df,cols,label):
 m=sorted(set(cols)-set(df.columns))
 if m: raise SchemaError(f"{label} missing columns: {m}")
def validate_levels(x):
 req={"all","area","district","sector"}; m=req-set(x)
 if m: raise SchemaError(f"postcode_levels missing: {sorted(m)}")
 out={k:str(v).strip().upper() for k,v in x.items()}
 if len(set(out.values()))!=len(out): raise SchemaError("postcode level labels must be unique")
 return out
def validate_weights(w,tol):
 s=w.groupby(["geography_level","geography_code"],as_index=False).agg(weight_sum=("allocation_weight","sum"),region_count=("itl1_code","nunique"),commercial_property_count=("commercial_property_count","sum")); s["absolute_error"]=(s.weight_sum-1).abs(); s["valid"]=s.absolute_error.le(tol)
 if not s.valid.all(): raise GeographyError("weights do not sum to one")
 return s
