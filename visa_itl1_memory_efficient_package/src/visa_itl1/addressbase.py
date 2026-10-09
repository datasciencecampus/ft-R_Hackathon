import gc,pandas as pd
from .validation import require_columns
from .exceptions import SchemaError
from .geography import full
def prepare_commercial_property_counts(df,*,postcode_column,classification_column=None,commercial_classification="C",missing_classification_policy="exclude",property_id_column=None,deduplicate_properties=False,input_mode="raw",count_column="commercial_property_count"):
 if input_mode=="postcode_counts":
  require_columns(df,[postcode_column,count_column],"AddressBase counts"); pc=full(df[postcode_column]); n=pd.to_numeric(df[count_column],errors="coerce"); ok=pc.notna()&n.notna()&n.ge(0); out=pd.DataFrame({"full_postcode":pc[ok],"commercial_property_count":n[ok]}).groupby("full_postcode",sort=False,as_index=False).commercial_property_count.sum(); return out,pd.DataFrame(),pd.DataFrame([{"metric":"invalid_rows","value":int((~ok).sum())}])
 if input_mode!="raw" or not classification_column: raise SchemaError("raw mode requires classification_column")
 cols=[postcode_column,classification_column]+([property_id_column] if deduplicate_properties and property_id_column else []); require_columns(df,cols,"AddressBase")
 cls=df[classification_column].astype("string").str.strip().str.upper().replace("",pd.NA); missing=int(cls.isna().sum())
 if missing_classification_policy=="error" and missing: raise SchemaError("missing classification codes")
 summary=cls.value_counts(dropna=False).rename_axis("classification_code_clean").reset_index(name="record_count"); summary["is_commercial"]=summary.classification_code_clean.eq(str(commercial_classification).upper())
 mask=cls.eq(str(commercial_classification).strip().upper()); keep=[postcode_column]+([property_id_column] if deduplicate_properties else []); commercial=df.loc[mask,keep].copy(); del cls,mask; gc.collect(); commercial[postcode_column]=full(commercial[postcode_column]); invalid=int(commercial[postcode_column].isna().sum()); commercial.dropna(subset=[postcode_column],inplace=True)
 if deduplicate_properties:
  if not property_id_column: raise SchemaError("property_id_column required")
  commercial.drop_duplicates(property_id_column,inplace=True)
 counts=commercial.groupby(postcode_column,sort=False).size().rename("commercial_property_count").reset_index().rename(columns={postcode_column:"full_postcode"}); diag=pd.DataFrame([{"metric":"source_rows","value":len(df)},{"metric":"commercial_rows","value":len(commercial)},{"metric":"invalid_postcodes","value":invalid},{"metric":"unique_postcodes","value":len(counts)}]); del commercial; gc.collect(); return counts,summary,diag
