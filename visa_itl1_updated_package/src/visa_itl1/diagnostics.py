from __future__ import annotations
import pandas as pd


def visa_geography_coverage(prepared_visa: pd.DataFrame) -> pd.DataFrame:
    fields = [
        "postcode_area_key", "postcode_district_key",
        "postcode_sector_key", "full_postcode_key",
    ]
    total = len(prepared_visa)
    return pd.DataFrame([
        {
            "geography_level": field,
            "total_rows": total,
            "valid_rows": int(prepared_visa[field].notna().sum()),
            "missing_or_invalid_rows": int(prepared_visa[field].isna().sum()),
            "coverage_rate": float(prepared_visa[field].notna().mean()) if total else 0.0,
        }
        for field in fields
    ])


def match_summary(total: int, matched: int, label: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "stage": label,
        "total_records": total,
        "matched_records": matched,
        "unmatched_records": total - matched,
        "match_rate": matched / total if total else 0.0,
    }])
