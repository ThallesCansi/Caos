from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd
import requests


def _local_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _get_xml(url: str, params: dict[str, Any], timeout: int = 90) -> ET.Element:
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    if _local_name(root.tag) == "ExceptionReport":
        messages = [
            (el.text or "").strip()
            for el in root.iter()
            if _local_name(el.tag) == "ExceptionText"
        ]
        raise RuntimeError("WFS Exception: " + " | ".join(messages))
    return root


def discover_feature_types(wfs_url: str) -> pd.DataFrame:
    root = _get_xml(
        wfs_url,
        {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"},
    )
    rows: list[dict[str, str | None]] = []
    for feature_type in root.iter():
        if _local_name(feature_type.tag) != "FeatureType":
            continue
        name = title = None
        for child in feature_type:
            if _local_name(child.tag) == "Name":
                name = (child.text or "").strip()
            elif _local_name(child.tag) == "Title":
                title = (child.text or "").strip()
        if name:
            rows.append({"name": name, "title": title})
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def choose_layer(feature_types: pd.DataFrame, preferred_local_name: str) -> str:
    names = feature_types["name"].tolist()
    exact = [name for name in names if name.split(":")[-1].lower() == preferred_local_name.lower()]
    if len(exact) != 1:
        raise RuntimeError(
            f"Expected one WFS layer with local name {preferred_local_name!r}; found {exact}. "
            f"Available: {names}"
        )
    return exact[0]


def describe_fields(wfs_url: str, layer: str) -> pd.DataFrame:
    root = _get_xml(
        wfs_url,
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "DescribeFeatureType",
            "typeNames": layer,
        },
    )
    fields = []
    for el in root.iter():
        if _local_name(el.tag) == "element" and el.attrib.get("name"):
            fields.append({"name": el.attrib["name"], "type": el.attrib.get("type")})
    return pd.DataFrame(fields).drop_duplicates().reset_index(drop=True)


def choose_date_field(fields: pd.DataFrame, candidates: list[str]) -> str:
    names = fields["name"].tolist()
    lookup = {name.lower(): name for name in names}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    date_like = [name for name in names if "date" in name.lower()]
    if len(date_like) == 1:
        return date_like[0]
    raise RuntimeError(f"Could not identify date field safely. Candidates found: {date_like}")


def count_features(wfs_url: str, layer: str, cql_filter: str) -> int:
    root = _get_xml(
        wfs_url,
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer,
            "resultType": "hits",
            "CQL_FILTER": cql_filter,
        },
    )
    for key in ["numberMatched", "numberOfFeatures"]:
        value = root.attrib.get(key)
        if value and value != "unknown":
            return int(value)
    raise RuntimeError(f"WFS did not report feature count: {root.attrib}")


def download_geojson(
    wfs_url: str,
    layer: str,
    cql_filter: str,
    destination: str | Path,
    count: int = 100_000,
) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return destination

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer,
        "CQL_FILTER": cql_filter,
        "outputFormat": "application/json",
        "count": count,
        "startIndex": 0,
        "srsName": "EPSG:4674",
    }
    response = requests.get(wfs_url, params=params, timeout=180)
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        text = response.text[:1000]
        raise RuntimeError(f"TerraBrasilis did not return JSON. First bytes: {text}") from exc
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"Unexpected WFS JSON payload: {json.dumps(payload)[:1000]}")
    destination.write_text(json.dumps(payload), encoding="utf-8")
    return destination


def download_deter_pilot(config: dict[str, Any], destination: str | Path) -> Path:
    tb = config["terrabrasilis"]
    feature_types = discover_feature_types(tb["wfs_url"])
    layer = choose_layer(feature_types, tb["preferred_layer_local_name"])
    fields = describe_fields(tb["wfs_url"], layer)
    date_field = choose_date_field(fields, tb["date_field_candidates"])
    start = config["time"]["science_start"]
    end = config["time"]["science_end"]
    cql = f"{date_field} BETWEEN '{start}' AND '{end}'"
    n = count_features(tb["wfs_url"], layer, cql)
    limit = int(tb.get("max_features_without_pagination", 100_000))
    if n > limit:
        raise RuntimeError(
            f"DETER query matches {n} features, above non-paginated limit {limit}. "
            "Implement controlled pagination before scaling."
        )
    return download_geojson(tb["wfs_url"], layer, cql, destination, count=limit)
