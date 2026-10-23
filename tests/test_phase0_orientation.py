#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de orientação, headers e chamadas dos geradores de matrizes."""

import ast
from pathlib import Path

import numpy as np
import pytest

from phase0_harness import (
    CLASSES,
    grid_values,
    read_csv,
    run_bluesky_matrix,
    run_man_bluesky,
    run_predi_matrix,
    run_scalar_matrix,
)


def _first_data_row(path: Path):
    rows = read_csv(path)
    assert len(rows) >= 2
    return rows[0], rows[1]


def test_matriz_escalar_cabecalho_atual(tmp_path):
    path = run_scalar_matrix(tmp_path)
    header, row = _first_data_row(path)
    assert header == ["lat", "lon", "temp"]
    assert len(row) == 3


def test_matriz_escalar_converte_kelvin_para_celsius(tmp_path):
    lat = np.array([10.0, 0.0, -10.0])
    lon = np.array([-60.0, -50.0, -40.0, -30.0])
    path = run_scalar_matrix(tmp_path, data=np.full((lat.size, lon.size), 300.0))
    _, row = _first_data_row(path)
    assert float(row[2]) == pytest.approx(26.85, abs=0.01)


@pytest.mark.xfail(
    strict=True,
    reason="D-01: a latitude é invertida, mas os dados não; a primeira linha do CSV não corresponde ao sul.",
)
def test_matriz_escalar_primeira_linha_deve_ser_o_sul(tmp_path):
    lat = np.array([10.0, 0.0, -10.0])
    lon = np.array([-60.0, -50.0, -40.0, -30.0])
    data = grid_values(lat, lon)
    path = run_scalar_matrix(tmp_path, data=data)
    _, row = _first_data_row(path)
    assert float(row[0]) == pytest.approx(-10.0)
    assert float(row[2]) == pytest.approx(float(data[2, 0]))


def test_bluesky_cabecalho_atual(tmp_path):
    path = run_bluesky_matrix(tmp_path)
    header, row = _first_data_row(path)
    assert header == ["lat", "lon", "hMET", "angMET", "vento_resultante"]
    assert len(row) == 5


def test_bluesky_resultante_em_nos(tmp_path):
    path = run_bluesky_matrix(tmp_path)
    _, row = _first_data_row(path)
    assert float(row[4]) == pytest.approx(10.0 * 1.943, abs=0.001)


def test_bluesky_altitude_de_pressao_500_hpa(tmp_path):
    path = run_bluesky_matrix(tmp_path, level=500)
    _, row = _first_data_row(path)
    assert float(row[2]) == pytest.approx(18281.18, abs=0.1)


@pytest.mark.xfail(
    strict=True,
    reason="D-03: hMET de 20 m usa a fórmula de pressão (76.487 ft) em vez de 65,6 ft.",
)
def test_bluesky_altitude_de_20_metros(tmp_path):
    path = run_bluesky_matrix(tmp_path, level=20)
    _, row = _first_data_row(path)
    assert float(row[2]) == pytest.approx(65.6168, abs=0.01)


@pytest.mark.xfail(
    strict=True,
    reason="D-12: angMET de vento de oeste sai -90 em vez de 270.",
)
def test_bluesky_angulo_de_vento_de_oeste(tmp_path):
    path = run_bluesky_matrix(tmp_path)
    _, row = _first_data_row(path)
    assert float(row[3]) == pytest.approx(270.0)


@pytest.mark.xfail(
    strict=True,
    reason="D-01: a primeira linha tem lat=-10, mas o valor ainda é o da linha de lat=10.",
)
def test_bluesky_primeira_linha_deve_ser_o_sul(tmp_path):
    lat = np.array([10.0, 0.0, -10.0])
    lon = np.array([-60.0, -50.0, -40.0, -30.0])
    u = 10.0 + (lat[:, None] + 10.0)  # 10 no sul, 20 no equador, 30 no norte
    v = np.zeros_like(u)
    path = run_bluesky_matrix(tmp_path, lat=lat, lon=lon, u=u, v=v)
    _, row = _first_data_row(path)
    assert float(row[0]) == pytest.approx(-10.0)
    assert float(row[4]) == pytest.approx(10.0 * 1.943, abs=0.001)


