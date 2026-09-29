from __future__ import annotations
from pathlib import Path
import json
import yaml
from .io import read_table, write_table
from .nspl import prepare_nspl
from .addressbase import prepare_commercial_properties
from .weights import build_postcode_area_itl1_weights
from .visa import prepare_visa, create_area_controls
from .allocation import allocate_visa_area_controls
from .diagnostics import visa_geography_coverage, match_summary


def run_pipeline(
    *, nspl_path: str, addressbase_path: str, visa_path: str,
    config_path: str, output_dir: str,
) -> None:
    cfg = yaml.safe_load(Path(config_path).read_text())
    nspl_cfg, ab_cfg = cfg["nspl"], cfg["addressbase"]
    visa_cfg, alloc_cfg = cfg["visa"], cfg["allocation"]
    out = Path(output_dir)

    nspl_lookup, nspl_invalid = prepare_nspl(
        read_table(nspl_path),
        postcode_column=nspl_cfg["postcode_column"],
        region_code_column=nspl_cfg["region_code_column"],
        region_names=cfg["region_names"],
    )
    commercial, class_summary, commercial_invalid = prepare_commercial_properties(
        read_table(addressbase_path),
        postcode_column=ab_cfg["postcode_column"],
        classification_column=ab_cfg["classification_column"],
        classification_rule=ab_cfg["classification_filter"],
        property_id_column=ab_cfg.get("property_id_column"),
        deduplicate_properties=ab_cfg.get("deduplicate_properties", False),
    )
    weights, unmatched_address, weight_diagnostics = build_postcode_area_itl1_weights(
        commercial, nspl_lookup,
        tolerance=alloc_cfg.get("weight_tolerance", 1e-10),
    )
    prepared_visa, spend_summary, level_summary = (
        prepare_visa(
            read_table(visa_path),
            postcode_level_column=visa_cfg["postcode_level_column"],
            postcode_code_column=visa_cfg["postcode_code_column"],
            postcode_levels=visa_cfg["postcode_levels"],
            spend_columns=visa_cfg["spend_columns"],
            dimensions=visa_cfg.get("dimensions", []),
            suppressed_tokens=(
                visa_cfg.get(
                    "suppressed_tokens",
                    [],
                )
            ),
            unknown_level_policy=(
                visa_cfg.get(
                    "unknown_level_policy",
                    "error",
                )
            ),
        )
    )
    area_controls = create_area_controls(
        prepared_visa,
        area_level_label=(
            visa_cfg["postcode_levels"]["area"]
        ),
        spend_columns=(
            visa_cfg["spend_columns"]
        ),
        dimensions=(
            visa_cfg.get("dimensions", [])
        ),
    )
    result, unmatched_visa, reconciliation = allocate_visa_area_controls(
        area_controls, weights,
        spend_columns=visa_cfg["spend_columns"],
        dimensions=visa_cfg.get("dimensions", []),
        unmatched_policy=alloc_cfg.get("unmatched_policy", "retain"),
        reconciliation_tolerance=alloc_cfg.get("reconciliation_tolerance", 1e-8),
    )

    paths = {
        "main": out / "main", "lookups": out / "lookups",
        "diagnostics": out / "diagnostics", "reconciliation": out / "reconciliation",
    }
    for path in paths.values(): path.mkdir(parents=True, exist_ok=True)
    write_table(result, paths["main"] / "visa_itl1.parquet")
    write_table(nspl_lookup, paths["lookups"] / "nspl_postcode_itl1.parquet")
    write_table(weights, paths["lookups"] / "postcode_area_itl1_weights.parquet")
    write_table(class_summary, paths["diagnostics"] / "addressbase_classification_summary.csv")
    write_table(nspl_invalid, paths["diagnostics"] / "nspl_invalid_rows.parquet")
    write_table(commercial_invalid, paths["diagnostics"] / "addressbase_invalid_postcodes.parquet")
    write_table(unmatched_address, paths["diagnostics"] / "addressbase_unmatched_nspl.parquet")
    write_table(weight_diagnostics, paths["diagnostics"] / "weight_validation.csv")
    write_table(weights[weights["cross_boundary"]], paths["diagnostics"] / "cross_boundary_postcode_areas.csv")
    write_table(visa_geography_coverage(prepared_visa), paths["diagnostics"] / "visa_geography_coverage.csv")
    write_table(spend_summary, paths["diagnostics"] / "visa_spend_quality.csv")
    write_table(unmatched_visa, paths["diagnostics"] / "visa_unmatched_postcode_areas.parquet")
    write_table(reconciliation, paths["reconciliation"] / "reconciliation_overall.csv")
    write_table(match_summary(len(commercial), len(commercial)-len(unmatched_address), "AddressBase to NSPL"), paths["diagnostics"] / "addressbase_nspl_match_summary.csv")
    (out / "run_config.yml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    manifest = {"package_version": "0.2.0", "output_files": [str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
