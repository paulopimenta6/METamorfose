#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes da seleção de ciclo/data do leitor automático (D-04/C-05)."""

from pathlib import Path

import pytest

from phase0_harness import run_reader_at


def _relative_to_gribs(paths, tmp_path):
    gribs = (tmp_path / "gribs").resolve()
    return [path.resolve().relative_to(gribs).as_posix() for path in paths]


def test_ciclo_0730_usa_o_ciclo_06_do_mesmo_dia(tmp_path):
    opened = run_reader_at(tmp_path, (2026, 10, 23, 7, 30))
    relative = _relative_to_gribs(opened, tmp_path)
    assert relative, "o leitor não abriu nenhum GRIB"
    assert all(path.startswith("20261023/06/") for path in relative), relative


def test_ciclo_0630_deve_escolher_o_ciclo_06(tmp_path):
    opened = run_reader_at(tmp_path, (2026, 10, 23, 6, 30))
    relative = _relative_to_gribs(opened, tmp_path)
    assert relative, "o leitor não abriu nenhum GRIB"
    assert all(path.startswith("20261023/06/") for path in relative), relative


def test_ciclo_0030_usa_o_ciclo_00_do_mesmo_dia(tmp_path):
    opened = run_reader_at(tmp_path, (2026, 10, 23, 0, 30))
    relative = _relative_to_gribs(opened, tmp_path)
    assert relative, "o leitor não abriu nenhum GRIB"
    assert all(path.startswith("20261023/00/") for path in relative), relative