def test_preditor_cabecalho_atual(tmp_path):
    path = run_predi_matrix(tmp_path)
    header, row = _first_data_row(path)
    assert header == ["lat", "lon", "vento U", "vento V", "temp"]
    assert len(row) == 5


def test_preditor_preserva_u_e_v_quando_recebe_componentes_corretas(tmp_path):
    path = run_predi_matrix(tmp_path)
    _, row = _first_data_row(path)
    assert float(row[2]) == pytest.approx(10.0)
    assert float(row[3]) == pytest.approx(0.0)
    assert float(row[4]) == pytest.approx(280.0)


@pytest.mark.xfail(
    strict=True,
    reason="D-01: a primeira linha tem lat=-10, mas o U ainda é o da linha de lat=10.",
)
def test_preditor_primeira_linha_deve_ser_o_sul(tmp_path):
    lat = np.array([10.0, 0.0, -10.0])
    lon = np.array([-60.0, -50.0, -40.0, -30.0])
    u = 10.0 + (lat[:, None] + 10.0)
    v = np.zeros_like(u)
    path = run_predi_matrix(tmp_path, lat=lat, lon=lon, u=u, v=v)
    _, row = _first_data_row(path)
    assert float(row[0]) == pytest.approx(-10.0)
    assert float(row[2]) == pytest.approx(10.0)


def test_man_bluesky_cabecalho_atual(tmp_path):
    path = run_man_bluesky(tmp_path)
    header, row = _first_data_row(path)
    assert header == ["lat", "lon", "hMET<feet>", "angMET<grau>", "vento_resultante<knot>"]
    assert len(row) == 5


@pytest.mark.xfail(
    strict=True,
    reason="D-03: hMET do MAN para 20 m também usa a fórmula de pressão.",
)
def test_man_bluesky_altitude_de_20_metros(tmp_path):
    path = run_man_bluesky(tmp_path)
    _, row = _first_data_row(path)
    assert float(row[2]) == pytest.approx(65.6168, abs=0.01)


@pytest.mark.xfail(
    strict=True,
    reason="D-12: angMET do MAN também não é normalizado.",
)
def test_man_bluesky_angulo_de_vento_de_oeste(tmp_path):
    path = run_man_bluesky(tmp_path)
    _, row = _first_data_row(path)
    assert float(row[3]) == pytest.approx(270.0)


def _calls_in_function(source: Path, function_name: str, call_name: str):
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == call_name
    ]


@pytest.mark.xfail(
    strict=True,
    reason="D-02: geraMatrizVentoSup passa u_comp_supe também como componente V do preditor.",
)
def test_aut_preditor_deve_receber_v_comp_supe():
    calls = _calls_in_function(
        CLASSES / "gera_matriz_vento_MET.py",
        "geraMatrizVentoSup",
        "geraMatriz_Vento_UVT_predi",
    )
    assert len(calls) == 1
    second_arg = calls[0].args[1]
    assert isinstance(second_arg, ast.Name)
    assert second_arg.id == "v_comp_supe"


@pytest.mark.xfail(
    strict=True,
    reason="D-02: o mapa de vento superficial lê uSupe para a componente V.",
)
def test_mapa_vento_superficial_deve_ler_v_supe():
    tree = ast.parse(
        (CLASSES / "gera_mapas_vento_MET.py").read_text(encoding="utf-8"),
        filename="gera_mapas_vento_MET.py",
    )
    wrong = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if "v_comp" not in targets:
            continue
        call = node.value
        # Desembrulha chamadas externas, p.ex.
        # processamento_dados_met_AUT("uSupe", ...).define_lista_var_com_altitude()
        while (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Call)
        ):
            call = call.func.value
        if not isinstance(call, ast.Call):
            continue
        if not call.args or not isinstance(call.args[0], ast.Constant):
            continue
        if call.args[0].value == "uSupe":
            wrong.append(node.lineno)
    assert wrong == [], f"v_comp usa uSupe nas linhas {wrong}"
