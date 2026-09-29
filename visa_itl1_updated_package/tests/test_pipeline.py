import pandas as pd
from visa_itl1.nspl import prepare_nspl
from visa_itl1.addressbase import prepare_commercial_properties
from visa_itl1.weights import build_postcode_area_itl1_weights
from visa_itl1.visa import prepare_visa, create_area_controls
from visa_itl1.allocation import allocate_visa_area_controls

def test_end_to_end_fractional_allocation():
    nspl = pd.DataFrame({
        "postcode": ["AB1 1AA", "AB2 2BB", "CD1 1AA"],
        "rgn_code": ["R1", "R2", "R2"],
    })
    lookup, invalid = prepare_nspl(
        nspl, postcode_column="postcode", region_code_column="rgn_code",
        region_names={"R1": "One", "R2": "Two"},
    )
    address = pd.DataFrame({
        "postcode": ["AB1 1AA"] * 3 + ["AB2 2BB"] * 2 + ["CD1 1AA"],
        "classification_code": ["C"] * 6,
    })
    commercial, _, _ = prepare_commercial_properties(
        address, postcode_column="postcode", classification_column="classification_code",
        classification_rule={"mode": "prefix", "include_prefixes": ["C"]},
    )
    weights, unmatched, diagnostic = build_postcode_area_itl1_weights(commercial, lookup)
    ab = weights[weights.postcode_area.eq("AB")].set_index("itl1_code").allocation_weight.to_dict()
    assert ab == {"R1": 0.6, "R2": 0.4}
    assert unmatched.empty and diagnostic.valid.all()

    visa = pd.DataFrame({
        "postcode_area": ["AB", "CD"], "postcode_district": ["AB1", "CD1"],
        "sector": ["1", "1"], "unit": ["AA", "AA"],
        "period": ["2024-01", "2024-01"], "mcg": ["A", "A"],
        "spend": [100.0, 50.0],
    })
    prepared, _ = prepare_visa(
        visa, area_column="postcode_area", district_column="postcode_district",
        sector_column="sector", unit_column="unit", spend_columns=["spend"],
        dimensions=["period", "mcg"],
    )
    controls = create_area_controls(prepared, spend_columns=["spend"], dimensions=["period", "mcg"])
    result, missing, audit = allocate_visa_area_controls(
        controls, weights, spend_columns=["spend"], dimensions=["period", "mcg"]
    )
    assert missing.empty
    assert result["spend_allocated"].sum() == 150.0
    assert audit.loc[0, "valid"]
