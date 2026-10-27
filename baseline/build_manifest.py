#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera `baseline/manifest.json` com hashes, versões e resultados das Fases 0 e 1."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = Path(
    "/home/paulo/Documentos/meus_codigos/backups/"
    "servidor_MET-fase-0-20261023.tar.gz"
)
REPORT = ROOT / "baseline" / "reports" / "20261022-00"
SUMMARY = REPORT / "summary.json"
PYTEST = REPORT / "pytest.txt"
MANIFEST = ROOT / "baseline" / "manifest.json"

PHASE1_REPORT = ROOT / "reprocessamento" / "reports" / "20261022-00"
PHASE1_SUMMARY = PHASE1_REPORT / "summary.json"
PHASE1_PYTEST = PHASE1_REPORT / "pytest.txt"
PHASE1_VALIDATION = PHASE1_REPORT / "validation.json"

SOURCE_GLOBS = [
    ".gitignore",
    "pytest.ini",
    "goGribV2.sh",
    "remove_GRIBS_antigos.sh",
    "environment/path.conf",
    "bash/*.sh",
    "classes_MET/*.py",
    "METARpy/*.py",
    "METARpy/*.sh",
    "tests/*.py",
    "tests/*.md",
    "docs/*.md",
    "baseline/*.py",
    "baseline/*.md",
    "baseline/freeze.json",
    "baseline/samples/*.json",
    "baseline/reports/20261022-00/summary.json",
    "baseline/reports/20261022-00/pytest.txt",
    "reprocessamento/*.py",
    "reprocessamento/*.md",
    "reprocessamento/reports/20261022-00/summary.json",
    "reprocessamento/reports/20261022-00/validation.json",
    "reprocessamento/reports/20261022-00/pytest.txt",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def source_files():
    paths = set()
    for pattern in SOURCE_GLOBS:
        paths.update(ROOT.glob(pattern))
    result = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        result.append(
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def parse_pytest(text: str):
    counts = {}
    for name in (
        "passed",
        "failed",
        "skipped",
        "xfailed",
        "xpassed",
        "error",
        "deselected",
    ):
        match = re.search(rf"(\d+) {name}", text)
        counts[name] = int(match.group(1)) if match else 0
    xfail_tests = []
    for line in text.splitlines():
        if line.startswith("XFAIL "):
            xfail_tests.append(line.split()[1])
    return counts, xfail_tests


def find_csv(csvs, *, folder: str, level: str):
    for name, info in csvs.items():
        if not name.startswith(folder + "/"):
            continue
        if f"_N{level}_" in name and name.endswith(".csv"):
            return name, info
    return None, {}


def columns_identical(path: Path, first: int, second: int) -> bool:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return False
    return all(row[first] == row[second] for row in rows[1:])


def build_evidence(summary):
    csvs = summary.get("csv", {})
    temp_name, temp = find_csv(csvs, folder="matrizes", level="850")
    bluesky20_name, bluesky20 = find_csv(csvs, folder="bluesky", level="20")
    bluesky850_name, bluesky850 = find_csv(csvs, folder="bluesky", level="850")
    predi20_name, predi20 = find_csv(csvs, folder="predi", level="20")
    predi850_name, predi850 = find_csv(csvs, folder="predi", level="850")

    predi20_path = REPORT / predi20_name if predi20_name else None
    predi850_path = REPORT / predi850_name if predi850_name else None

    return {
        "temperature_850_csv": {
            "path": temp_name,
            "lat_first": temp.get("lat_first"),
            "lat_last": temp.get("lat_last"),
            "temp_range_c": temp.get("ranges", {}).get("temp"),
        },
        "bluesky_20m_csv": {
            "path": bluesky20_name,
            "hmet_range_ft": bluesky20.get("ranges", {}).get("hMET"),
            "angmet_range_deg": bluesky20.get("ranges", {}).get("angMET"),
        },
        "bluesky_850_csv": {
            "path": bluesky850_name,
            "hmet_range_ft": bluesky850.get("ranges", {}).get("hMET"),
            "angmet_range_deg": bluesky850.get("ranges", {}).get("angMET"),
        },
        "preditor_20m_csv": {
            "path": predi20_name,
            "vento_u_range": predi20.get("ranges", {}).get("vento U"),
            "vento_v_range": predi20.get("ranges", {}).get("vento V"),
            "u_equals_v": (
                columns_identical(predi20_path, 2, 3)
                if predi20_path and predi20_path.exists()
                else None
            ),
        },
        "preditor_850_csv": {
            "path": predi850_name,
            "vento_u_range": predi850.get("ranges", {}).get("vento U"),
            "vento_v_range": predi850.get("ranges", {}).get("vento V"),
            "u_equals_v": (
                columns_identical(predi850_path, 2, 3)
                if predi850_path and predi850_path.exists()
                else None
            ),
        },
        "reference_point": summary.get("sample", {}).get("reference_point"),
    }


def file_info(path: Path):
    if not path.is_file():
        return None
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_phase1():
    """Consolida a evidência da Fase 1 sem tocar na seção histórica da Fase 0."""
    if not (
        PHASE1_SUMMARY.is_file()
        and PHASE1_VALIDATION.is_file()
        and PHASE1_PYTEST.is_file()
    ):
        return None

    summary = json.loads(PHASE1_SUMMARY.read_text(encoding="utf-8"))
    validation = json.loads(PHASE1_VALIDATION.read_text(encoding="utf-8"))
    pytest_counts, _ = parse_pytest(PHASE1_PYTEST.read_text(encoding="utf-8"))

    return {
        "phase": "Fase 1",
        "base_commit": git("rev-parse", "fase-0-concluida^{commit}"),
        "purpose": (
            "Registrar as correções de cálculo D-01/D-02/D-03/D-04/D-12 e o "
            "reprocessamento da amostra em diretório separado."
        ),
        "fixes": ["D-01", "D-02", "D-03", "D-04", "D-12"],
        "report_dir": str(PHASE1_REPORT.relative_to(ROOT)),
        "fixed_local_time": summary.get("fixed_local_time"),
        "summary": file_info(PHASE1_SUMMARY),
        "validation": {
            **file_info(PHASE1_VALIDATION),
            "status": validation.get("status"),
            "checks": validation.get("checks"),
            "failures": validation.get("failures"),
        },
        "pytest": {
            **file_info(PHASE1_PYTEST),
            **pytest_counts,
            "total_cases": sum(
                pytest_counts.get(name, 0)
                for name in ("passed", "failed", "skipped", "xfailed", "xpassed")
            ),
        },
        "product_count": len(summary.get("files", [])),
        "csv_count": len(summary.get("csv", {})),
        "product_hashes": summary.get("files", []),
        "runs": summary.get("runs", []),
        "notes": [
            "O baseline da Fase 0 não foi sobrescrito e continua incorreto de "
            "propósito para comparação histórica.",
            "O reprocessamento usa a mesma amostra f000 do baseline; "
            "f006/f012/f018 são cópias com forecastTime=0.",
            "A validação independente com pygrib grava validation.json separado "
            "do summary.json e não é executada pelo runner.",
            "goGribV2.sh, URLs, ciclos, previsões, resoluções, variáveis, "
            "headers e nomes de produtos foram preservados.",
        ],
    }


def build_manifest():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    pytest_text = PYTEST.read_text(encoding="utf-8")
    pytest_counts, xfail_tests = parse_pytest(pytest_text)

    tags = {}
    for tag in ("fase-0-snapshot", "fase-0-inicio"):
        try:
            tags[tag] = {
                "object": git("rev-parse", tag),
                "commit": git("rev-parse", f"{tag}^{{commit}}"),
            }
        except subprocess.CalledProcessError:
            continue

    backup_info = None
    if BACKUP.exists():
        backup_info = {
            "path": str(BACKUP),
            "bytes": BACKUP.stat().st_size,
            "sha256": sha256_file(BACKUP),
        }

    report_files = []
    for path in sorted(REPORT.rglob("*")):
        if path.is_file():
            report_files.append(
                {
                    "path": str(path.relative_to(REPORT)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

    manifest = {
        "phase": "Fase 0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Registrar backup, snapshot Git, amostra GFS, baseline, harness e "
            "contratos antes das correções de cálculo."
        ),
        "repository": {
            "original": {
                "remote": "https://github.com/paulopimenta6/servidor_MET",
                "branch": "main",
                "snapshot_commit": git("rev-parse", "fase-0-snapshot^{commit}"),
            },
            "improvements": {
                "remote": "https://github.com/paulopimenta6/METamorfose",
                "branch": git("branch", "--show-current"),
                "phase_start_commit": git("rev-parse", "fase-0-inicio^{commit}"),
                "head_at_manifest_generation": git("rev-parse", "HEAD"),
            },
            "tags": tags,
        },
        "backup": backup_info,
        "freeze": json.loads(
            (ROOT / "baseline" / "freeze.json").read_text(encoding="utf-8")
        ),
        "sample": summary.get("sample"),
        "environment": summary.get("environment"),
        "baseline": {
            "report_dir": str(REPORT.relative_to(ROOT)),
            "fixed_local_time": summary.get("fixed_local_time"),
            "summary": {
                "path": str(SUMMARY.relative_to(ROOT)),
                "bytes": SUMMARY.stat().st_size,
                "sha256": sha256_file(SUMMARY),
            },
            "pytest": {
                "path": str(PYTEST.relative_to(ROOT)),
                "bytes": PYTEST.stat().st_size,
                "sha256": sha256_file(PYTEST),
            },
            "runs": summary.get("runs", []),
            "csv_count": len(summary.get("csv", {})),
            "product_count": len(summary.get("files", [])),
            "product_hashes": summary.get("files", []),
            "report_file_count": len(report_files),
            "report_file_hashes": report_files,
            "evidence": build_evidence(summary),
        },
        "tests": {
            **pytest_counts,
            "total_cases": sum(
                pytest_counts.get(name, 0)
                for name in ("passed", "failed", "skipped", "xfailed", "xpassed")
            ),
            "xfail_tests": xfail_tests,
        },
        "phase_1": build_phase1(),
        "source_files": source_files(),
        "notes": [
            "O baseline é intencionalmente incorreto e não deve ser usado como "
            "referência operacional.",
            "As previsões f006/f012/f018 do baseline são cópias da amostra f000; "
            "todas têm forecastTime=0 e o baseline representa apenas f000.",
            "A coluna lat dos CSVs do baseline é ascendente (-28 a -18), mas os "
            "dados ainda estão na ordem norte-sul do GFS (D-01).",
            "O código de produção não foi alterado; o goGribV2.sh está congelado.",
            "O backup contém o snapshot do código e dos dados METAR versionados; "
            "não havia produtos GFS históricos disponíveis em /media/MET.",
            "A tag fase-0-concluida é criada depois deste manifesto, no commit "
            "que contém a suíte de aceitação; consulte git tag no repositório.",
        ],
    }
    return manifest


def main():
    if not SUMMARY.exists():
        raise SystemExit(f"resumo ausente: {SUMMARY}; rode baseline/run_baseline.py")
    if not PYTEST.exists():
        raise SystemExit(f"saída do pytest ausente: {PYTEST}; rode python3 -m pytest -q")

    manifest = build_manifest()
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"manifesto: {MANIFEST}")
    print(f"arquivos de código/documentação: {len(manifest['source_files'])}")
    print(f"produtos do baseline: {manifest['baseline']['product_count']}")
    print(
        "testes: "
        f"{manifest['tests']['passed']} passed, "
        f"{manifest['tests']['xfailed']} xfailed, "
        f"{manifest['tests']['skipped']} skipped"
    )
    if manifest["phase_1"]:
        validation = manifest["phase_1"]["validation"]
        print(f"produtos da Fase 1: {manifest['phase_1']['product_count']}")
        print(
            "validação da Fase 1: "
            f"{validation['checks']} verificações, "
            f"{validation['failures']} falhas"
        )


if __name__ == "__main__":
    main()
