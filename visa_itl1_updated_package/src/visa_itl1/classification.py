from __future__ import annotations
import pandas as pd
from .exceptions import SchemaError


def clean_classification(values: pd.Series) -> pd.Series:
    return values.astype("string").str.upper().str.strip().replace("", pd.NA)


def select_commercial_records(
    addressbase: pd.DataFrame,
    *,
    classification_column: str,
    rule: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = addressbase.copy()
    codes = clean_classification(data[classification_column])
    data["classification_code_clean"] = codes

    missing_policy = rule.get("missing_policy", "exclude")
    if missing_policy == "error" and codes.isna().any():
        raise SchemaError("AddressBase contains missing classification codes")

    exact = {str(x).strip().upper() for x in rule.get("include_exact", [])}
    prefixes = tuple(str(x).strip().upper() for x in rule.get("include_prefixes", []))
    exclude_exact = {str(x).strip().upper() for x in rule.get("exclude_exact", [])}
    exclude_prefixes = tuple(str(x).strip().upper() for x in rule.get("exclude_prefixes", []))
    mode = rule.get("mode", "exact_or_prefix")

    exact_match = codes.isin(exact) if exact else pd.Series(False, index=data.index)
    prefix_match = codes.str.startswith(prefixes, na=False) if prefixes else pd.Series(False, index=data.index)
    if mode == "exact":
        include = exact_match
    elif mode == "prefix":
        include = prefix_match
    elif mode == "exact_or_prefix":
        include = exact_match | prefix_match
    else:
        raise SchemaError(f"Unsupported classification filter mode: {mode}")

    excluded = codes.isin(exclude_exact) if exclude_exact else pd.Series(False, index=data.index)
    if exclude_prefixes:
        excluded |= codes.str.startswith(exclude_prefixes, na=False)
    include &= ~excluded & codes.notna()

    summary = (
        data.assign(is_commercial=include)
        .groupby(["classification_code_clean", "is_commercial"], dropna=False)
        .size().rename("record_count").reset_index()
        .sort_values(["is_commercial", "record_count"], ascending=[False, False])
    )
    return data.loc[include].copy(), summary
