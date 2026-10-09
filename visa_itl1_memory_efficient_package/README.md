# Memory-efficient Visa to ITL1 package

Creates separate ITL1 estimates from Visa area, district and sector records using AddressBase commercial-property shares.

## Memory design
- Does not copy the complete AddressBase dataframe.
- Filters to `classification_code == C`, keeps only required columns and immediately aggregates to full-postcode counts.
- Supports already aggregated postcode counts.
- Deletes property-level intermediates before NSPL matching.
- Builds compact area, district and sector lookup weights.
- Processes Visa levels independently and never adds them together.
- Writes memory, matching, geography and reconciliation diagnostics.

## Run
```bash
python -m pip install -e ".[dev]"
pytest
visa-itl1 --nspl data/nspl.parquet --addressbase data/addressbase.parquet --visa data/visa.parquet --config config/example.yml --output outputs
```
