import pandas as pd
from visa_itl1.addressbase import prepare_commercial_property_counts
from visa_itl1.nspl import prepare_nspl
from visa_itl1.weights import match_counts_to_nspl,build_all_geography_weights
from visa_itl1.visa import prepare_visa,create_level_controls
from visa_itl1.allocation import allocate_level_controls
def test_flow():
 ab=pd.DataFrame({"pc":["AB1 1AA"]*3+["AB2 2BB"]*2+["CD1 1AA"],"cl":["C"]*6}); counts,_,_=prepare_commercial_property_counts(ab,postcode_column="pc",classification_column="cl"); ns,_=prepare_nspl(pd.DataFrame({"pc":["AB1 1AA","AB2 2BB","CD1 1AA"],"r":["R1","R2","R2"]}),postcode_column="pc",region_code_column="r",region_names={"R1":"One","R2":"Two"}); matched,_=match_counts_to_nspl(counts,ns); w,d=build_all_geography_weights(matched,["area","district","sector"]); assert w.query("geography_level=='area' and geography_code=='AB'").set_index("itl1_code").allocation_weight.to_dict()=={"R1":.6,"R2":.4}
 visa=pd.DataFrame({"level":["Postal Area"],"code":["AB"],"period":["2024-01"],"mcg":["A"],"spend":[100.]}); p,_,_=prepare_visa(visa,postcode_level_column="level",postcode_code_column="code",postcode_levels={"all":"All","area":"Postal Area","district":"Postal District","sector":"Postal Sector"},spend_columns=["spend"],dimensions=["period","mcg"]); c=create_level_controls(p,level="area",level_label="Postal Area",spend_columns=["spend"],dimensions=["period","mcg"]); out,u,a=allocate_level_controls(c,w,level="area",spend_columns=["spend"],dimensions=["period","mcg"]); assert u.empty and out.spend_allocated.sum()==100 and a.valid.all()
