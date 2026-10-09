import pandas as pd
from .validation import require_columns,validate_levels
from .exceptions import SchemaError
from .geography import clean,exact_area,exact_district,exact_sector,full
def prepare_visa(df,*,postcode_level_column,postcode_code_column,postcode_levels,spend_columns,dimensions,suppressed_tokens=None,unknown_level_policy="retain"):
 require_columns(df,[postcode_level_column,postcode_code_column,*spend_columns,*dimensions],"Visa"); levels=validate_levels(postcode_levels); x=df.copy(deep=False); x["postcode_level_key"]=x[postcode_level_column].astype("string").str.strip().str.upper(); x["postcode_code_clean"]=clean(x[postcode_code_column]); x["geography_type_detected"]=pd.Series(pd.NA,index=x.index,dtype="string"); x["geography_status"]=pd.Series(pd.NA,index=x.index,dtype="string"); x["geography_code"]=pd.Series(pd.NA,index=x.index,dtype="string"); allm=x.postcode_level_key.eq(levels["all"]); x.loc[allm,["geography_type_detected","geography_status"]]=["all","all"]
 funcs={"area":exact_area,"district":exact_district,"sector":exact_sector,"unit":full}
 for level,func in funcs.items():
  if level not in levels: continue
  m=x.postcode_level_key.eq(levels[level]); p=func(x.loc[m,postcode_code_column]); idx=p[p.notna()].index; x.loc[idx,"geography_type_detected"]=level; x.loc[idx,"geography_status"]="valid"; x.loc[idx,"geography_code"]=p.loc[idx]
  unresolved=m&x.geography_status.isna(); a=exact_area(x.loc[unresolved,postcode_code_column]); ai=a[a.notna()].index; x.loc[ai,"geography_type_detected"]="area"; x.loc[ai,"geography_status"]="parent_at_child_level"; x.loc[ai,"geography_code"]=a.loc[ai]
  if level in {"sector","unit"}:
   unresolved=m&x.geography_status.isna(); d=exact_district(x.loc[unresolved,postcode_code_column]); di=d[d.notna()].index; x.loc[di,"geography_type_detected"]="district"; x.loc[di,"geography_status"]="parent_at_child_level"; x.loc[di,"geography_code"]=d.loc[di]
  x.loc[m&x.geography_status.isna(),"geography_status"]="invalid_for_reported_level"
 unknown=x.postcode_level_key.notna()&~x.postcode_level_key.isin(set(levels.values())); x.loc[unknown,"geography_status"]="unknown_level"
 if unknown_level_policy=="error" and unknown.any(): raise SchemaError("unknown Visa levels")
 tokens={str(v).strip().lower() for v in (suppressed_tokens or [])}; quality=[]
 for col in spend_columns:
  raw=x[col].astype("string").str.strip(); sup=raw.str.lower().isin(tokens); num=pd.to_numeric(raw.where(~sup),errors="coerce"); bad=raw.notna()&~sup&num.isna()
  if bad.any(): raise SchemaError(f"invalid values in {col}")
  x[col]=num; x[f"{col}_suppressed"]=sup; quality.append({"spend_column":col,"valid_rows":int(num.notna().sum()),"suppressed_rows":int(sup.sum()),"missing_rows":int(num.isna().sum()-sup.sum())})
 status=x.groupby(["postcode_level_key","geography_type_detected","geography_status"],dropna=False).size().rename("record_count").reset_index(); return x,pd.DataFrame(quality),status
def create_level_controls(prepared,*,level,level_label,spend_columns,dimensions):
 rows=prepared.loc[prepared.postcode_level_key.eq(str(level_label).upper())&prepared.geography_status.eq("valid")&prepared.geography_type_detected.eq(level),[*dimensions,"geography_code",*spend_columns]]; return rows.groupby([*dimensions,"geography_code"],sort=False,dropna=False,as_index=False)[spend_columns].sum(min_count=1)
