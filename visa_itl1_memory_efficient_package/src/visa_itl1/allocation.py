import pandas as pd
from .exceptions import GeographyError,ReconciliationError
def allocate_level_controls(controls,weights,*,level,spend_columns,dimensions,unmatched_policy="retain",reconciliation_tolerance=1e-8):
 w=weights.loc[weights.geography_level.eq(level)]; j=controls.merge(w,on="geography_code",how="left",validate="many_to_many",copy=False); u=j.loc[j.allocation_weight.isna()].copy()
 if unmatched_policy=="error" and not u.empty: raise GeographyError(f"unmatched {level} controls")
 m=j.dropna(subset=["allocation_weight"]).copy(); outs=[]
 for c in spend_columns: n=f"{c}_allocated"; m[n]=m[c]*m.allocation_weight; outs.append(n)
 r=m.groupby([*dimensions,"itl1_code","itl1_name"],sort=False,dropna=False,as_index=False)[outs].sum(min_count=1); known=set(w.geography_code); audit=[]
 for c,o in zip(spend_columns,outs):
  inp=controls.loc[controls.geography_code.isin(known),c].sum(min_count=1); val=r[o].sum(min_count=1); diff=val-inp; ok=pd.isna(diff) or abs(float(diff))<=reconciliation_tolerance*max(1,abs(float(inp))); audit.append({"geography_level":level,"spend_column":c,"matched_input_total":inp,"allocated_total":val,"difference":diff,"valid":ok,"unmatched_input_total":controls.loc[~controls.geography_code.isin(known),c].sum(min_count=1)})
 a=pd.DataFrame(audit)
 if not a.valid.all(): raise ReconciliationError(a.to_dict("records"))
 return r,u,a
