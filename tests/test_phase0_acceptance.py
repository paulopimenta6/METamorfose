#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aceitação automatizada dos entregáveis da Fase 0.

Diferente dos testes de ``test_phase0_real_grib.py``, esta suíte não usa
``skip``: o backup, a amostra, o baseline e os remotos Git são pré-requisitos
da aceitação. Se algum deles estiver ausente, o teste falha de forma explícita.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pygrib
import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "baseline" / "reports" / "20261022-00"
SUMMARY = REPORT / "summary.json"
SAMPLE = ROOT / "baseline" / "samples" / "gfs.20261022.00.0p25.subset.grb2"
SIDECAR = Path(str(SAMPLE) + ".json")
MANIFEST = ROOT / "baseline" / "manifest.json"
FREEZE = ROOT / "baseline" / "freeze.json"
BACKUP = Path(
    os.environ.get(
        "MET_PHASE0_BACKUP",
        "/home/paulo/Documentos/meus_codigos/backups/"
        "servidor_MET-fase-0-20261023.tar.gz",
    )
)

SNAPSHOT_COMMIT = "3bf69eebf2322df6cb10ac176ca05ed342ef68df"
PHASE_START_COMMIT = "3bf74a12e190c79c67f7117d6c1d81dcaf3124ac"
BACKUP_SHA256 = "15d9710edbba23d760953436b7e1463177a3d9785da35329b0dedad87cdba3fe"
SAMPLE_SHA256 = "7adc84c35743c9fe4884756b938f38c8a18a5278d3b30bb945a300adde908a90"
SIDECAR_SHA256 = "fc7b1f607b5b91512325591a0d99bda76e70848be9bfd1d1730c4ea9df69e31d"
FREEZE_SHA256 = "994ce16c1480b17a62b78e72761307af2000dc47819abbaf48ce042c72023ce0"

