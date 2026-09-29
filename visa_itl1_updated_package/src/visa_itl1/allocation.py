from __future__ import annotations
import pandas as pd
from .exceptions import GeographyError, ReconciliationError


def allocate_visa_area_controls(
    area_controls: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    spend_columns: list[str],
    dimensions: list[str],
    unmatched_policy: str = "retain",
    reconciliation_tolerance: float = 1e-8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    joined = area_controls.merge(
        weights,
        left_on="postcode_area_key", right_on="postcode_area",
        how="left", validate="many_to_many",
    )
    unmatched = joined.loc[joined["allocation_weight"].isna()].copy()
    if unmatched_policy == "error" and not unmatched.empty:
        areas = unmatched["postcode_area_key"].drop_duplicates().head().tolist()
        raise GeographyError(f"Visa postcode areas have no AddressBase weights: {areas}")
    if unmatched_policy not in {"retain", "error"}:
        raise GeographyError(f"Unsupported unmatched_policy: {unmatched_policy}")

    matched = joined.dropna(subset=["allocation_weight"]).copy()
    allocated_columns = []
    for column in spend_columns:
        out = f"{column}_allocated"
        matched[out] = matched[column] * matched["allocation_weight"]
        allocated_columns.append(out)

    group_keys = [*dimensions, "itl1_code", "itl1_name"]
    result = (
        matched.groupby(group_keys, dropna=False, as_index=False)[allocated_columns]
        .sum(min_count=1)
    )

    audit_rows = []
    matched_areas = set(weights["postcode_area"])
    input_matched = area_controls[area_controls["postcode_area_key"].isin(matched_areas)]
    for column, allocated_column in zip(spend_columns, allocated_columns):
        input_total = input_matched[column].sum(min_count=1)
        allocated_total = result[allocated_column].sum(min_count=1)
        difference = allocated_total - input_total
        scale = max(1.0, abs(float(input_total))) if pd.notna(input_total) else 1.0
        valid = pd.isna(difference) or abs(float(difference)) <= reconciliation_tolerance * scale
        audit_rows.append({
            "spend_column": column,
            "matched_input_total": input_total,
            "allocated_total": allocated_total,
            "difference": difference,
            "valid": valid,
            "unmatched_input_total": area_controls.loc[
                ~area_controls["postcode_area_key"].isin(matched_areas), column
            ].sum(min_count=1),
        })
    audit = pd.DataFrame(audit_rows)
    if not audit["valid"].all():
        raise ReconciliationError(
            "Allocation does not reconcile: " + str(audit.to_dict("records"))
        )
    return result, unmatched, audit
