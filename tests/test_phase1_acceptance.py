#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aceitação da Fase 1: D-01, D-02, D-03, D-04 e D-12 (T-01 a T-05).

Os testes exercitam o código de produção extraído pela AST, sem importar os
módulos com efeitos colaterais. Mapas usam um Basemap/plt de captura para
verificar a matriz efetivamente entregue ao desenho.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phase0_harness import (
    CLASSES,
    grid_values,
    read_csv,
    run_bluesky_matrix,
    run_man_bluesky,
    run_man_predi,
    run_predi_matrix,
    run_reader_at,
    run_scalar_matrix,
    run_scalar_map,
    run_wind_map,
    run_man_scalar_map,
    run_man_wind_map,
)

pytestmark = pytest.mark.acceptance

LAT = np.array([10.0, 0.0, -10.0])
LON = np.array([-60.0, -50.0, -40.0, -30.0])
LON_CROSS = np.array([-70.0, -60.0, -50.0, -40.0, -30.0, -20.0, -10.0, 0.0, 10.0])

HEADERS = {
    "scalar": ["lat", "lon", "temp"],
    "bluesky": ["lat", "lon", "hMET", "angMET", "vento_resultante"],
    "predi": ["lat", "lon", "vento U", "vento V", "temp"],
    "man_bluesky": [
        "lat",
        "lon",
        "hMET<feet>",
        "angMET<grau>",
        "vento_resultante<knot>",
    ],
    "man_predi": ["lat", "lon", "vento U", "vento V", "temperatura K"],
}


def _rows(path: Path):
    rows = read_csv(path)
    assert rows, f"CSV vazio: {path}"
    return rows


def _lat_values(rows):
    return [float(row[0]) for row in rows[1:]]


def _group_by_lat(rows):
    grouped = {}
    for row in rows[1:]:
        grouped.setdefault(float(row[0]), []).append(row)
    return grouped


def _assert_lat_ascending(rows):
    lats = _lat_values(rows)
    assert lats == sorted(lats), lats
    counts = {lat: lats.count(lat) for lat in set(lats)}
    assert len(set(counts.values())) == 1, counts


def _assert_rows_match(rows, expected_by_lat, column, *, offset=0.0):
    """Confere cada linha do CSV contra a matriz original indexada por latitude."""

    grouped = _group_by_lat(rows)
    assert sorted(grouped) == sorted(expected_by_lat)
    for lat, lat_rows in grouped.items():
        values = [float(row[column]) for row in lat_rows]
        expected = list(np.asarray(expected_by_lat[lat], dtype=float) + offset)
        assert values == pytest.approx(expected), lat


def _assert_south_first(rows, south_value, column):
    first = rows[1]
    assert float(first[0]) == pytest.approx(float(LAT.min()))
    assert float(first[column]) == pytest.approx(south_value)


def _single_contourf(basemaps):
    calls = [call for basemap in basemaps for call in basemap.contourf_calls]
    assert len(calls) == 1, calls
    return calls[0]


def _single_streamplot(plt):
    assert len(plt.streamplot_calls) == 1, plt.streamplot_calls
    return plt.streamplot_calls[0]


# ---------------------------------------------------------------------------
# T-01 — orientação norte-sul
# ---------------------------------------------------------------------------


def test_t01_matriz_escalar_alinha_dados_com_lat_ascendente(tmp_path):
    data = grid_values(LAT, LON)
    path = run_scalar_matrix(tmp_path, lat=LAT, lon=LON, data=data)
    rows = _rows(path)
    assert rows[0] == HEADERS["scalar"]
    _assert_lat_ascending(rows)
    _assert_rows_match(
        rows,
        {lat: data[index, :] for index, lat in enumerate(LAT)},
        2,
        offset=-273.15,
    )


def test_t01_bluesky_alinha_vento_com_lat_ascendente(tmp_path):
    u = 5.0 + LAT[:, None] + np.zeros_like(LON)
    v = np.zeros_like(u)
    path = run_bluesky_matrix(tmp_path, lat=LAT, lon=LON, u=u, v=v)
    rows = _rows(path)
    assert rows[0] == HEADERS["bluesky"]
    _assert_lat_ascending(rows)
    _assert_rows_match(
        rows,
        {lat: np.abs(u[index, :]) * 1.943 for index, lat in enumerate(LAT)},
        4,
    )
    _assert_south_first(rows, abs(u[2, 0]) * 1.943, 4)


