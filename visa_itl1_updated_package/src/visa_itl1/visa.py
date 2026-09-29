"""Prepare Visa data supplied in long-form postcode geography."""

from __future__ import annotations

import pandas as pd

from .exceptions import SchemaError
from .geography import (
    clean_component,
    extract_postcode_area,
    normalise_full_postcode,
    normalise_postcode_area,
    normalise_postcode_district,
)
from .validation import (
    require_columns,
    validate_area_controls,
    validate_postcode_level_config,
    validate_visa_level_values,
)


def normalise_level(
    values: pd.Series,
) -> pd.Series:
    """Normalise Visa postcode-level labels."""

    return (
        values.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


def prepare_visa(
    visa: pd.DataFrame,
    *,
    postcode_level_column: str,
    postcode_code_column: str,
    postcode_levels: dict[str, str],
    spend_columns: list[str],
    dimensions: list[str],
    suppressed_tokens: list[str] | None = None,
    unknown_level_policy: str = "error",
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Prepare Visa data containing one geography-level column and
    one corresponding postcode-code column.

    For example:

    postcode_level    postcode
    ---------------   --------
    All               All
    Area              M
    District          M1
    Sector            M1 1
    Unit              M1 1AA
    """
    required_columns = [
        postcode_level_column,
        postcode_code_column,
        *spend_columns,
        *dimensions,
    ]

    require_columns(
        visa,
        required_columns,
        "Visa",
    )

    configured_levels = (
        validate_postcode_level_config(
            postcode_levels
        )
    )

    data = visa.copy()
    data["source_row_id"] = range(len(data))

    data["postcode_level_key"] = normalise_level(
        data[postcode_level_column]
    )

    data["postcode_code_raw"] = (
        data[postcode_code_column]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
    )

    data["postcode_code_clean"] = (
        clean_component(
            data[postcode_code_column]
        )
    )

    string_columns = [
        "postcode_area_key",
        "postcode_district_key",
        "postcode_sector_key",
        "full_postcode_key",
        "geography_type_detected",
        "geography_status",
    ]

    for column in string_columns:
        data[column] = pd.Series(
            pd.NA,
            index=data.index,
            dtype="string",
        )

    all_mask = data["postcode_level_key"].eq(
        configured_levels["all"]
    )

    area_mask = data["postcode_level_key"].eq(
        configured_levels["area"]
    )

    district_mask = data[
        "postcode_level_key"
    ].eq(
        configured_levels["district"]
    )

    sector_mask = data["postcode_level_key"].eq(
        configured_levels["sector"]
    )

    unit_label = configured_levels.get("unit")

    if unit_label is not None:
        unit_mask = data[
            "postcode_level_key"
        ].eq(unit_label)
    else:
        unit_mask = pd.Series(
            False,
            index=data.index,
        )

    recognised_mask = (
        all_mask
        | area_mask
        | district_mask
        | sector_mask
        | unit_mask
    )

    data.loc[
        ~recognised_mask,
        "geography_status",
    ] = "unknown_level"

    # All-level rows
    data.loc[
        all_mask,
        "geography_type_detected",
    ] = "all"

    data.loc[
        all_mask,
        "geography_status",
    ] = "all"

    # Area-level rows
    area_codes = normalise_postcode_area(
        data.loc[
            area_mask,
            postcode_code_column,
        ]
    )

    data.loc[
        area_mask,
        "postcode_area_key",
    ] = area_codes

    data.loc[
        area_mask & data[
            "postcode_area_key"
        ].notna(),
        "geography_type_detected",
    ] = "area"

    data.loc[
        area_mask & data[
            "postcode_area_key"
        ].notna(),
        "geography_status",
    ] = "valid"

    data.loc[
        area_mask & data[
            "postcode_area_key"
        ].isna(),
        "geography_status",
    ] = "invalid_for_reported_level"

    # District-level rows
    district_codes = (
        normalise_postcode_district(
            data.loc[
                district_mask,
                postcode_code_column,
            ]
        )
    )

    data.loc[
        district_mask,
        "postcode_district_key",
    ] = district_codes

    data.loc[
        district_mask,
        "postcode_area_key",
    ] = extract_postcode_area(
        data.loc[
            district_mask,
            postcode_code_column,
        ]
    )

    valid_district = (
        district_mask
        & data["postcode_district_key"].notna()
    )

    data.loc[
        valid_district,
        "geography_type_detected",
    ] = "district"

    data.loc[
        valid_district,
        "geography_status",
    ] = "valid"

    # Detect area codes reported at district level.
    district_parent_area = (
        district_mask
        & data["postcode_district_key"].isna()
    )

    parent_area_codes = (
        normalise_postcode_area(
            data.loc[
                district_parent_area,
                postcode_code_column,
            ]
        )
    )

    parent_area_indices = (
        parent_area_codes[
            parent_area_codes.notna()
        ].index
    )

    data.loc[
        parent_area_indices,
        "postcode_area_key",
    ] = parent_area_codes.loc[
        parent_area_indices
    ]

    data.loc[
        parent_area_indices,
        "geography_type_detected",
    ] = "area"

    data.loc[
        parent_area_indices,
        "geography_status",
    ] = "parent_at_child_level"

    unresolved_district = (
        district_mask
        & data["geography_status"].isna()
    )

    data.loc[
        unresolved_district,
        "geography_status",
    ] = "invalid_for_reported_level"

    # Sector-level rows
    sector_codes = clean_component(
        data.loc[
            sector_mask,
            postcode_code_column,
        ]
    )

    valid_sector_codes = sector_codes.where(
        sector_codes.str.fullmatch(
            r"[A-Z]{1,2}[0-9][0-9A-Z]?[0-9]",
            na=False,
        )
    )

    data.loc[
        sector_mask,
        "postcode_sector_key",
    ] = valid_sector_codes

    data.loc[
        sector_mask,
        "postcode_area_key",
    ] = extract_postcode_area(
        data.loc[
            sector_mask,
            postcode_code_column,
        ]
    )

    valid_sector = (
        sector_mask
        & data["postcode_sector_key"].notna()
    )

    data.loc[
        valid_sector,
        "geography_type_detected",
    ] = "sector"

    data.loc[
        valid_sector,
        "geography_status",
    ] = "valid"

    # Detect district or area codes reported at sector level.
    sector_parent_mask = (
        sector_mask
        & data["postcode_sector_key"].isna()
    )

    sector_parent_district = (
        normalise_postcode_district(
            data.loc[
                sector_parent_mask,
                postcode_code_column,
            ]
        )
    )

    district_parent_indices = (
        sector_parent_district[
            sector_parent_district.notna()
        ].index
    )

    data.loc[
        district_parent_indices,
        "postcode_district_key",
    ] = sector_parent_district.loc[
        district_parent_indices
    ]

    data.loc[
        district_parent_indices,
        "geography_type_detected",
    ] = "district"

    data.loc[
        district_parent_indices,
        "geography_status",
    ] = "parent_at_child_level"

    remaining_sector_parent = (
        sector_mask
        & data["geography_status"].isna()
    )

    sector_parent_area = normalise_postcode_area(
        data.loc[
            remaining_sector_parent,
            postcode_code_column,
        ]
    )

    area_parent_indices = (
        sector_parent_area[
            sector_parent_area.notna()
        ].index
    )

    data.loc[
        area_parent_indices,
        "postcode_area_key",
    ] = sector_parent_area.loc[
        area_parent_indices
    ]

    data.loc[
        area_parent_indices,
        "geography_type_detected",
    ] = "area"

    data.loc[
        area_parent_indices,
        "geography_status",
    ] = "parent_at_child_level"

    data.loc[
        sector_mask
        & data["geography_status"].isna(),
        "geography_status",
    ] = "invalid_for_reported_level"

    # Optional unit-level rows
    if unit_mask.any():
        unit_codes = normalise_full_postcode(
            data.loc[
                unit_mask,
                postcode_code_column,
            ]
        )

        valid_unit_codes = unit_codes.where(
            unit_codes.str.fullmatch(
                r"[A-Z]{1,2}[0-9][0-9A-Z]?"
                r"[0-9][A-Z]{2}",
                na=False,
            )
        )

        data.loc[
            unit_mask,
            "full_postcode_key",
        ] = valid_unit_codes

        data.loc[
            unit_mask,
            "postcode_area_key",
        ] = extract_postcode_area(
            data.loc[
                unit_mask,
                postcode_code_column,
            ]
        )

        valid_unit = (
            unit_mask
            & data["full_postcode_key"].notna()
        )

        data.loc[
            valid_unit,
            "geography_type_detected",
        ] = "unit"

        data.loc[
            valid_unit,
            "geography_status",
        ] = "valid"

        data.loc[
            unit_mask
            & data["geography_status"].isna(),
            "geography_status",
        ] = "invalid_for_reported_level"

    # Missing geography codes
    missing_code = (
        recognised_mask
        & data["postcode_code_raw"].isna()
    )

    data.loc[
        missing_code,
        "geography_status",
    ] = "missing_code"

    level_summary = validate_visa_level_values(
        data,
        postcode_levels=postcode_levels,
        unknown_policy=unknown_level_policy,
    )

    tokens = {
        str(token).strip().lower()
        for token in (suppressed_tokens or [])
    }

    spend_quality_rows = []

    for spend_column in spend_columns:
        raw = (
            data[spend_column]
            .astype("string")
            .str.strip()
        )

        suppressed = raw.str.lower().isin(
            tokens
        )

        numeric = pd.to_numeric(
            raw.where(~suppressed),
            errors="coerce",
        )

        invalid_numeric = (
            raw.notna()
            & ~suppressed
            & numeric.isna()
        )

        if invalid_numeric.any():
            examples = (
                raw.loc[invalid_numeric]
                .drop_duplicates()
                .head()
                .tolist()
            )

            raise SchemaError(
                f"Visa {spend_column} contains "
                "invalid non-numeric values: "
                f"{examples}"
            )

        data[spend_column] = numeric

        data[
            f"{spend_column}_suppressed"
        ] = suppressed

        spend_quality_rows.append(
            {
                "spend_column": spend_column,
                "valid_rows": int(
                    numeric.notna().sum()
                ),
                "suppressed_rows": int(
                    suppressed.sum()
                ),
                "missing_rows": int(
                    numeric.isna().sum()
                    - suppressed.sum()
                ),
            }
        )

    spend_quality = pd.DataFrame(
        spend_quality_rows
    )

    return (
        data,
        spend_quality,
        level_summary,
    )


def create_area_controls(
    prepared_visa: pd.DataFrame,
    *,
    area_level_label: str,
    spend_columns: list[str],
    dimensions: list[str],
) -> pd.DataFrame:
    """
    Create postcode-area controls from genuine area-level rows.

    Parent-area codes reported at district or sector level are
    excluded from the primary controls.
    """
    area_level_key = (
        str(area_level_label)
        .strip()
        .upper()
    )

    require_columns(
        prepared_visa,
        [
            "postcode_level_key",
            "postcode_area_key",
            "geography_status",
            *dimensions,
            *spend_columns,
        ],
        "Prepared Visa data",
    )

    genuine_area_rows = prepared_visa.loc[
        prepared_visa[
            "postcode_level_key"
        ].eq(area_level_key)
        & prepared_visa[
            "geography_status"
        ].eq("valid")
        & prepared_visa[
            "postcode_area_key"
        ].notna()
    ].copy()

    control_keys = [
        *dimensions,
        "postcode_area_key",
    ]

    area_controls = (
        genuine_area_rows.groupby(
            control_keys,
            dropna=False,
            as_index=False,
        )[spend_columns]
        .sum(min_count=1)
    )

    validate_area_controls(
        area_controls,
        dimensions=dimensions,
        spend_columns=spend_columns,
    )

    return area_controls
