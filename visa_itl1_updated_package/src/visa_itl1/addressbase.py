from __future__ import annotations
import pandas as pd
from .classification import select_commercial_records
from .geography import normalise_full_postcode, extract_postcode_area
from .validation import require_columns
from .exceptions import SchemaError


def prepare_commercial_properties(
    addressbase: pd.DataFrame,
    *,
    postcode_column: str,
    classification_column: str,
    classification_rule: dict,
    property_id_column: str | None = None,
    deduplicate_properties: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = [postcode_column, classification_column]
    if deduplicate_properties:
        if not property_id_column:
            raise SchemaError("property_id_column is required for deduplication")
        required.append(property_id_column)
    require_columns(addressbase, required, "AddressBase")

    commercial, classification_summary = select_commercial_records(
        addressbase,
        classification_column=classification_column,
        rule=classification_rule,
    )
    commercial["full_postcode"] = normalise_full_postcode(commercial[postcode_column])
    commercial["postcode_area"] = extract_postcode_area(commercial["full_postcode"])
    invalid = commercial.loc[commercial["full_postcode"].isna()].copy()
    commercial = commercial.dropna(subset=["full_postcode", "postcode_area"]).copy()

    if deduplicate_properties:
        before = len(commercial)
        commercial = commercial.drop_duplicates(property_id_column)
        commercial.attrs["deduplicated_rows"] = before - len(commercial)
    return commercial, classification_summary, invalid
