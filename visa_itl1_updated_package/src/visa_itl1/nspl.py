from __future__ import annotations
import pandas as pd
from .geography import normalise_full_postcode, extract_postcode_area
from .validation import require_columns, validate_region_dictionary
from .exceptions import GeographyError


def prepare_nspl(
    nspl: pd.DataFrame,
    *,
    postcode_column: str,
    region_code_column: str,
    region_names: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    require_columns(nspl, [postcode_column, region_code_column], "NSPL")
    data = nspl[[postcode_column, region_code_column]].copy()
    data["full_postcode"] = normalise_full_postcode(data[postcode_column])
    data["itl1_code"] = data[region_code_column].astype("string").str.strip()
    invalid = data[data["full_postcode"].isna() | data["itl1_code"].isna()].copy()
    valid = data.dropna(subset=["full_postcode", "itl1_code"]).copy()
    conflict = valid.groupby("full_postcode")["itl1_code"].nunique()
    if conflict.gt(1).any():
        examples = conflict[conflict.gt(1)].head().index.tolist()
        raise GeographyError(f"NSPL postcodes map to multiple ITL1 codes: {examples}")
    valid = valid.drop_duplicates("full_postcode")
    validate_region_dictionary(valid["itl1_code"], region_names)
    valid["itl1_name"] = valid["itl1_code"].map(region_names)
    valid["postcode_area"] = extract_postcode_area(valid["full_postcode"])
    return valid[["full_postcode", "postcode_area", "itl1_code", "itl1_name"]], invalid
