#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reprocessa a amostra da Fase 0 com o código corrigido da Fase 1.

Espelha `baseline/run_baseline.py`, mas escreve em `reprocessamento/run/` e
`reprocessamento/reports/20261022-00/`. O baseline nunca é sobrescrito.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
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
RUN = ROOT / "reprocessamento" / "run"
REPORT = ROOT / "reprocessamento" / "reports" / "20261022-00"
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


def acquire_lock():
    """Impede dois reprocessamentos simultâneos no mesmo worktree."""
    lock_path = ROOT / "reprocessamento" / ".run.lock"
    handle = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise SystemExit(
            f"outro reprocessamento já está em execução; lock: {lock_path}"
        )
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def prepare_tree(resume: bool = False):
    if not SAMPLE.exists():
        raise SystemExit(
            f"amostra ausente: {SAMPLE}\n"
            "Rode: python3 tests/fetch_gfs_sample.py"
        )
    if RUN.exists() and not resume:
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

    shutil.copytree(
        ROOT / "classes_MET",
        RUN / "classes_MET",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(SAMPLE, RUN / "gribs" / "20261022" / "00" / "gfs.t00z.pgrb2.0p25.f000")
    # O leitor exige as quatro previsões; as cópias mantêm forecastTime=0,
    # então o reprocessamento representa somente f000, como no baseline.
    for forecast in ("006", "012", "018"):
        shutil.copy2(
            SAMPLE,
            RUN / "gribs" / "20261022" / "00" / f"gfs.t00z.pgrb2.0p25.f{forecast}",
        )
    (RUN / "gribs" / "20261022" / "00" / "LEIA-ME.txt").write_text(
        "Amostra f000 copiada para f006/f012/f018 apenas para satisfazer o loop\n"
        "do leitor. Todas as mensagens têm forecastTime=0; o reprocessamento\n"
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


def run_one(label: str, script: str, args, resume: bool = False):
    log_path = RUN / "logs" / f"{label}.log"
    if resume and log_path.exists() and log_path.stat().st_size > 0:
        print(f"[reprocessamento] {label}: log já existe, pulando")
        return {
            "label": label,
            "script": script,
            "args": args,
            "returncode": 0,
            "log": str(log_path.relative_to(ROOT)),
            "resumed": True,
        }
    command = [sys.executable, str(WRAPPER), FIXED_TIME, script] + args
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    environment["PYTHONUNBUFFERED"] = "1"
    print(f"[reprocessamento] {label}: {' '.join(command)}")
    result = subprocess.run(
        command,
        cwd=RUN / "classes_MET",
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
    )
    if result.returncode != 0:
        failed = log_path.with_suffix(".failed.log")
        failed.write_text(result.stdout, encoding="utf-8")
        tail = "\n".join(result.stdout.splitlines()[-40:])
        raise SystemExit(
            f"comando falhou ({label}, código {result.returncode}). Últimas linhas:\n{tail}\n"
            f"log completo: {failed}"
        )
    log_path.write_text(result.stdout, encoding="utf-8")
    return {
        "label": label,
        "script": script,
        "args": args,
        "returncode": result.returncode,
        "log": str(log_path.relative_to(ROOT)),
    }


def copy_outputs(resume: bool = False):
    if REPORT.exists() and not resume:
        shutil.rmtree(REPORT)
    REPORT.mkdir(parents=True, exist_ok=True)
    for destination, source in COPY_DIRS:
        target = REPORT / destination
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)
            print(f"[reprocessamento] aviso: diretório ausente: {source}")


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
        "purpose": "Reprocessamento da Fase 1 com D-01/D-02/D-03/D-04/D-12 corrigidos.",
        "fixed_local_time": FIXED_TIME,
        "note": (
            "Produtos gerados com o código corrigido da Fase 1, a partir da mesma "
            "amostra f000 do baseline. As previsões f006/f012/f018 são cópias da "
            "amostra f000; todas têm forecastTime=0."
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Reprocessa a amostra da Fase 0 com as correções da Fase 1."
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="preserva reprocessamento/run/ e pula comandos cujo log já existe",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    lock = acquire_lock()  # mantém o lock até o processo terminar
    prepare_tree(resume=args.resume)
    runs = []
    for label, script, command_args in RUNS:
        runs.append(run_one(label, script, command_args, resume=args.resume))
    copy_outputs(resume=args.resume)
    summary = build_summary(runs)
    summary_path = REPORT / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[reprocessamento] resumo: {summary_path}")
    print(f"[reprocessamento] arquivos copiados: {len(summary['files'])}")
    print(f"[reprocessamento] CSVs: {len(summary['csv'])}")
    print(
        "[reprocessamento] validação independente: "
        "python3 reprocessamento/validar_fase1.py"
    )


if __name__ == "__main__":
    main()