def test_t01_preditor_alinha_u_v_com_lat_ascendente(tmp_path):
    u = np.array([[10.0, 11.0, 12.0, 13.0], [20.0, 21.0, 22.0, 23.0], [30.0, 31.0, 32.0, 33.0]])
    v = -u
    path = run_predi_matrix(tmp_path, lat=LAT, lon=LON, u=u, v=v)
    rows = _rows(path)
    assert rows[0] == HEADERS["predi"]
    _assert_lat_ascending(rows)
    _assert_rows_match(rows, {lat: u[index, :] for index, lat in enumerate(LAT)}, 2)
    _assert_rows_match(rows, {lat: v[index, :] for index, lat in enumerate(LAT)}, 3)
    _assert_south_first(rows, u[2, 0], 2)


def test_t01_man_bluesky_alinha_vento_com_lat_ascendente(tmp_path):
    u = 5.0 + LAT[:, None] + np.zeros_like(LON)
    v = np.zeros_like(u)
    path = run_man_bluesky(tmp_path, lat=LAT, lon=LON, u=u, v=v)
    rows = _rows(path)
    assert rows[0] == HEADERS["man_bluesky"]
    _assert_lat_ascending(rows)
    _assert_rows_match(
        rows,
        {lat: np.abs(u[index, :]) * 1.943 for index, lat in enumerate(LAT)},
        4,
    )
    _assert_south_first(rows, abs(u[2, 0]) * 1.943, 4)


def test_t01_man_preditor_alinha_u_v_com_lat_ascendente(tmp_path):
    u = np.array([[10.0, 11.0, 12.0, 13.0], [20.0, 21.0, 22.0, 23.0], [30.0, 31.0, 32.0, 33.0]])
    v = -u
    path = run_man_predi(tmp_path, lat=LAT, lon=LON, u=u, v=v)
    rows = _rows(path)
    assert rows[0] == HEADERS["man_predi"]
    _assert_lat_ascending(rows)
    _assert_rows_match(rows, {lat: u[index, :] for index, lat in enumerate(LAT)}, 2)
    _assert_rows_match(rows, {lat: v[index, :] for index, lat in enumerate(LAT)}, 3)
    _assert_south_first(rows, u[2, 0], 2)


@pytest.mark.parametrize(
    "runner,column,expected,magnitude,factor",
    [
        ("scalar", 2, "data", False, 1.0),
        ("bluesky", 4, "u", True, 1.943),
        ("predi", 2, "u", False, 1.0),
        ("man_bluesky", 4, "u", True, 1.943),
        ("man_predi", 2, "u", False, 1.0),
    ],
)
def test_t01_ramo_flag3_alinha_linhas_com_lat_ascendente(
    tmp_path, runner, column, expected, magnitude, factor
):
    data = grid_values(LAT, LON_CROSS)
    u = 5.0 + LAT[:, None] + np.zeros_like(LON_CROSS)
    v = np.zeros_like(u)
    kwargs = {"lat": LAT, "lon": LON_CROSS}

    if runner == "scalar":
        path = run_scalar_matrix(tmp_path, data=data, **kwargs)
    elif runner == "bluesky":
        path = run_bluesky_matrix(tmp_path, u=u, v=v, **kwargs)
    elif runner == "predi":
        path = run_predi_matrix(tmp_path, u=u, v=v, **kwargs)
    elif runner == "man_bluesky":
        path = run_man_bluesky(tmp_path, u=u, v=v, **kwargs)
    else:
        path = run_man_predi(tmp_path, u=u, v=v, **kwargs)

    rows = _rows(path)
    _assert_lat_ascending(rows)
    assert float(rows[1][0]) == pytest.approx(float(LAT.min()))
    assert float(rows[-1][0]) == pytest.approx(float(LAT.max()))

    if expected == "data":
        assert float(rows[1][column]) == pytest.approx(data[2, 0] - 273.15)
        assert float(rows[-1][column]) == pytest.approx(data[0, -1] - 273.15)
    else:
        south = (abs(u[2, 0]) if magnitude else u[2, 0]) * factor
        north = (abs(u[0, -1]) if magnitude else u[0, -1]) * factor
        assert float(rows[1][column]) == pytest.approx(south)
        assert float(rows[-1][column]) == pytest.approx(north)


def test_t01_mapa_escalar_desenha_primeiro_o_sul(tmp_path):
    data = grid_values(LAT, LON)
    basemaps, _ = run_scalar_map(tmp_path, lat=LAT, lon=LON, data=data)
    _, y, plotted, _ = _single_contourf(basemaps)

    assert y[:, 0].tolist() == pytest.approx(LAT[::-1])
    assert plotted.tolist() == pytest.approx((data - 273.15)[::-1, :])


