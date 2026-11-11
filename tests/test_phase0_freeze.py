#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Congelamento do script de aquisição GRIB (Fase 0)."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "baseline" / "freeze.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_go_grib_v2_esta_congelado():
    manifest = json.loads(FREEZE.read_text(encoding="utf-8"))
    expected = manifest["files"]["goGribV2.sh"]["sha256"]
    actual = sha256(ROOT / "goGribV2.sh")
    assert actual == expected, (
        "goGribV2.sh foi alterado. A aquisição GRIB está congelada na Fase 0; "
        "qualquer mudança exige revisão explícita do plano."
    )


def test_invariantes_da_aquisicao_estao_documentados():
    manifest = json.loads(FREEZE.read_text(encoding="utf-8"))
    invariants = manifest["invariants"]
    assert invariants["cycles"] == ["00", "06", "12", "18"]
    assert invariants["forecasts"] == ["f000", "f006", "f012", "f018"]
    assert invariants["resolutions"] == ["0p25", "1p00"]
    assert invariants["source"].startswith("https://nomads.ncep.noaa.gov/")
