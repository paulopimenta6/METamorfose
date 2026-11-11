#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o baseline da Fase 0 com o código de produção e a amostra GFS real.

O código não é modificado: `classes_MET` é exposto por symlink na árvore de
execução e `environment/path.conf` aponta para diretórios temporários.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "baseline" / "samples" / "gfs.20261022.00.0p25.subset.grb2"
SAMPLE_SIDECAR = Path(str(SAMPLE) + ".json")
RUN = ROOT / "baseline" / "run"
REPORT = ROOT / "baseline" / "reports" / "20261022-00"
WRAPPER = ROOT / "baseline" / "run_with_time.py"
FIXED_TIME = "2026-10-22T01:00"

RUNS = [
    ("matriz_temp_850", "gera_matriz_MET.py", ["-v", "temp", "-n", "850", "-r", "SP"]),
    ("mapa_temp_850", "gera_mapas_MET.py", ["-v", "temp", "-n", "850", "-r", "SP"]),
    ("matriz_wind_850", "gera_matriz_vento_MET.py", ["-v", "wind", "-n", "850", "-r", "SP"]),
    ("mapa_wind_850", "gera_mapas_vento_MET.py", ["-v", "wind", "-n", "850", "-r", "SP"]),
    ("matriz_winds_20", "gera_matriz_vento_MET.py", ["-v", "winds", "-ns", "-r", "SP"]),
    ("mapa_winds_20", "gera_mapas_vento_MET.py", ["-v", "winds", "-ns", "-r", "SP"]),
]

COPY_DIRS = [
    ("mapas", RUN / "mapasGrib" / "20261022" / "00"),
    ("matrizes", RUN / "matrizGrib" / "20261022" / "00"),
    ("bluesky", RUN / "matrizGrib" / "bluesky" / "20261022" / "00"),
    ("predi", RUN / "matrizGrib" / "predi" / "20261022" / "00"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_version(name: str):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def prepare_tree():
    if not SAMPLE.exists():
        raise SystemExit(
            f"amostra ausente: {SAMPLE}\n"
            "Rode: python3 tests/fetch_gfs_sample.py"
        )
    if RUN.exists():
        shutil.rmtree(RUN)
    for path in (
        RUN / "environment",
        RUN / "gribs" / "20261022" / "00",
        RUN / "mapasGrib",
        RUN / "matrizGrib",
        RUN / "matrizGrib" / "predi",
        RUN / "matrizGrib" / "bluesky",
        RUN / "logs",
    ):
        path.mkdir(parents=True, exist_ok=True)

    (RUN / "classes_MET").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "classes_MET",
        RUN / "classes_MET",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(SAMPLE, RUN / "gribs" / "20261022" / "00" / "gfs.t00z.pgrb2.0p25.f000")
    # O leitor atual exige as quatro previsões e não tolera ausência. Para o
    # baseline f000, os nomes f006/f012/f018 recebem cópias da mesma amostra;
    # o forecastTime interno continua 0, então o produto final é o de f000.
    for forecast in ("006", "012", "018"):
        shutil.copy2(
            SAMPLE,
            RUN / "gribs" / "20261022" / "00" / f"gfs.t00z.pgrb2.0p25.f{forecast}",
        )
    (RUN / "gribs" / "20261022" / "00" / "LEIA-ME.txt").write_text(
        "Amostra f000 copiada para f006/f012/f018 apenas para satisfazer o loop\n"
        "do leitor atual. Todas as mensagens têm forecastTime=0; o baseline\n"
        "representa somente a previsão f000.\n",
        encoding="utf-8",
    )

    path_conf = "\n".join(
        [
            f"dir_gribs={RUN / 'gribs'}",
            f"dir_mapas={RUN / 'mapasGrib'}",
            f"dir_matrizes={RUN / 'matrizGrib'}",
            f"dir_matrizes_predi={RUN / 'matrizGrib' / 'predi'}",
            f"dir_matrizes_bluesky={RUN / 'matrizGrib' / 'bluesky'}",
            "",
        ]
    )
    (RUN / "environment" / "path.conf").write_text(path_conf, encoding="utf-8")


def run_one(label: str, script: str, args):
    log_path = RUN / "logs" / f"{label}.log"
    command = [sys.executable, str(WRAPPER), FIXED_TIME, script] + args
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    environment["PYTHONUNBUFFERED"] = "1"
    print(f"[baseline] {label}: {' '.join(command)}")
    result = subprocess.run(
        command,
        cwd=RUN / "classes_MET",
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
    )
    log_path.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-40:])
        raise SystemExit(
            f"comando falhou ({label}, código {result.returncode}). Últimas linhas:\n{tail}\n"
            f"log completo: {log_path}"
        )
    return {
        "label": label,
        "script": script,
        "args": args,
        "returncode": result.returncode,
        "log": str(log_path.relative_to(ROOT)),
    }