def test_t01_mapa_de_vento_desenha_primeiro_o_sul(tmp_path):
    u = 5.0 + LAT[:, None] + np.zeros_like(LON)
    v = np.zeros_like(u)
    _, plt = run_wind_map(tmp_path, lat=LAT, lon=LON, u=u, v=v)
    # O mapa de vento usa streamplot, não contourf.
    _, lats, plotted_u, plotted_v = _single_streamplot(plt)
    assert lats[:, 0].tolist() == pytest.approx(LAT[::-1])
    assert plotted_u.tolist() == pytest.approx(u[::-1, :])
    assert plotted_v.tolist() == pytest.approx(v[::-1, :])


def test_t01_mapa_man_escalar_desenha_primeiro_o_sul(tmp_path):
    data = grid_values(LAT, LON)
    basemaps, _ = run_man_scalar_map(tmp_path, lat=LAT, lon=LON, data=data)
    _, y, plotted, _ = _single_contourf(basemaps)
    assert y[:, 0].tolist() == pytest.approx(LAT[::-1])
    assert plotted.tolist() == pytest.approx((data - 273.15)[::-1, :])


def test_t01_mapa_man_de_vento_desenha_primeiro_o_sul(tmp_path):
    u = 5.0 + LAT[:, None] + np.zeros_like(LON)
    v = np.zeros_like(u)
    _, plt = run_man_wind_map(tmp_path, lat=LAT, lon=LON, u=u, v=v)
    _, lats, plotted_u, plotted_v = _single_streamplot(plt)
    assert lats[:, 0].tolist() == pytest.approx(LAT[::-1])
    assert plotted_u.tolist() == pytest.approx(u[::-1, :])
    assert plotted_v.tolist() == pytest.approx(v[::-1, :])


def test_t01_mapas_flag3_desenham_primeiro_o_sul(tmp_path):
    data = grid_values(LAT, LON_CROSS)
    basemaps, _ = run_scalar_map(tmp_path, lat=LAT, lon=LON_CROSS, data=data)
    _, y, plotted, _ = _single_contourf(basemaps)
    assert y[:, 0].tolist() == pytest.approx(LAT[::-1])
    assert plotted[0, 0] == pytest.approx(data[2, 0] - 273.15)
    assert plotted[0, -1] == pytest.approx(data[2, -1] - 273.15)

    u = 5.0 + LAT[:, None] + np.zeros_like(LON_CROSS)
    v = np.zeros_like(u)
    # O ramo flag==3 reutiliza o índice do laço no título; com quatro GRIBs
    # (como no fluxo real de f000/f006/f012/f018) a execução é completa.
    _, plt = run_wind_map(
        tmp_path, lat=LAT, lon=LON_CROSS, u=u, v=v, replicas=4
    )
    assert len(plt.streamplot_calls) == 4
    _, lats, plotted_u, _ = plt.streamplot_calls[-1]
    assert lats[:, 0].tolist() == pytest.approx(LAT[::-1])
    assert plotted_u[0, 0] == pytest.approx(u[2, 0])
    assert plotted_u[0, -1] == pytest.approx(u[2, -1])


# ---------------------------------------------------------------------------
# T-02 — componentes U/V
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("runner", ["bluesky", "predi", "man_bluesky", "man_predi"])
def test_t02_u_puro_preserva_componente_v_zero(tmp_path, runner):
    u = np.full((LAT.size, LON.size), 10.0)
    v = np.zeros_like(u)
    if runner == "bluesky":
        rows = _rows(run_bluesky_matrix(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[4]) for row in rows[1:]] == pytest.approx([19.43] * 12)
    elif runner == "predi":
        rows = _rows(run_predi_matrix(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[2]) for row in rows[1:]] == pytest.approx([10.0] * 12)
        assert [float(row[3]) for row in rows[1:]] == pytest.approx([0.0] * 12)
    elif runner == "man_bluesky":
        rows = _rows(run_man_bluesky(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[4]) for row in rows[1:]] == pytest.approx([19.43] * 12)
    else:
        rows = _rows(run_man_predi(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[2]) for row in rows[1:]] == pytest.approx([10.0] * 12)
        assert [float(row[3]) for row in rows[1:]] == pytest.approx([0.0] * 12)


