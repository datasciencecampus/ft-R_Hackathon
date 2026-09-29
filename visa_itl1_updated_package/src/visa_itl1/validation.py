from __future__ import annotations
import pandas as pd
from .exceptions import SchemaError, GeographyError


def require_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise SchemaError(f"{label} missing required columns: {missing}")


def assert_no_null_keys(df: pd.DataFrame, columns: list[str], label: str) -> None:
    bad = df[columns].isna().any(axis=1)
    if bad.any():
        raise SchemaError(f"{label} contains {int(bad.sum())} rows with null keys")


def validate_region_dictionary(codes: pd.Series, region_names: dict[str, str]) -> None:
    observed = set(codes.dropna().astype(str).unique())
    missing = sorted(observed - set(region_names))
    if missing:
        raise GeographyError(
            "Region codes are absent from region_names dictionary: " + str(missing)
        )


def validate_weights(weights: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    summary = (
        weights.groupby("postcode_area", as_index=False)
        .agg(weight_sum=("allocation_weight", "sum"),
             region_count=("itl1_code", "nunique"),
             commercial_property_count=("commercial_property_count", "sum"))
    )
    summary["absolute_error"] = (summary["weight_sum"] - 1.0).abs()
    summary["valid"] = summary["absolute_error"] <= tolerance
    if not summary["valid"].all():
        sample = summary.loc[~summary["valid"]].head().to_dict("records")
        raise GeographyError(f"Postcode-area weights do not sum to one: {sample}")
    if weights["allocation_weight"].lt(0).any() or weights["allocation_weight"].gt(1).any():
        raise GeographyError("Allocation weights must be between zero and one")
    return summary
