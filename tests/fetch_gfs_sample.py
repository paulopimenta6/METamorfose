#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baixa uma amostra mínima e reproduzível do GFS 0.25° via .idx + HTTP Range.

A amostra não substitui o `goGribV2.sh` e não altera a aquisição operacional.
Ela serve apenas para o harness da Fase 0 e para validar pygrib/contratos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "baseline" / "samples" / "gfs.20261022.00.0p25.subset.grb2"
BASE = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"

# Mensagens necessárias para os produtos de referência:
# temp 850, wind 850, winds 20/30/40/50/80, superfície e pressão.
SELECTORS = [
    ("PRMSL", "mean sea level"),
    ("TMP", "850 mb"),
    ("RH", "850 mb"),
    ("TCDC", "850 mb"),
    ("UGRD", "850 mb"),
    ("VGRD", "850 mb"),
    ("TMP", "surface"),
    ("TMP", "2 m above ground"),
    ("UGRD", "10 m above ground"),
    ("VGRD", "10 m above ground"),
    ("UGRD", "20 m above ground"),
    ("VGRD", "20 m above ground"),
    ("UGRD", "30 m above ground"),
    ("VGRD", "30 m above ground"),
    ("UGRD", "40 m above ground"),
    ("VGRD", "40 m above ground"),
    ("UGRD", "50 m above ground"),
    ("VGRD", "50 m above ground"),
    ("UGRD", "80 m above ground"),
    ("VGRD", "80 m above ground"),
]

REFERENCE_POINT = {
    "lat": -23.55,
    "lon_0_360": 313.37,
    "lon_180": -46.63,
}

REFERENCE_SELECTORS = {
    "Temperature_850": ("Temperature", "isobaricInhPa", 850),
    "U_850": ("U component of wind", "isobaricInhPa", 850),
    "V_850": ("V component of wind", "isobaricInhPa", 850),
    "Temperature_surface": ("Temperature", "surface", 0),
    "U_20m": ("U component of wind", "heightAboveGround", 20),
    "V_20m": ("V component of wind", "heightAboveGround", 20),
    "Pressure_MSL": ("Pressure reduced to MSL", "meanSea", 0),
}

