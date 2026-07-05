import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_SEED_FILE = Path(__file__).resolve().parents[1] / "data" / "mizaaj_atlas_seed_v2.json"


def build_atlas_document(record: dict[str, Any]) -> str:
    identity = record["identity"]
    facts = "\n".join(
        f"- {item['field']}: {item['value']} ({item['evidence']})"
        for item in record["source_facts"]
    )
    rules = "\n".join(
        (
            f"- {item['type']}: {item['value']} "
            f"Basis: {', '.join(item['basis_fields'])}. Confidence: {item['confidence']}."
        )
        for item in record["derived_rules"]
    )
    sources = f"Primary source: {identity['canonical_url']}"
    if supporting_source := identity.get("supporting_url"):
        sources = f"{sources}\nSupporting source: {supporting_source}"
    related_size_guides = "\n".join(f"- {item}" for item in record.get("related_size_guides", []))
    size_chart = _size_chart_document(record.get("size_chart", []))
    return "\n".join(
        part
        for part in [
            f"Mizaaj Atlas record: {record['id']}",
            f"Kind: {record['kind']}",
            f"Brand: {identity['brand']}",
            f"Retailer: {identity['retailer']}",
            f"Title: {identity['title']}",
            f"Category: {identity['category']}",
            f"Gender: {identity['gender']}",
            f"Style number: {identity['style_number'] or 'none'}",
            f"Color: {identity['color'] or 'none'}",
            f"Region: {identity['region']}",
            sources,
            "Source facts:",
            facts,
            "Related size guides:" if related_size_guides else "",
            related_size_guides,
            "Structured size chart:" if size_chart else "",
            size_chart,
            "Non-personal derived rules:",
            rules,
            (
                "Policy: This is public product evidence, not private user experience. "
                "Private Mizaaj memory overrides Atlas when they conflict."
            ),
        ]
        if part
    )


def _size_chart_document(size_chart: list[dict[str, Any]]) -> str:
    sections = []
    for chart in size_chart:
        columns = chart.get("columns", [])
        rows = chart.get("rows", [])
        row_text = "\n".join(
            "- "
            + "; ".join(f"{column}: {row.get(column, '')}" for column in columns if row.get(column))
            for row in rows
        )
        sections.append(
            "\n".join(
                part
                for part in [
                    f"Chart scope: {chart.get('scope', 'unspecified')}",
                    f"Measurement type: {chart.get('measurement_type', 'unspecified')}",
                    f"Unit: {chart.get('unit', 'unspecified')}",
                    f"Columns: {', '.join(columns)}" if columns else "",
                    row_text,
                ]
                if part
            )
        )
    return "\n\n".join(sections)


async def seed_atlas(
    seed_file: Path,
    dataset_name: str,
    spend_credits: bool,
    forget_first: bool,
) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.cognee_cloud_base_url or not settings.cognee_cloud_api_key:
        raise RuntimeError("COGNEE_CLOUD_BASE_URL and COGNEE_CLOUD_API_KEY are required.")

    payload = json.loads(seed_file.read_text(encoding="utf-8"))
    records = payload["records"]
    print(f"Atlas dataset: {dataset_name}")
    print(f"Records: {len(records)}")

    if not spend_credits:
        for record in records:
            identity = record["identity"]
            print(f"DRY RUN {record['id']}: {identity['brand']} - {identity['title']}")
        print("Pass --spend-credits to index these records into Cognee Cloud.")
        return

    async with httpx.AsyncClient(
        base_url=str(settings.cognee_cloud_base_url).rstrip("/"),
        headers={"X-Api-Key": settings.cognee_cloud_api_key},
        timeout=settings.cognee_timeout_seconds,
    ) as client:
        if forget_first:
            response = await client.post(
                "/api/v1/forget",
                json={"dataset": dataset_name, "everything": False, "memoryOnly": True},
            )
            response.raise_for_status()

        for record in records:
            body, content_type = _multipart_body(dataset_name, record)
            response = await client.post(
                "/api/v1/remember",
                content=body,
                headers={"Content-Type": content_type},
            )
            response.raise_for_status()
            print(f"Indexed {record['id']}")


def _multipart_body(dataset_name: str, record: dict[str, Any]) -> tuple[bytes, str]:
    boundary = f"mizaaj-atlas-{uuid4().hex}"
    chunks: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )

    def add_file(name: str, file_name: str, value: str) -> None:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; filename="{file_name}"\r\n'
                ).encode(),
                b"Content-Type: text/plain\r\n\r\n",
                value.encode(),
                b"\r\n",
            ]
        )

    add_field("datasetName", dataset_name)
    add_field("run_in_background", "false")
    add_field("custom_prompt", _atlas_prompt())
    for tag in record["tags"]:
        add_field("node_set", tag)
    add_field("node_set", "scope:public-atlas")
    add_file("data", f"{record['id']}.txt", build_atlas_document(record))
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _atlas_prompt() -> str:
    return (
        "Extract public clothing fit intelligence for Mizaaj Atlas. Preserve brand, category, "
        "fit label, material, size-guide signals, source URLs, and risk notes. Mark these facts "
        "as public Atlas evidence, not private user experience."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-file", type=Path, default=DEFAULT_SEED_FILE)
    parser.add_argument("--dataset", default="mizaaj_atlas_seed_v2")
    parser.add_argument("--spend-credits", action="store_true")
    parser.add_argument("--forget-first", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    asyncio.run(seed_atlas(args.seed_file, args.dataset, args.spend_credits, args.forget_first))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
