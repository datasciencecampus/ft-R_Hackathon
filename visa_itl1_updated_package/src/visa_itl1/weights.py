from __future__ import annotations
import pandas as pd
from .validation import validate_weights


def build_postcode_area_itl1_weights(
    commercial_properties: pd.DataFrame,
    nspl_lookup: pd.DataFrame,
    *,
    tolerance: float = 1e-10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    joined = commercial_properties.merge(
        nspl_lookup[["full_postcode", "itl1_code", "itl1_name"]],
        on="full_postcode", how="left", validate="many_to_one",
    )
    unmatched = joined.loc[joined["itl1_code"].isna()].copy()
    matched = joined.dropna(subset=["itl1_code"]).copy()
    counts = (
        matched.groupby(["postcode_area", "itl1_code", "itl1_name"],
                        as_index=False, dropna=False)
        .size().rename(columns={"size": "commercial_property_count"})
    )
    counts["postcode_area_property_count"] = counts.groupby("postcode_area")[
        "commercial_property_count"
    ].transform("sum")
    counts["allocation_weight"] = (
        counts["commercial_property_count"] / counts["postcode_area_property_count"]
    )
    counts["number_of_itl1_regions"] = counts.groupby("postcode_area")[
        "itl1_code"
    ].transform("nunique")
    counts["cross_boundary"] = counts["number_of_itl1_regions"].gt(1)
    diagnostics = validate_weights(counts, tolerance)
    return counts.sort_values(["postcode_area", "itl1_code"]), unmatched, diagnostics
