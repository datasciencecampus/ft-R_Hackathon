import pandas as pd
from visa_itl1.geography import (
    extract_postcode_area, normalise_postcode_district,
    construct_sector, construct_full_postcode,
)

def test_geography_components():
    assert extract_postcode_area(pd.Series(["SW1A 1AA", "M1 1AE"])).tolist() == ["SW", "M"]
    assert normalise_postcode_district(pd.Series(["sw1a", "M1"])).tolist() == ["SW1A", "M1"]
    assert construct_sector(pd.Series(["SW1A"]), pd.Series(["1"])).iloc[0] == "SW1A1"
    assert construct_full_postcode(pd.Series(["SW1A"]), pd.Series(["1"]), pd.Series(["AA"])).iloc[0] == "SW1A1AA"