@pytest.mark.parametrize("runner", ["bluesky", "predi", "man_bluesky", "man_predi"])
def test_t02_vento_diagonal_preserva_componentes_e_resultante(tmp_path, runner):
    u = np.full((LAT.size, LON.size), 3.0)
    v = np.full((LAT.size, LON.size), 4.0)
    if runner == "bluesky":
        rows = _rows(run_bluesky_matrix(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[4]) for row in rows[1:]] == pytest.approx([5.0 * 1.943] * 12)
        assert [float(row[3]) for row in rows[1:]] == pytest.approx([216.8698976] * 12)
    elif runner == "predi":
        rows = _rows(run_predi_matrix(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[2]) for row in rows[1:]] == pytest.approx([3.0] * 12)
        assert [float(row[3]) for row in rows[1:]] == pytest.approx([4.0] * 12)
    elif runner == "man_bluesky":
        rows = _rows(run_man_bluesky(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[4]) for row in rows[1:]] == pytest.approx([5.0 * 1.943] * 12)
        assert [float(row[3]) for row in rows[1:]] == pytest.approx([216.8698976] * 12)
    else:
        rows = _rows(run_man_predi(tmp_path, lat=LAT, lon=LON, u=u, v=v))
        assert [float(row[2]) for row in rows[1:]] == pytest.approx([3.0] * 12)
        assert [float(row[3]) for row in rows[1:]] == pytest.approx([4.0] * 12)


def test_t02_preditor_aut_20m_nao_recebe_u_no_lugar_de_v():
    """Regressão estrutural direta de D-02 no fluxo automático."""

    source = (CLASSES / "gera_matriz_vento_MET.py").read_text(encoding="utf-8")
    assert (
        "geraMatriz_Vento_UVT_predi(u_comp_supe, v_comp_supe, t_comp_supe"
        in source
    )


def test_t02_mapa_aut_superficial_le_v_supe():
    """Regressão estrutural direta de D-02 no mapa superficial automático."""

    source = (CLASSES / "gera_mapas_vento_MET.py").read_text(encoding="utf-8")
    assert (
        'v_comp=processamento_dados_met_AUT("vSupe", nivelQuaseSupe)'
        in source
    )


# ---------------------------------------------------------------------------
# T-03 — altura do vento
# ---------------------------------------------------------------------------

HIERARCHY = [(20, 65.6168), (30, 98.4252), (40, 131.2336), (50, 164.0420), (80, 262.4672)]


@pytest.mark.parametrize("height_m,expected_ft", HIERARCHY)
def test_t03_altura_em_metros_usa_conversao_linear(tmp_path, height_m, expected_ft):
    for runner in (run_bluesky_matrix, run_man_bluesky):
        directory = tmp_path / runner.__name__
        directory.mkdir(parents=True, exist_ok=True)
        rows = _rows(runner(directory, level=height_m))
        assert [float(row[2]) for row in rows[1:]] == pytest.approx([expected_ft] * 12)


def test_t03_500_hpa_permanece_com_formula_barometrica(tmp_path):
    expected = 18281.18084128231
    for runner in (run_bluesky_matrix, run_man_bluesky):
        directory = tmp_path / runner.__name__
        directory.mkdir(parents=True, exist_ok=True)
        rows = _rows(runner(directory, level=500, eh_vento_superficie=False))
        assert [float(row[2]) for row in rows[1:]] == pytest.approx([expected] * 12)


def test_t03_100_hpa_nao_e_confundido_com_altitude(tmp_path):
    expected = 51805.97785610506
    rows = _rows(run_bluesky_matrix(tmp_path, level=100, eh_vento_superficie=False))
    values = [float(row[2]) for row in rows[1:]]
    assert values == pytest.approx([expected] * 12)
    assert all(value > 50_000.0 for value in values)


def test_t03_850_hpa_permanece_com_formula_barometrica(tmp_path):
    expected = 4779.1936018229135
    for runner in (run_bluesky_matrix, run_man_bluesky):
        directory = tmp_path / runner.__name__
        directory.mkdir(parents=True, exist_ok=True)
        rows = _rows(runner(directory, level=850, eh_vento_superficie=False))
        assert [float(row[2]) for row in rows[1:]] == pytest.approx([expected] * 12)


def test_t03_fluxos_passam_a_flag_explicita_de_vento_superficial():
    automatico = (CLASSES / "gera_matriz_vento_MET.py").read_text(encoding="utf-8")
    manual = (CLASSES / "gera_matriz_vento_MAN_MET.py").read_text(encoding="utf-8")

    assert (
        "geraMatriz_Vento_Resu(u_comp_supe, v_comp_supe, lon_lat, varReg, varNivel_sup, True)"
        in automatico
    )
    assert (
        "geraMatriz_Vento_Resu(u_comp, v_comp, lonslats, varRegiaoNome, varNivel, False)"
        in automatico
    )
    assert "self.gera_matriz_vento_bluesky(" in manual
    assert "nivelVento, self.saida, True)" in manual
    assert "self.nivel, self.saida, False)" in manual
    for source in (automatico, manual):
        assert "if pres in (20, 30, 40, 50, 80)" not in source


