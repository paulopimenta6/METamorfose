#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valida o reprocessamento da Fase 1 contra leitura independente via pygrib.

Confere, produto a produto:
- nomes, headers e contagem de linhas em relação ao baseline;
- coordenadas e orientação sul-primeiro;
- valores das matrizes contra a amostra GRIB lida diretamente pelo pygrib;
- D-01 (orientação), D-02 (U/V), D-03 (altitudes) e D-12 (ângulo);
- seleção do ciclo 00 do mesmo dia (D-04) nos logs do reprocessamento.

Escreve `reprocessamento/reports/20261022-00/validation.json` e retorna
código 1 se qualquer verificação falhar.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pygrib

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "baseline" / "samples" / "gfs.20261022.00.0p25.subset.grb2"
BASELINE = ROOT / "baseline" / "reports" / "20261022-00"
REPROC = ROOT / "reprocessamento" / "reports" / "20261022-00"
LOG_DIR = ROOT / "reprocessamento" / "run" / "logs"
OUT = REPROC / "validation.json"

LAT1, LAT2 = -28.0, -18.0
LON1_360, LON2_360 = 304.0, 318.0

HEIGHTS = (20, 30, 40, 50, 80)
PRESSURE_LEVELS = (850,)


class Checks:
    def __init__(self):
        self.items = []
        self.failures = 0

    def check(self, name: str, condition: bool, detail=None):
        status = "ok" if condition else "falha"
        if not condition:
            self.failures += 1
        self.items.append({"name": name, "status": status, "detail": detail})
        print(f"[{'OK' if condition else 'FALHA'}] {name}")
        return condition

    def report(self):
        return {
            "status": "ok" if self.failures == 0 else "falha",
            "checks": len(self.items),
            "failures": self.failures,
            "items": self.items,
        }


def load_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    header = rows[0]
    data = np.array([[float(value) for value in row] for row in rows[1:]])
    return header, data


def independent(grb):
    """Extrai a região SP já na mesma orientação do CSV (sul primeiro)."""
    values, lats, lons = grb.data(
        lat1=LAT1, lat2=LAT2, lon1=LON1_360, lon2=LON2_360
    )
    values = np.asarray(values, dtype=float)[::-1, :]
    lats = np.asarray(lats, dtype=float)[:, 0][::-1]
    lons = np.asarray(lons, dtype=float)[0, :] - 360.0
    return values, lats, lons


def select(grib, name, type_of_level, level=None):
    if level is None:
        return grib.select(name=name, typeOfLevel=type_of_level)[0]
    return grib.select(name=name, typeOfLevel=type_of_level, level=level)[0]


def altitude_ft(level: int) -> float:
    if level in HEIGHTS:
        return level * 3.28084
    return (1 - (level / 1013.25) ** 0.190284) * 145366.45


def angle(u, v):
    return ((180 / np.pi) * np.arctan2(-u, -v) + 360) % 360


def compare_columns(checks, label, data, indices):
    for index, name, values in indices:
        ok = np.allclose(data[:, index], np.asarray(values).ravel(), rtol=1e-12, atol=1e-9)
        checks.check(f"{label}: coluna {name}", ok)


def compare_grid(checks, label, data, lats, lons):
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    checks.check(
        f"{label}: lat alinhada e crescente",
        np.allclose(data[:, 0], lat_grid.ravel(), atol=1e-12),
        {"lat_min": float(data[:, 0].min()), "lat_max": float(data[:, 0].max())},
    )
    checks.check(
        f"{label}: lon alinhada",
        np.allclose(data[:, 1], lon_grid.ravel(), atol=1e-12),
        {"lon_min": float(data[:, 1].min()), "lon_max": float(data[:, 1].max())},
    )


def compare_inventory(checks, baseline, reproc):
    base_files = sorted(path.relative_to(baseline).as_posix() for path in baseline.rglob("*") if path.is_file() and path.name not in {"summary.json", "pytest.txt", "validation.json"})
    rep_files = sorted(path.relative_to(reproc).as_posix() for path in reproc.rglob("*") if path.is_file() and path.name not in {"summary.json", "pytest.txt", "validation.json"})
    checks.check("inventário: mesmos caminhos do baseline", base_files == rep_files, {"baseline": len(base_files), "reprocessamento": len(rep_files)})
    checks.check("inventário: 13 CSVs", len([p for p in rep_files if p.endswith(".csv")]) == 13)
    checks.check("inventário: 7 PNGs", len([p for p in rep_files if p.endswith(".png")]) == 7)
    for name in rep_files:
        if name.endswith(".png"):
            checks.check(f"mapa não vazio: {name}", (reproc / name).stat().st_size > 0)


