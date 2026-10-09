import gc,pandas as pd
from .geography import area,district,sector
from .validation import require_columns,validate_weights
def match_counts_to_nspl(counts,nspl):
 require_columns(counts,["full_postcode","commercial_property_count"],"counts"); x=counts.merge(nspl,on="full_postcode",how="left",validate="one_to_one",copy=False); u=x.loc[x.itl1_code.isna(),["full_postcode","commercial_property_count"]].copy(); return x.dropna(subset=["itl1_code"]),u
def build_level_weights(matched,level):
 f={"area":area,"district":district,"sector":sector}[level]; t=pd.DataFrame({"geography_code":f(matched.full_postcode),"itl1_code":matched.itl1_code,"itl1_name":matched.itl1_name,"commercial_property_count":matched.commercial_property_count}).dropna(subset=["geography_code"]); o=t.groupby(["geography_code","itl1_code","itl1_name"],sort=False,as_index=False).commercial_property_count.sum(); o["allocation_weight"]=o.commercial_property_count/o.groupby("geography_code",sort=False).commercial_property_count.transform("sum"); o["geography_level"]=level; o["cross_boundary"]=o.groupby("geography_code",sort=False).itl1_code.transform("nunique").gt(1); return o[["geography_level","geography_code","itl1_code","itl1_name","commercial_property_count","allocation_weight","cross_boundary"]]
def build_all_geography_weights(matched,levels,tolerance=1e-10):
 frames=[]
 for level in levels: frames.append(build_level_weights(matched,level)); gc.collect()
 w=pd.concat(frames,ignore_index=True); return w,validate_weights(w,tolerance)
