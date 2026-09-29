import pandas as pd
from visa_itl1.classification import select_commercial_records

def test_prefix_classification_filter():
    df = pd.DataFrame({"classification_code": ["C", "CA", "R", None]})
    selected, summary = select_commercial_records(
        df, classification_column="classification_code",
        rule={"mode": "prefix", "include_prefixes": ["C"], "missing_policy": "exclude"},
    )
    assert selected["classification_code"].tolist() == ["C", "CA"]
    assert summary["record_count"].sum() == 4
