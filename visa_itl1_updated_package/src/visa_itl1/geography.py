"""Vectorised UK postcode cleaning and component construction."""
from __future__ import annotations
import re
import pandas as pd

NON_ALNUM = re.compile(r"[^A-Z0-9]")
AREA_PATTERN = r"^([A-Z]{1,2})"
DISTRICT_PATTERN = r"^([A-Z]{1,2}[0-9][0-9A-Z]?)"
FULL_POSTCODE_PATTERN = r"^[A-Z]{1,2}[0-9][0-9A-Z]?[0-9][A-Z]{2}$"


def clean_component(values: pd.Series) -> pd.Series:
    return (
        values.astype("string")
        .str.upper()
        .str.strip()
        .str.replace(NON_ALNUM, "", regex=True)
        .replace("", pd.NA)
    )


def normalise_full_postcode(values: pd.Series) -> pd.Series:
    return clean_component(values)


def extract_postcode_area(values: pd.Series) -> pd.Series:
    return clean_component(values).str.extract(AREA_PATTERN, expand=False).astype("string")


def normalise_postcode_area(values: pd.Series) -> pd.Series:
    cleaned = clean_component(values)
    valid = cleaned.str.fullmatch(r"[A-Z]{1,2}", na=False)
    return cleaned.where(valid)


def normalise_postcode_district(values: pd.Series) -> pd.Series:
    cleaned = clean_component(values)
    extracted = cleaned.str.extract(DISTRICT_PATTERN, expand=False).astype("string")
    valid = cleaned.str.fullmatch(r"[A-Z]{1,2}[0-9][0-9A-Z]?", na=False)
    return extracted.where(valid)


def normalise_sector_component(values: pd.Series) -> pd.Series:
    cleaned = clean_component(values)
    return cleaned.where(cleaned.str.fullmatch(r"[0-9]", na=False))


def normalise_unit_component(values: pd.Series) -> pd.Series:
    cleaned = clean_component(values)
    return cleaned.where(cleaned.str.fullmatch(r"[A-Z]{2}", na=False))


def construct_sector(district: pd.Series, sector: pd.Series) -> pd.Series:
    d = normalise_postcode_district(district)
    s = normalise_sector_component(sector)
    return (d.fillna("") + s.fillna("")).where(d.notna() & s.notna())


def construct_full_postcode(
    district: pd.Series, sector: pd.Series, unit: pd.Series
) -> pd.Series:
    d = normalise_postcode_district(district)
    s = normalise_sector_component(sector)
    u = normalise_unit_component(unit)
    result = d.fillna("") + s.fillna("") + u.fillna("")
    valid = result.str.fullmatch(FULL_POSTCODE_PATTERN, na=False)
    return result.where(d.notna() & s.notna() & u.notna() & valid)
