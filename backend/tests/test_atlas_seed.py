import json
from pathlib import Path

from scripts.seed_atlas import build_atlas_document


def test_atlas_seed_records_are_source_labeled_and_non_private():
    seed_path = Path(__file__).resolve().parents[1] / "data" / "mizaaj_atlas_seed_v2.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))

    assert seed["dataset_name"] == "mizaaj_atlas_seed_v2"
    assert len(seed["records"]) >= 8

    for record in seed["records"]:
        document = build_atlas_document(record)
        assert "demo_queries" not in record
        assert "observed_facts" not in record
        assert "fit_signals" not in record
        assert record["identity"]["canonical_url"].startswith("https://")
        assert record["source_facts"]
        assert record["derived_rules"]
        assert "public product evidence" in document
        assert "Private Mizaaj memory overrides Atlas" in document
        assert record["identity"]["brand"] in document
        assert "atlas" in record["tags"]


def test_product_atlas_records_have_identity_or_are_explicit_category_signals():
    seed_path = Path(__file__).resolve().parents[1] / "data" / "mizaaj_atlas_seed_v2.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    record_ids = {record["id"] for record in seed["records"]}

    for record in seed["records"]:
        identity = record["identity"]
        if record["kind"] == "product":
            assert identity["style_number"], record["id"]
            assert any(tag == "identity:style-number" for tag in record["tags"])
            for guide_id in record.get("related_size_guides", []):
                assert guide_id in record_ids
        else:
            assert any(
                tag in {"identity:category-signal", "kind:size-guide"} for tag in record["tags"]
            )


def test_size_guides_are_structured_chart_records():
    seed_path = Path(__file__).resolve().parents[1] / "data" / "mizaaj_atlas_seed_v2.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))

    guides = [
        record
        for record in seed["records"]
        if record["kind"] in {"brand_size_guide", "product_size_guide"}
    ]
    assert len(guides) >= 4

    for guide in guides:
        document = build_atlas_document(guide)
        assert guide["size_chart"]
        assert "Chart scope:" in document
        assert "Measurement type:" in document
        for chart in guide["size_chart"]:
            assert chart["columns"]
            assert chart["rows"]
