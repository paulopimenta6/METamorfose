#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validação da amostra real de GFS 0.25° com pygrib e ponto conhecido."""

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "baseline" / "samples" / "gfs.20261022.00.0p25.subset.grb2"
SIDECAR = Path(str(SAMPLE) + ".json")

REFERENCE_SELECTORS = {
    "Temperature_850": ("Temperature", "isobaricInhPa", 850),
    "U_850": ("U component of wind", "isobaricInhPa", 850),
    "V_850": ("V component of wind", "isobaricInhPa", 850),
    "Temperature_surface": ("Temperature", "surface", 0),
    "U_20m": ("U component of wind", "heightAboveGround", 20),
    "V_20m": ("V component of wind", "heightAboveGround", 20),
    "Pressure_MSL": ("Pressure reduced to MSL", "meanSea", 0),
}


def _open_sample():
    pygrib = pytest.importorskip("pygrib")
    return pygrib.open(str(SAMPLE))


def _mean_at_point(message, lat: float, lon: float):
    data, _, _ = message.data(lat1=lat - 0.5, lat2=lat + 0.5, lon1=lon - 0.5, lon2=lon + 0.5)
    return float(np.nanmean(data))


def test_amostra_real_existe_ou_esta_documentada():
    if not SAMPLE.exists():
        pytest.skip(
            f"amostra ausente: {SAMPLE}. Rode tests/fetch_gfs_sample.py para baixá-la."
        )
    assert SAMPLE.stat().st_size > 0


def test_amostra_tem_as_mensagens_esperadas():
    if not SAMPLE.exists():
        pytest.skip("amostra GFS ausente")
    grbs = _open_sample()
    try:
        found = {(msg.name, msg.typeOfLevel, msg.level) for msg in grbs}
    finally:
        grbs.close()

    expected = set(REFERENCE_SELECTORS.values()) | {
        ("Relative humidity", "isobaricInhPa", 850),
        ("Total Cloud Cover", "isobaricInhPa", 850),
        ("2 metre temperature", "heightAboveGround", 2),
        ("10 metre U wind component", "heightAboveGround", 10),
        ("10 metre V wind component", "heightAboveGround", 10),
        ("U component of wind", "heightAboveGround", 30),
        ("V component of wind", "heightAboveGround", 30),
        ("U component of wind", "heightAboveGround", 40),
        ("V component of wind", "heightAboveGround", 40),
        ("U component of wind", "heightAboveGround", 50),
        ("V component of wind", "heightAboveGround", 50),
        ("U component of wind", "heightAboveGround", 80),
        ("V component of wind", "heightAboveGround", 80),
    }
    assert expected <= found, f"mensagens ausentes: {sorted(expected - found)}"


def test_amostra_tem_grade_global_com_latitude_decrescente():
    if not SAMPLE.exists():
        pytest.skip("amostra GFS ausente")
    grbs = _open_sample()
    try:
        msg = grbs.select(name="Temperature", typeOfLevel="isobaricInhPa", level=850)[0]
        data, lats, lons = msg.data()
    finally:
        grbs.close()

    assert data.shape == lats.shape == lons.shape
    assert data.shape[0] > 700
    assert data.shape[1] > 1400
    assert lats[0, 0] > lats[-1, 0]
    assert np.isfinite(data).mean() > 0.99


def test_ponto_conhecido_de_sao_paulo_e_fisicamente_plausivel():
    if not SAMPLE.exists():
        pytest.skip("amostra GFS ausente")
    grbs = _open_sample()
    try:
        selectors = {
            "Temperature_850": ("Temperature", "isobaricInhPa", 850),
            "Temperature_surface": ("Temperature", "surface", 0),
            "U_850": ("U component of wind", "isobaricInhPa", 850),
            "V_850": ("V component of wind", "isobaricInhPa", 850),
            "U_20m": ("U component of wind", "heightAboveGround", 20),
            "V_20m": ("V component of wind", "heightAboveGround", 20),
            "Pressure_MSL": ("Pressure reduced to MSL", "meanSea", 0),
        }
        values = {
            label: _mean_at_point(grbs.select(name=name, typeOfLevel=level_type, level=level)[0], -23.55, 313.37)
            for label, (name, level_type, level) in selectors.items()
        }
    finally:
        grbs.close()

    assert 240.0 < values["Temperature_850"] < 310.0
    assert 250.0 < values["Temperature_surface"] < 320.0
    assert abs(values["U_850"]) < 100.0
    assert abs(values["V_850"]) < 100.0
    assert abs(values["U_20m"]) < 50.0
    assert abs(values["V_20m"]) < 50.0
    assert 90000.0 < values["Pressure_MSL"] < 105000.0

    if SIDECAR.exists():
        sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
        reference = sidecar.get("reference_point", {})
        expected = reference.get("values", {})
        for label, value in values.items():
            if label in expected:
                assert value == pytest.approx(float(expected[label]), abs=1e-6), label
