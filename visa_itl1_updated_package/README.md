# Visa ITL1 allocation package

This package creates modelled ITL1 Visa estimates using postcode-area control totals and AddressBase commercial-property shares.

## Method

1. Clean NSPL full postcodes and map each to an ITL1 code and name.
2. Filter property-level AddressBase records using configurable `classification_code` rules.
3. Optionally deduplicate AddressBase using a configured property identifier.
4. Match commercial-property postcodes to NSPL.
5. Count commercial properties by postcode area and ITL1.
6. Convert counts to fractional postcode-area-to-ITL1 weights.
7. Parse Visa postcode area, district, sector and unit fields.
8. Aggregate Visa values to postcode-area controls by configured dimensions.
9. Allocate each control total fractionally to ITL1.
10. Write matching, coverage, cross-boundary and reconciliation diagnostics.

## Important configuration decisions

- `include_prefixes: [C]` is illustrative. Replace it with the approved AddressBase business-property rule.
- Paste the approved ITL1 code/name dictionary into `region_names`.
- Set the actual Visa spend columns and non-geographic dimensions such as period and MCG.
- If AddressBase has repeated rows per property, configure `property_id_column` and set `deduplicate_properties: true`.
- Suppressed Visa values remain missing. They are never converted to zero.

## Install and run

```bash
python -m pip install -e ".[dev]"
pytest
visa-itl1 \
  --nspl data/nspl.parquet \
  --addressbase data/addressbase.parquet \
  --visa data/visa.parquet \
  --config config/example.yml \
  --output outputs
```

## Output structure

```text
outputs/
├── main/visa_itl1.parquet
├── lookups/
│   ├── nspl_postcode_itl1.parquet
│   └── postcode_area_itl1_weights.parquet
├── diagnostics/
│   ├── addressbase_classification_summary.csv
│   ├── addressbase_nspl_match_summary.csv
│   ├── addressbase_unmatched_nspl.parquet
│   ├── cross_boundary_postcode_areas.csv
│   ├── visa_geography_coverage.csv
│   ├── visa_spend_quality.csv
│   ├── visa_unmatched_postcode_areas.parquet
│   └── weight_validation.csv
├── reconciliation/reconciliation_overall.csv
├── run_config.yml
└── manifest.json
```

## Current statistical boundary

The production estimate allocates postcode-area controls. District, sector and unit are parsed and retained for data-quality checks and later benchmark estimators, but they do not alter the primary AddressBase-weighted estimate.
