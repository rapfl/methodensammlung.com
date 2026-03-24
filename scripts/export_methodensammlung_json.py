#!/usr/bin/env python3
"""
Export the normalized Methodensammlung SSOT workbook into deterministic JSON and
an ESM data module for the static product layer.

The repository does not ship spreadsheet dependencies, so this parser reads the
XLSX OOXML package directly with the Python standard library.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

ROOT = Path(__file__).resolve().parents[1]
SOURCE_WORKBOOK = ROOT / "Methodensammlung_SSOT_v2_1.xlsx"
OUTPUT_JSON = ROOT / "data" / "methodensammlung.json"
OUTPUT_MODULE = ROOT / "src" / "generated" / "methodensammlung-data.js"

SHEET_ALIASES = OrderedDict(
    [
        ("README", "readme"),
        ("RAW_Original_Import", "rawOriginalImport"),
        ("Methods", "methods"),
        ("Method_Tags", "methodTags"),
        ("Method_Variants", "methodVariants"),
        ("Finder_Intents", "finderIntents"),
        ("Collections", "collections"),
        ("Collection_Items", "collectionItems"),
        ("Vectors", "vectors"),
        ("Method_Vector_Map", "methodVectorMap"),
        ("Composer_Blocks_Reference", "composerBlocksReference"),
        ("UI_Field_Mapping", "uiFieldMapping"),
        ("Mockup_Constraints", "mockupConstraints"),
        ("Open_Questions", "openQuestions"),
    ]
)

NUMERIC_FIELDS = {
    "legacy_row_id",
    "duration_min",
    "duration_max",
    "age_min",
    "age_max",
    "group_size_min",
    "group_size_max",
    "recommended_duration",
    "sort_order",
    "confidence",
    "duration_filter_min",
    "duration_filter_max",
}

BOOLEAN_FIELDS = {
    "uncertainty_flag",
    "suitable_for_finder",
    "suitable_for_library",
    "suitable_for_composer",
    "suitable_for_active_session",
    "is_customizable",
}

ARRAY_FIELDS = {
    "recommended_method_ids_or_variant_ids",
}


def col_name_to_index(name: str) -> int:
    total = 0
    for char in name:
        total = total * 26 + ord(char.upper()) - 64
    return total


def parse_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root:
        text = "".join(node.text or "" for node in item.iterfind(".//a:t", NS))
        values.append(text)
    return values


def parse_sheet_rows(zf: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_path))
    sheet_data = root.find("a:sheetData", NS)
    rows: list[list[str]] = []
    if sheet_data is None:
        return rows
    for row in sheet_data.findall("a:row", NS):
        values: dict[int, str] = {}
        for cell in row.findall("a:c", NS):
            ref = cell.attrib["r"]
            col_name = "".join(ch for ch in ref if ch.isalpha())
            idx = col_name_to_index(col_name)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("a:v", NS)
            inline_node = cell.find("a:is", NS)
            value = ""
            if cell_type == "s" and value_node is not None and value_node.text is not None:
                value = shared_strings[int(value_node.text)]
            elif cell_type == "inlineStr" and inline_node is not None:
                value = "".join(node.text or "" for node in inline_node.iterfind(".//a:t", NS))
            elif value_node is not None and value_node.text is not None:
                value = value_node.text
            values[idx] = value
        max_col = max(values, default=0)
        rows.append([values.get(index, "") for index in range(1, max_col + 1)])
    return rows


def read_sheet_map(zf: ZipFile) -> dict[str, str]:
    workbook_root = ET.fromstring(zf.read("xl/workbook.xml"))
    rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}
    mapping: dict[str, str] = {}
    sheets = workbook_root.find("a:sheets", NS)
    if sheets is None:
        return mapping
    for sheet in sheets:
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        mapping[sheet.attrib["name"]] = f"xl/{rel_map[rel_id]}"
    return mapping


def parse_number(value: str) -> int | float | None:
    if value == "":
        return None
    if "." in value:
        return float(value)
    return int(value)


def parse_boolean(value: str) -> bool | None:
    if value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"ja", "yes", "true", "1", "aktiv"}:
        return True
    if normalized in {"nein", "no", "false", "0", "inaktiv"}:
        return False
    return None


def normalize_value(field: str, value: str) -> Any:
    if value == "":
        return None
    if field in ARRAY_FIELDS:
        return [item.strip() for item in value.split(",") if item.strip()]
    if field in NUMERIC_FIELDS:
        return parse_number(value)
    if field in BOOLEAN_FIELDS:
        parsed = parse_boolean(value)
        return parsed if parsed is not None else value
    return value


def build_record(headers: list[str], row: list[str]) -> dict[str, Any]:
    padded = (row + [""] * len(headers))[: len(headers)]
    record: dict[str, Any] = OrderedDict()
    for header, value in zip(headers, padded):
        record[header] = normalize_value(header, value)
    return record


def export_workbook(source: Path) -> dict[str, Any]:
    sheets: dict[str, list[dict[str, Any]]] = OrderedDict()
    with ZipFile(source) as zf:
        shared_strings = parse_shared_strings(zf)
        sheet_map = read_sheet_map(zf)
        for workbook_name, alias in SHEET_ALIASES.items():
            sheet_rows = parse_sheet_rows(zf, sheet_map[workbook_name], shared_strings)
            if not sheet_rows:
                sheets[alias] = []
                continue
            headers = sheet_rows[0]
            sheets[alias] = [build_record(headers, row) for row in sheet_rows[1:]]

    counts = OrderedDict((alias, len(records)) for alias, records in sheets.items())
    return OrderedDict(
        [
            (
                "meta",
                OrderedDict(
                    [
                        ("sourceWorkbook", source.name),
                        ("entityCounts", counts),
                    ]
                ),
            ),
            ("sheets", sheets),
        ]
    )


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MODULE.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    OUTPUT_JSON.write_text(json_text + "\n", encoding="utf-8")
    OUTPUT_MODULE.write_text(
        "export const METHODENSAMMLUNG_DATA = " + json_text + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    payload = export_workbook(SOURCE_WORKBOOK)
    write_outputs(payload)
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MODULE}")


if __name__ == "__main__":
    main()