def copy_outputs():
    if REPORT.exists():
        shutil.rmtree(REPORT)
    REPORT.mkdir(parents=True, exist_ok=True)
    for destination, source in COPY_DIRS:
        target = REPORT / destination
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)
            print(f"[baseline] aviso: diretório ausente: {source}")


def csv_summary(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return {"header": [], "rows": 0}
    header = rows[0]
    data = rows[1:]
    summary = {
        "header": header,
        "rows": len(data),
    }
    if not data:
        return summary

    lats = [float(row[0]) for row in data]
    summary.update(
        {
            "lat_first": lats[0],
            "lat_last": lats[-1],
            "lat_min": min(lats),
            "lat_max": max(lats),
        }
    )

    numeric_columns = {
        "hMET",
        "angMET",
        "vento_resultante",
        "vento U",
        "vento V",
        "temp",
    }
    ranges = {}
    for index, column in enumerate(header):
        if column not in numeric_columns:
            continue
        values = [float(row[index]) for row in data]
        ranges[column] = {
            "min": min(values),
            "max": max(values),
        }
    if ranges:
        summary["ranges"] = ranges
    return summary


def build_summary(runs):
    files = []
    for path in sorted(REPORT.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": str(path.relative_to(REPORT)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

    csvs = {}
    for path in sorted(REPORT.rglob("*.csv")):
        csvs[str(path.relative_to(REPORT))] = csv_summary(path)

    sidecar = json.loads(SAMPLE_SIDECAR.read_text(encoding="utf-8"))
    freeze = json.loads((ROOT / "baseline" / "freeze.json").read_text(encoding="utf-8"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Baseline da Fase 0, gerado com o código de produção anterior às correções.",
        "fixed_local_time": FIXED_TIME,
        "note": (
            "Os produtos refletem os defeitos D-01/D-02/D-03/D-04/D-12. "
            "Não usar como referência operacional. As previsões f006/f012/f018 "
            "são cópias da amostra f000 para satisfazer o leitor atual; todas têm "
            "forecastTime=0 e o baseline representa apenas f000."
        ),
        "sample": {
            "path": str(SAMPLE.relative_to(ROOT)),
            "bytes": SAMPLE.stat().st_size,
            "sha256": sha256_file(SAMPLE),
            "source": sidecar["source"],
            "sidecar": str(SAMPLE_SIDECAR.relative_to(ROOT)),
            "sidecar_sha256": sha256_file(SAMPLE_SIDECAR),
            "reference_point": sidecar["reference_point"],
        },
        "frozen_acquisition": freeze["files"]["goGribV2.sh"],
        "environment": {
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "numpy": package_version("numpy"),
            "matplotlib": package_version("matplotlib"),
            "pygrib": package_version("pygrib"),
            "basemap": package_version("basemap"),
        },
        "runs": runs,
        "files": files,
        "csv": csvs,
    }


def main():
    prepare_tree()
    runs = []
    for label, script, args in RUNS:
        runs.append(run_one(label, script, args))
    copy_outputs()
    summary = build_summary(runs)
    summary_path = REPORT / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[baseline] resumo: {summary_path}")
    print(f"[baseline] arquivos copiados: {len(summary['files'])}")
    print(f"[baseline] CSVs: {len(summary['csv'])}")


if __name__ == "__main__":
    main()