pytestmark = pytest.mark.acceptance


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def _git(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def _git_ok(*args: str, timeout: int = 30) -> str:
    completed = _git(*args, timeout=timeout)
    assert completed.returncode == 0, (
        f"git {' '.join(args)} falhou com código {completed.returncode}:\n"
        f"{completed.stderr or completed.stdout}"
    )
    return completed.stdout.strip()


def _point_value(message, lat: float, lon: float) -> float:
    values, _, _ = message.data(
        lat1=lat,
        lat2=lat,
        lon1=lon % 360,
        lon2=lon % 360,
    )
    return float(np.asarray(values).squeeze())


@pytest.fixture(scope="module")
def sample_grib():
    assert SAMPLE.is_file(), f"amostra GFS ausente: {SAMPLE}"
    grbs = pygrib.open(str(SAMPLE))
    try:
        yield grbs
    finally:
        grbs.close()


@pytest.fixture(scope="module")
def summary():
    assert SUMMARY.is_file(), f"resumo do baseline ausente: {SUMMARY}"
    return _load_json(SUMMARY)


@pytest.fixture(scope="module")
def manifest():
    assert MANIFEST.is_file(), f"manifesto ausente: {MANIFEST}"
    return _load_json(MANIFEST)


# ---------------------------------------------------------------------------
# Artefatos externos e congelamento
# ---------------------------------------------------------------------------


def test_backup_da_fase_0_existe_com_hash_esperado():
    assert BACKUP.is_file(), f"backup da Fase 0 ausente: {BACKUP}"
    assert BACKUP.stat().st_size == 5_300_650
    assert _sha256(BACKUP) == BACKUP_SHA256


def test_amostra_gfs_e_sidecar_estao_integros():
    assert SAMPLE.is_file(), f"amostra GFS ausente: {SAMPLE}"
    assert SIDECAR.is_file(), f"sidecar ausente: {SIDECAR}"
    assert SAMPLE.stat().st_size == 14_852_876
    assert _sha256(SAMPLE) == SAMPLE_SHA256
    assert _sha256(SIDECAR) == SIDECAR_SHA256

    sidecar = _load_json(SIDECAR)
    assert sidecar["file"]["bytes"] == SAMPLE.stat().st_size
    assert sidecar["file"]["sha256"] == SAMPLE_SHA256
    assert sidecar["source"]["date"] == "20261022"
    assert sidecar["source"]["cycle"] == "00"
    assert sidecar["source"]["resolution"] == "0p25"
    assert sidecar["source"]["forecast_hour"] == "000"
    assert len(sidecar["selection"]) == 20
    assert sidecar["validation"]["message_count"] == 20


def test_go_grib_v2_esta_congelado():
    freeze = _load_json(FREEZE)
    frozen = freeze["files"]["goGribV2.sh"]
    script = ROOT / "goGribV2.sh"
    assert script.is_file()
    assert script.stat().st_size == 4_291
    assert _sha256(script) == FREEZE_SHA256
    assert frozen["sha256"] == FREEZE_SHA256
    assert frozen["bytes"] == 4_291

    invariants = freeze["invariants"]
    assert invariants["cycles"] == ["00", "06", "12", "18"]
    assert invariants["forecasts"] == ["f000", "f006", "f012", "f018"]
    assert invariants["resolutions"] == ["0p25", "1p00"]
    assert invariants["source"] == (
        "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"
    )


# ---------------------------------------------------------------------------
# Baseline: inventário, hashes e contratos dos CSVs
# ---------------------------------------------------------------------------


def test_baseline_tem_20_produtos_e_22_arquivos(summary):
    assert len(summary["files"]) == 20
    assert len(summary["csv"]) == 13
    assert len(summary["runs"]) == 6
    assert len(list(REPORT.glob("mapas/*.png"))) == 7
    assert len(list(REPORT.glob("matrizes/*.csv"))) == 1
    assert len(list(REPORT.glob("bluesky/*.csv"))) == 6
    assert len(list(REPORT.glob("predi/*.csv"))) == 6
    assert len([path for path in REPORT.rglob("*") if path.is_file()]) == 22
    assert (REPORT / "summary.json").is_file()
    assert (REPORT / "pytest.txt").is_file()
    assert all(run["returncode"] == 0 for run in summary["runs"])


def test_todos_os_produtos_do_baseline_tem_hash_esperado(summary):
    for item in summary["files"]:
        path = REPORT / item["path"]
        assert path.is_file(), f"produto ausente: {path}"
        assert path.stat().st_size == item["bytes"], path
        assert _sha256(path) == item["sha256"], path


def test_csvs_tem_headers_ordem_e_crlf_estaveis(summary):
    expected_headers = {
        "matrizes": ["lat", "lon", "temp"],
        "bluesky": ["lat", "lon", "hMET", "angMET", "vento_resultante"],
        "predi": ["lat", "lon", "vento U", "vento V", "temp"],
    }
    assert len(summary["csv"]) == 13

    for name, info in summary["csv"].items():
        path = REPORT / name
        assert path.is_file(), f"CSV ausente: {path}"
        folder = name.split("/", 1)[0]
        assert folder in expected_headers, name
        assert info["header"] == expected_headers[folder]

        rows = _csv_rows(path)
        assert rows[0] == expected_headers[folder]
        assert len(rows) - 1 == info["rows"] == 2_337

        lat_values = [float(row[0]) for row in rows[1:]]
        lon_values = [float(row[1]) for row in rows[1:]]
        pairs = list(zip(lat_values, lon_values))
        assert pairs == sorted(pairs), f"ordem lat/lon fora do contrato: {name}"
        assert lat_values[0] == info["lat_first"] == -28.0
        assert lat_values[-1] == info["lat_last"] == -18.0
        assert len(set(lat_values)) == 41
        assert len(set(lon_values)) == 57
        assert min(lon_values) == -56.0
        assert max(lon_values) == -42.0

        raw = path.read_bytes()
        assert raw.count(b"\n") == raw.count(b"\r\n") == len(rows)


# ---------------------------------------------------------------------------
# Evidências dos defeitos congelados no baseline
# ---------------------------------------------------------------------------


def test_baseline_reproduz_d01_orientacao_norte_sul(summary, sample_grib):
    temp_name = next(
        name
        for name in summary["csv"]
        if name.startswith("matrizes/") and name.endswith(".csv")
    )
    rows = _csv_rows(REPORT / temp_name)
    first = next(
        row
        for row in rows[1:]
        if float(row[0]) == -28.0 and float(row[1]) == -56.0
    )
    csv_celsius = float(first[2])
    assert csv_celsius == pytest.approx(26.093398437500014, abs=1e-12)

    message = sample_grib.select(
        name="Temperature", typeOfLevel="isobaricInhPa", level=850
    )[0]
    north = _point_value(message, -18.0, -56.0) - 273.15
    south = _point_value(message, -28.0, -56.0) - 273.15

    assert csv_celsius == pytest.approx(north, abs=1e-9)
    assert abs(csv_celsius - south) > 1.0


def test_baseline_reproduz_d02_u_igual_a_v_no_preditor(summary):
    predi20 = next(
        name
        for name in summary["csv"]
        if name.startswith("predi/") and "_N20_" in name
    )
    predi850 = next(
        name
        for name in summary["csv"]
        if name.startswith("predi/") and "_N850_" in name
    )

    rows20 = _csv_rows(REPORT / predi20)
    assert all(float(row[2]) == float(row[3]) for row in rows20[1:])

    rows850 = _csv_rows(REPORT / predi850)
    assert any(float(row[2]) != float(row[3]) for row in rows850[1:])


def test_baseline_reproduz_d03_conversao_de_altura(summary):
    def hmet_values(level: str):
        name = next(
            name
            for name in summary["csv"]
            if name.startswith("bluesky/") and f"_N{level}_" in name
        )
        return [float(row[2]) for row in _csv_rows(REPORT / name)[1:]]

    values20 = hmet_values("20")
    values80 = hmet_values("80")
    assert all(value == pytest.approx(76_487.0117634869, abs=1e-9) for value in values20)
    assert all(value == pytest.approx(55_695.456840965366, abs=1e-9) for value in values80)
    assert all(abs(value - 65.6168) > 1.0 for value in values20)
    assert all(abs(value - 262.4672) > 1.0 for value in values80)


def test_baseline_reproduz_d12_angulos_negativos(summary):
    for level in ("20", "850"):
        name = next(
            name
            for name in summary["csv"]
            if name.startswith("bluesky/") and f"_N{level}_" in name
        )
        angles = [float(row[3]) for row in _csv_rows(REPORT / name)[1:]]
        assert min(angles) < 0.0, level
        assert max(angles) < 360.0, level


# ---------------------------------------------------------------------------
# Documentação, manifesto e integridade do repositório
# ---------------------------------------------------------------------------


def test_documentos_e_relatorios_obrigatorios_existem():
    required = [
        ROOT / "docs" / "07-fase-0-baseline.md",
        ROOT / "docs" / "08-contratos-e-consumidores.md",
        ROOT / "docs" / "README.md",
        ROOT / "tests" / "README.md",
        ROOT / "baseline" / "README.md",
        ROOT / "baseline" / "manifest.json",
        REPORT / "summary.json",
        REPORT / "pytest.txt",
    ]
    for path in required:
        assert path.is_file(), f"documento/relatório ausente: {path}"
        assert path.stat().st_size > 0, f"documento/relatório vazio: {path}"


def test_manifesto_consolida_os_artefatos_da_fase_0(summary, manifest):
    assert manifest["phase"] == "Fase 0"
    assert manifest["backup"]["bytes"] == BACKUP.stat().st_size
    assert manifest["backup"]["sha256"] == BACKUP_SHA256
    assert manifest["sample"]["sha256"] == SAMPLE_SHA256
    assert manifest["sample"]["sidecar_sha256"] == SIDECAR_SHA256
    assert manifest["freeze"]["files"]["goGribV2.sh"]["sha256"] == FREEZE_SHA256
    assert manifest["freeze"]["invariants"]["cycles"] == ["00", "06", "12", "18"]
    assert manifest["repository"]["original"]["snapshot_commit"] == SNAPSHOT_COMMIT
    assert manifest["repository"]["tags"]["fase-0-snapshot"]["commit"] == SNAPSHOT_COMMIT
    assert manifest["repository"]["tags"]["fase-0-inicio"]["commit"] == PHASE_START_COMMIT

    assert manifest["baseline"]["product_count"] == 20
    assert manifest["baseline"]["csv_count"] == 13
    assert manifest["baseline"]["report_file_count"] == 22
    manifest_products = {
        item["path"]: item["sha256"]
        for item in manifest["baseline"]["product_hashes"]
    }
    summary_products = {item["path"]: item["sha256"] for item in summary["files"]}
    assert manifest_products == summary_products

    evidence = manifest["baseline"]["evidence"]
    assert evidence["preditor_20m_csv"]["u_equals_v"] is True
    assert evidence["preditor_850_csv"]["u_equals_v"] is False
    assert evidence["temperature_850_csv"]["lat_first"] == -28.0
    assert evidence["temperature_850_csv"]["lat_last"] == -18.0

    tests = manifest["tests"]
    assert tests["failed"] == 0
    assert tests["error"] == 0
    assert tests["skipped"] == 0
    assert tests["xfailed"] == 20
    assert tests["xpassed"] == 0
    assert tests["passed"] >= 22
    assert tests["total_cases"] >= 42
    assert len(tests["xfail_tests"]) == 20


def test_codigo_de_producao_nao_mudou_desde_o_snapshot():
    changed = _git_ok(
        "diff",
        "--name-only",
        f"{SNAPSHOT_COMMIT}..HEAD",
        "--",
        "classes_MET",
        "bash",
        "environment",
        "METARpy",
        "goGribV2.sh",
        "remove_GRIBS_antigos.sh",
        "varMET",
        "varPythonGrib",
        "variables.txt",
        "variable_inside_list.txt",
    )
    assert changed == "", f"código/dados de produção alterados:\n{changed}"


def test_amostra_binaria_e_run_nao_estao_versionados():
    tracked = _git_ok("ls-files", "baseline/samples", "baseline/run").splitlines()
    assert "baseline/samples/gfs.20261022.00.0p25.subset.grb2.json" in tracked
    assert not any(path.endswith(".grb2") for path in tracked)
    assert not any(path.startswith("baseline/run/") for path in tracked)


def test_branch_de_execucao_e_execucao():
    assert _git_ok("branch", "--show-current") == "execucao"


# ---------------------------------------------------------------------------
# Remotos Git (rede)
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_tag_fase_0_concluida_esta_no_remoto():
    local = _git_ok("rev-parse", "fase-0-concluida^{commit}")
    remote_output = _git_ok(
        "ls-remote", "melhorias", "refs/tags/fase-0-concluida^{}"
    )
    assert remote_output, "tag fase-0-concluida ausente no remoto melhorias"
    remote = remote_output.split()[0]
    assert remote == local
    assert _git("merge-base", "--is-ancestor", local, "HEAD").returncode == 0


@pytest.mark.network
def test_main_original_continua_no_snapshot():
    remote_output = _git_ok("ls-remote", "origin", "refs/heads/main")
    assert remote_output, "branch main ausente no repositório original"
    assert remote_output.split()[0] == SNAPSHOT_COMMIT


@pytest.mark.network
def test_branch_execucao_remota_contem_o_commit_atual():
    head = _git_ok("rev-parse", "HEAD")
    remote_output = _git_ok("ls-remote", "melhorias", "refs/heads/execucao")
    assert remote_output, "branch execucao ausente no remoto melhorias"
    assert remote_output.split()[0] == head