# ---------------------------------------------------------------------------
# T-04 — ângulo do vento em [0, 360)
# ---------------------------------------------------------------------------


ANGLES = [
    (0.0, -10.0, 0.0),
    (-10.0, 0.0, 90.0),
    (0.0, 10.0, 180.0),
    (10.0, 0.0, 270.0),
    (-10.0, -10.0, 45.0),
    (-10.0, 10.0, 135.0),
    (10.0, 10.0, 225.0),
    (10.0, -10.0, 315.0),
]


@pytest.mark.parametrize("u,v,expected", ANGLES)
def test_t04_quatro_quadrantes_aut(tmp_path, u, v, expected):
    u_grid = np.full((LAT.size, LON.size), u)
    v_grid = np.full((LAT.size, LON.size), v)
    rows = _rows(run_bluesky_matrix(tmp_path, lat=LAT, lon=LON, u=u_grid, v=v_grid))
    angles = [float(row[3]) for row in rows[1:]]
    assert angles == pytest.approx([expected] * 12, abs=1e-9)
    assert all(0.0 <= angle < 360.0 for angle in angles)


@pytest.mark.parametrize("u,v,expected", ANGLES)
def test_t04_quatro_quadrantes_man(tmp_path, u, v, expected):
    u_grid = np.full((LAT.size, LON.size), u)
    v_grid = np.full((LAT.size, LON.size), v)
    rows = _rows(run_man_bluesky(tmp_path, lat=LAT, lon=LON, u=u_grid, v=v_grid))
    angles = [float(row[3]) for row in rows[1:]]
    assert angles == pytest.approx([expected] * 12, abs=1e-9)
    assert all(0.0 <= angle < 360.0 for angle in angles)


def test_t04_angulos_em_toda_a_grade_ficam_no_intervalo(tmp_path):
    lat = np.linspace(10.0, -10.0, 11)
    lon = np.linspace(-60.0, -30.0, 13)
    rng = np.random.default_rng(20261027)
    u = rng.normal(size=(lat.size, lon.size))
    v = rng.normal(size=(lat.size, lon.size))
    rows = _rows(run_bluesky_matrix(tmp_path, lat=lat, lon=lon, u=u, v=v))
    angles = [float(row[3]) for row in rows[1:]]
    assert len(angles) == lat.size * lon.size
    assert all(0.0 <= angle < 360.0 for angle in angles)


# ---------------------------------------------------------------------------
# T-05 — seleção de ciclo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hour,minute,expected",
    [
        (0, 0, "00"),
        (5, 59, "00"),
        (6, 0, "06"),
        (6, 59, "06"),
        (7, 0, "06"),
        (11, 59, "06"),
        (12, 0, "12"),
        (17, 59, "12"),
        (18, 0, "18"),
        (23, 59, "18"),
    ],
)
def test_t05_fronteiras_de_ciclo(tmp_path, hour, minute, expected):
    opened = run_reader_at(tmp_path, (2026, 10, 23, hour, minute))
    assert len(opened) == 4, opened
    assert all(path.is_absolute() for path in opened), opened
    assert all(path.parent.parent.name == "20261023" for path in opened), opened
    assert all(path.parent.name == expected for path in opened), opened


def test_t05_meia_noite_nao_usa_o_18_do_dia_anterior(tmp_path):
    opened = run_reader_at(tmp_path, (2026, 10, 23, 0, 0))
    assert all(path.parent.parent.name == "20261023" for path in opened), opened
    assert all(path.parent.name == "00" for path in opened), opened


def test_t05_ciclo_ausente_falha_com_arquivo_nao_encontrado(tmp_path):
    with pytest.raises(FileNotFoundError, match="06"):
        run_reader_at(tmp_path, (2026, 10, 23, 6, 30), cycles=("00",))


@pytest.mark.parametrize("resolution", ["0p50", "1p00"])
def test_t05_fallback_de_resolucao(tmp_path, resolution):
    opened = run_reader_at(
        tmp_path, (2026, 10, 23, 7, 30), resolutions=(resolution,)
    )
    assert len(opened) == 4, opened
    assert all(f".{resolution}." in path.name for path in opened), opened