def compare_baseline_metadata(checks, base_summary, rep_summary):
    checks.check(
        "baseline/reprocessamento: mesmos nomes de produto",
        sorted(base_summary["csv"]) == sorted(rep_summary["csv"]),
    )
    for name in sorted(rep_summary["csv"]):
        base = base_summary["csv"][name]
        rep = rep_summary["csv"][name]
        checks.check(
            f"{name}: header preservado",
            base["header"] == rep["header"],
            rep["header"],
        )
        checks.check(
            f"{name}: {rep['rows']} linhas (igual ao baseline)",
            base["rows"] == rep["rows"] == 2337,
        )
        checks.check(
            f"{name}: lat de -28 a -18",
            (rep["lat_first"], rep["lat_last"]) == (-28.0, -18.0),
            [rep["lat_first"], rep["lat_last"]],
        )


def validate_products(checks, grib):
    tmp850 = select(grib, "Temperature", "isobaricInhPa", 850)
    surface = select(grib, "Temperature", "surface")
    temperatures = {850: tmp850, "surface": surface}
    winds = {}
    for level in (*HEIGHTS, *PRESSURE_LEVELS):
        if level in HEIGHTS:
            winds[level] = (
                select(grib, "U component of wind", "heightAboveGround", level),
                select(grib, "V component of wind", "heightAboveGround", level),
            )
        else:
            winds[level] = (
                select(grib, "U component of wind", "isobaricInhPa", level),
                select(grib, "V component of wind", "isobaricInhPa", level),
            )

    temp_values, lats, lons = independent(tmp850)
    surface_values, _, _ = independent(surface)
    wind_values = {}
    for level, (u_grb, v_grb) in winds.items():
        wind_values[level] = (independent(u_grb)[0], independent(v_grb)[0])

    # Matriz escalar de temperatura em 850 hPa.
    path = REPROC / "matrizes" / "GFS_0.25_SP_N850_temp_00_20261022_00.csv"
    header, data = load_csv(path)
    checks.check("matriz temp 850: header", header == ["lat", "lon", "temp"], header)
    compare_grid(checks, "matriz temp 850", data, lats, lons)
    compare_columns(
        checks,
        "matriz temp 850",
        data,
        [(2, "temp", temp_values - 273.15)],
    )

    # Matrizes BlueSky.
    for level in (*HEIGHTS, *PRESSURE_LEVELS):
        path = REPROC / "bluesky" / f"GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N{level}_00_20261022_00.csv"
        header, data = load_csv(path)
        u, v = wind_values[level]
        resultant = np.sqrt(u**2 + v**2) * 1.943
        expected = [
            (2, "hMET", np.full_like(u, altitude_ft(level))),
            (3, "angMET", angle(u, v)),
            (4, "vento_resultante", resultant),
        ]
        checks.check(f"bluesky N{level}: header", header == ["lat", "lon", "hMET", "angMET", "vento_resultante"], header)
        compare_grid(checks, f"bluesky N{level}", data, lats, lons)
        compare_columns(checks, f"bluesky N{level}", data, expected)
        checks.check(
            f"bluesky N{level}: ângulo em [0, 360)",
            bool(np.all(data[:, 3] >= 0.0) and np.all(data[:, 3] < 360.0)),
            [float(data[:, 3].min()), float(data[:, 3].max())],
        )

    # Matrizes do preditor. Em níveis de pressão a temperatura acompanha o
    # nível; nos níveis de altura quase-superficiais ela é a de superfície.
    for level in (*HEIGHTS, *PRESSURE_LEVELS):
        path = REPROC / "predi" / f"GFS_0.25_matriz_lat_lon_Vento_UVT_Predi_SP_N{level}_00_20261022_00.csv"
        header, data = load_csv(path)
        u, v = wind_values[level]
        expected_temp = temp_values if level in PRESSURE_LEVELS else surface_values
        checks.check(f"predi N{level}: header", header == ["lat", "lon", "vento U", "vento V", "temp"], header)
        compare_grid(checks, f"predi N{level}", data, lats, lons)
        compare_columns(
            checks,
            f"predi N{level}",
            data,
            [
                (2, "vento U", u),
                (3, "vento V", v),
                (4, "temp", expected_temp),
            ],
        )
        checks.check(
            f"predi N{level}: U e V independentes",
            not np.allclose(data[:, 2], data[:, 3]),
        )

    # Evidências D-01/D-02/D-03/D-12, comparando com o baseline.
    baseline_scalar = load_csv(BASELINE / "matrizes" / "GFS_0.25_SP_N850_temp_00_20261022_00.csv")[1]
    reproc_scalar = load_csv(REPROC / "matrizes" / "GFS_0.25_SP_N850_temp_00_20261022_00.csv")[1]
    checks.check(
        "D-01: baseline começa com o valor do norte",
        abs(baseline_scalar[0, 2] - (temp_values[-1, 0] - 273.15)) < 1e-9,
        baseline_scalar[0, 2],
    )
    checks.check(
        "D-01: reprocessamento começa com o valor do sul",
        abs(reproc_scalar[0, 2] - (temp_values[0, 0] - 273.15)) < 1e-9,
        reproc_scalar[0, 2],
    )

    baseline_predi = load_csv(BASELINE / "predi" / "GFS_0.25_matriz_lat_lon_Vento_UVT_Predi_SP_N20_00_20261022_00.csv")[1]
    reproc_predi = load_csv(REPROC / "predi" / "GFS_0.25_matriz_lat_lon_Vento_UVT_Predi_SP_N20_00_20261022_00.csv")[1]
    checks.check(
        "D-02: baseline repete U em V em todas as linhas",
        np.allclose(baseline_predi[:, 2], baseline_predi[:, 3]),
    )
    checks.check(
        "D-02: reprocessamento separa U e V",
        not np.allclose(reproc_predi[:, 2], reproc_predi[:, 3]),
    )
    u20, v20 = wind_values[20]
    checks.check(
        "D-02: reprocessamento usa o V real",
        abs(reproc_predi[0, 3] - v20[0, 0]) < 1e-9,
        reproc_predi[0, 3],
    )

    baseline_20 = load_csv(BASELINE / "bluesky" / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N20_00_20261022_00.csv")[1]
    reproc_20 = load_csv(REPROC / "bluesky" / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N20_00_20261022_00.csv")[1]
    baseline_80 = load_csv(BASELINE / "bluesky" / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N80_00_20261022_00.csv")[1]
    reproc_80 = load_csv(REPROC / "bluesky" / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N80_00_20261022_00.csv")[1]
    checks.check(
        "D-03: baseline trata 20 m como pressão",
        abs(baseline_20[0, 2] - 76487.0117634869) < 1e-6,
        baseline_20[0, 2],
    )
    checks.check("D-03: reprocessamento usa 20 m × 3.28084", abs(reproc_20[0, 2] - 65.6168) < 1e-9, reproc_20[0, 2])
    checks.check(
        "D-03: baseline trata 80 m como pressão",
        abs(baseline_80[0, 2] - 55695.456840965366) < 1e-6,
        baseline_80[0, 2],
    )
    checks.check("D-03: reprocessamento usa 80 m × 3.28084", abs(reproc_80[0, 2] - 262.4672) < 1e-9, reproc_80[0, 2])
    reproc_850 = load_csv(REPROC / "bluesky" / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N850_00_20261022_00.csv")[1]
    checks.check(
        "D-03: 850 hPa mantém a fórmula barométrica",
        abs(reproc_850[0, 2] - 4779.1936018229135) < 1e-9,
        reproc_850[0, 2],
    )

    checks.check(
        "D-12: baseline tem ângulos negativos",
        float(baseline_20[:, 3].min()) < 0.0,
        float(baseline_20[:, 3].min()),
    )
    checks.check(
        "D-12: reprocessamento tem ângulos em [0, 360)",
        bool(reproc_20[:, 3].min() >= 0.0 and reproc_20[:, 3].max() < 360.0),
        [float(reproc_20[:, 3].min()), float(reproc_20[:, 3].max())],
    )
    checks.check(
        "D-12: ângulo do primeiro ponto confere com arctan2",
        abs(reproc_20[0, 3] - float(angle(u20, v20)[0, 0])) < 1e-9,
        reproc_20[0, 3],
    )


def validate_cycle_logs(checks):
    logs = sorted(LOG_DIR.glob("*.log"))
    checks.check("D-04: seis logs de execução", len(logs) == 6, [path.name for path in logs])
    for path in logs:
        text = path.read_text(encoding="utf-8", errors="replace")
        checks.check(
            f"D-04: {path.name} seleciona o ciclo 00 do mesmo dia",
            "ciclo GFS selecionado para a hora local 1: 00" in text,
        )


def main():
    if not REPROC.exists():
        raise SystemExit(f"reprocessamento ausente: {REPROC}")
    base_summary = json.loads((BASELINE / "summary.json").read_text(encoding="utf-8"))
    rep_summary = json.loads((REPROC / "summary.json").read_text(encoding="utf-8"))

    checks = Checks()
    compare_inventory(checks, BASELINE, REPROC)
    compare_baseline_metadata(checks, base_summary, rep_summary)

    with pygrib.open(str(SAMPLE)) as grib:
        validate_products(checks, grib)
    validate_cycle_logs(checks)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Validação independente do reprocessamento da Fase 1.",
        "sample": {
            "path": str(SAMPLE.relative_to(ROOT)),
            "sha256": json.loads(Path(str(SAMPLE) + ".json").read_text(encoding="utf-8"))["file"]["sha256"],
        },
        "region": {
            "lat": [LAT1, LAT2],
            "lon": [LON1_360 - 360.0, LON2_360 - 360.0],
        },
        "baseline": str(BASELINE.relative_to(ROOT)),
        "reprocessamento": str(REPROC.relative_to(ROOT)),
        **checks.report(),
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n[validacao] {report['checks']} verificações, {report['failures']} falhas")
    print(f"[validacao] relatório: {OUT}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
