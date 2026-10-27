#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes das funções puras de vento e altitude (comportamento atual)."""

import numpy as np
import pytest

from phase0_harness import CLASSES, load_definitions

NS = load_definitions(
    CLASSES / "gera_matriz_vento_MET.py",
    [
        "criaResultante",
        "criaResultanteKnot",
        "criaAngAzMET",
        "criaAngMET",
        "converte_altitude",
        "calcula_hmet",
    ],
)


def test_resultante_em_metros_por_segundo():
    result = NS["criaResultante"](np.array([3.0]), np.array([4.0]))
    assert result.tolist() == [5.0]


def test_resultante_em_nos():
    result = NS["criaResultanteKnot"](np.array([3.0]), np.array([4.0]))
    assert result.tolist() == pytest.approx([5.0 * 1.943])


@pytest.mark.parametrize(
    "u,v,expected",
    [
        (0.0, -10.0, 0.0),    # vento de norte
        (-10.0, 0.0, 90.0),   # vento de leste
        (-10.0, -10.0, 45.0), # vento de nordeste
        (-10.0, 10.0, 135.0), # vento de sudeste
    ],
)
def test_angmet_quadrantes_nao_negativos(u, v, expected):
    angle = NS["criaAngMET"](np.array([u]), np.array([v]))
    assert angle.tolist() == pytest.approx([expected])


@pytest.mark.parametrize(
    "u,v,expected",
    [
        (10.0, 0.0, 270.0),   # vento de oeste
        (10.0, 10.0, 225.0),  # vento de sudoeste
        (10.0, -10.0, 315.0), # vento de noroeste
        (0.0, 10.0, 180.0),   # vento de sul: atan2 devolve -180
    ],
)
def test_angmet_quadrantes_negativos_devem_ser_normalizados(u, v, expected):
    angle = NS["criaAngMET"](np.array([u]), np.array([v]))
    assert angle.tolist() == pytest.approx([expected])


def test_altitude_de_pressao_500_hpa():
    altitude = NS["converte_altitude"](500)
    assert altitude == pytest.approx(18281.18, abs=0.1)


@pytest.mark.parametrize(
    "height_m,expected_ft",
    [
        (20, 65.6168),
        (30, 98.4252),
        (40, 131.2336),
        (50, 164.0420),
        (80, 262.4672),
    ],
)
def test_altura_em_metros_deveria_ser_convertida_por_3_28084(height_m, expected_ft):
    altitude = NS["calcula_hmet"](height_m, True)
    assert altitude == pytest.approx(expected_ft, abs=0.01)


def test_altura_de_pressao_500_hpa_usa_formula_barometrica():
    altitude = NS["calcula_hmet"](500, False)
    assert altitude == pytest.approx(18281.18, abs=0.1)