IDX_LINE = re.compile(
    r"^(?P<index>\d+):(?P<start>\d+):d=(?P<date>\d+):"
    r"(?P<name>[^:]+):(?P<level>[^:]+):(?P<forecast>[^:]+):?$"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def http_get(url: str, headers=None, timeout=120):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, dict(response.headers), response.read()


def get_size(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(response.headers["Content-Length"])


def fetch_range(url: str, start: int, end: int) -> bytes:
    status, headers, data = http_get(
        url,
        {
            "Range": f"bytes={start}-{end}",
            "User-Agent": "servidor_MET-phase0/1.0",
        },
    )
    if status != 206:
        raise RuntimeError(f"o servidor não respondeu 206 para Range: status={status}")
    expected = end - start + 1
    if len(data) != expected:
        raise RuntimeError(f"Range retornou {len(data)} bytes; esperado {expected}")
    content_range = headers.get("Content-Range", "")
    if content_range and not content_range.startswith(f"bytes {start}-{end}/"):
        raise RuntimeError(f"Content-Range inesperado: {content_range}")
    return data


def parse_index(text: str):
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = IDX_LINE.match(line)
        if not match:
            raise RuntimeError(f"linha .idx não reconhecida: {line!r}")
        item = match.groupdict()
        item["index"] = int(item["index"])
        item["start"] = int(item["start"])
        entries.append(item)
    if not entries:
        raise RuntimeError("índice .idx vazio")
    return entries


def select_entries(entries, selectors):
    selected = []
    for name, level in selectors:
        matches = [entry for entry in entries if entry["name"] == name and entry["level"] == level]
        if len(matches) != 1:
            raise RuntimeError(
                f"esperava 1 mensagem para {name!r}/{level!r}, encontrei {len(matches)}"
            )
        selected.append(matches[0])
    return selected


def mean_at_point(grbs, selectors, lat: float, lon: float):
    values = {}
    for label, (name, type_of_level, level) in selectors.items():
        message = grbs.select(name=name, typeOfLevel=type_of_level, level=level)[0]
        candidates = (
            (lon - 0.5, lon + 0.5),
            (lon - 360.0 - 0.5, lon - 360.0 + 0.5),
        )
        last_error = None
        for lon1, lon2 in candidates:
            try:
                data, _, _ = message.data(
                    lat1=lat - 0.5,
                    lat2=lat + 0.5,
                    lon1=lon1,
                    lon2=lon2,
                )
            except ValueError as error:
                last_error = error
                continue
            values[label] = float(np.nanmean(data))
            break
        else:
            raise RuntimeError(f"não foi possível amostrar {label}: {last_error}")
    return values


def validate_sample(path: Path):
    import pygrib

    grbs = pygrib.open(str(path))
    try:
        messages = [
            {
                "name": message.name,
                "typeOfLevel": message.typeOfLevel,
                "level": message.level,
                "dataDate": message.dataDate,
                "forecastTime": message.forecastTime,
            }
            for message in grbs
        ]
        grbs.seek(0)
        reference = mean_at_point(
            grbs,
            REFERENCE_SELECTORS,
            REFERENCE_POINT["lat"],
            REFERENCE_POINT["lon_0_360"],
        )
    finally:
        grbs.close()
    return messages, reference


def build_urls(date: str, cycle: str, resolution: str, forecast_hour: str):
    grib_name = f"gfs.t{cycle}z.pgrb2.{resolution}.f{forecast_hour}"
    base = f"{BASE}/gfs.{date}/{cycle}/atmos/{grib_name}"
    return base, base + ".idx"


def fetch_sample(date: str, cycle: str, resolution: str, forecast_hour: str, output: Path, force: bool):
    grib_url, index_url = build_urls(date, cycle, resolution, forecast_hour)
    print(f"índice: {index_url}")
    status, _, index_bytes = http_get(index_url, {"User-Agent": "servidor_MET-phase0/1.0"})
    if status != 200:
        raise RuntimeError(f"falha ao baixar .idx: status={status}")
    entries = parse_index(index_bytes.decode("utf-8"))
    selected = select_entries(entries, SELECTORS)

    full_size = get_size(grib_url)
    print(f"GRIB completo: {full_size:,} bytes; mensagens selecionadas: {len(selected)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    ranges = []
    if output.exists() and not force:
        print(f"amostra já existe: {output} (use --force para rebaixar)")
    else:
        chunks = []
        ranges = []
        for position, entry in enumerate(selected):
            next_start = next(
                (candidate["start"] for candidate in entries if candidate["start"] > entry["start"]),
                full_size,
            )
            end = next_start - 1
            print(
                f"[{position + 1:02d}/{len(selected)}] "
                f"{entry['name']}:{entry['level']} bytes={entry['start']}-{end}"
            )
            chunk = fetch_range(grib_url, entry["start"], end)
            chunks.append(chunk)
            ranges.append(
                {
                    "idx_index": entry["index"],
                    "name": entry["name"],
                    "level": entry["level"],
                    "forecast": entry["forecast"],
                    "start": entry["start"],
                    "end": end,
                    "bytes": len(chunk),
                    "sha256": sha256_bytes(chunk),
                }
            )
        output.write_bytes(b"".join(chunks))
        print(f"gravado: {output} ({output.stat().st_size:,} bytes)")

    messages, reference = validate_sample(output)
    print(f"pygrib leu {len(messages)} mensagens")
    print("ponto de referência:", reference)

    if not ranges:
        # Reconstrói o manifesto de ranges a partir do .idx, sem rebaixar o binário.
        for entry in selected:
            next_start = next(
                (candidate["start"] for candidate in entries if candidate["start"] > entry["start"]),
                full_size,
            )
            end = next_start - 1
            ranges.append(
                {
                    "idx_index": entry["index"],
                    "name": entry["name"],
                    "level": entry["level"],
                    "forecast": entry["forecast"],
                    "start": entry["start"],
                    "end": end,
                    "bytes": end - entry["start"] + 1,
                    "sha256": None,
                }
            )

    sidecar = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "url": grib_url,
            "index_url": index_url,
            "date": date,
            "cycle": cycle,
            "resolution": resolution,
            "forecast_hour": forecast_hour,
            "full_bytes": full_size,
        },
        "file": {
            "path": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output),
            "bytes": output.stat().st_size,
            "sha256": sha256_file(output),
        },
        "selection": ranges,
        "validation": {
            "message_count": len(messages),
            "messages": messages,
        },
        "reference_point": {
            "lat": REFERENCE_POINT["lat"],
            "lon_0_360": REFERENCE_POINT["lon_0_360"],
            "lon_180": REFERENCE_POINT["lon_180"],
            "values": reference,
        },
        "note": (
            "Amostra parcial montada com mensagens GRIB2 completas via .idx + HTTP Range. "
            "Não é um arquivo operacional do goGribV2.sh."
        ),
    }
    sidecar_path = Path(str(output) + ".json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"manifesto: {sidecar_path}")
    return sidecar


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="20261022", help="AAAAMMDD (UTC)")
    parser.add_argument("--cycle", default="00", choices=["00", "06", "12", "18"])
    parser.add_argument("--resolution", default="0p25", choices=["0p25", "1p00"])
    parser.add_argument("--forecast-hour", default="000", help="000, 006, 012 ou 018")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="rebaixa mesmo se o arquivo existir")
    args = parser.parse_args(argv)

    try:
        fetch_sample(
            args.date,
            args.cycle,
            args.resolution,
            args.forecast_hour,
            args.output,
            args.force,
        )
    except (urllib.error.URLError, RuntimeError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
