import pandas as pd
from .validation import require_columns
from .exceptions import GeographyError
from .geography import full
def prepare_nspl(df,*,postcode_column,region_code_column,region_names):
 require_columns(df,[postcode_column,region_code_column],"NSPL"); pc=full(df[postcode_column]); rc=df[region_code_column].astype("string").str.strip().replace("",pd.NA); x=pd.DataFrame({"full_postcode":pc,"itl1_code":rc}).dropna(); conflicts=x.groupby("full_postcode").itl1_code.nunique()
 if conflicts.gt(1).any(): raise GeographyError("conflicting NSPL mappings")
 x.drop_duplicates("full_postcode",inplace=True); missing=set(x.itl1_code.unique())-set(region_names)
 if missing: raise GeographyError(f"region_names missing codes: {sorted(missing)}")
 x["itl1_name"]=x.itl1_code.map(region_names); invalid=pd.DataFrame({"full_postcode":pc,"itl1_code":rc}).loc[pc.isna()|rc.isna()]; return x,invalid
