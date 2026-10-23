#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harness da Fase 0 para exercitar o código atual sem importar módulos com efeitos colaterais.

O código de produção executa `parse_param(sys.argv)` e `controla_dirs_MET()` no
momento do import. Para testar as funções reais sem depender de `/media/MET` e
sem alterar o código, este harness extrai as funções/classes diretamente da AST
e as executa em um namespace controlado.
"""

from __future__ import annotations

import ast
import csv
import math
import os
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ROOT / "classes_MET"


class DummyBasemap:
    """Substitui Basemap nos testes; as funções testadas não usam o mapa."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class FakeDirSave:
    """Implementa apenas os métodos de controla_dirs_MET usados pelos geradores."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _dir(self, name: str) -> str:
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return str(path) + "/"

    def imprime_dirGrib(self) -> str:
        return self._dir("gribs")

    def imprime_dirMapas(self) -> str:
        return self._dir("mapasGrib")

    def imprime_dirMatrizes(self) -> str:
        return self._dir("matrizGrib")

    def imprime_dirMatrizesPredi(self) -> str:
        return self._dir("matrizGrib/predi")

    def imprime_dirMatrizesBluesky(self) -> str:
        return self._dir("matrizGrib/bluesky")


class FixedTime:
    """Fornece uma hora local fixa para as funções que usam time.localtime()."""

    def __init__(self, year: int, month: int, day: int, hour: int, minute: int = 0):
        self.value = time.struct_time((year, month, day, hour, minute, 0, 0, 0, -1))

    def localtime(self, *args, **kwargs):
        return self.value


class FakeGRIB:
    """Imita o subconjunto da API pygrib usado pelos geradores de matrizes."""

    def __init__(
        self,
        data,
        lat,
        lon,
        *,
        dataDate: int = 20261022,
        forecastTime: int = 0,
        iDirectionIncrementInDegrees: float = 0.25,
        name: str = "Temperature",
        typeOfLevel: str = "isobaricInhPa",
        level: int = 850,
    ):
        self._data = np.asarray(data, dtype=float)
        self._lat = np.asarray(lat, dtype=float).reshape(-1)
        self._lon = np.asarray(lon, dtype=float).reshape(-1)
        self.dataDate = dataDate
        self.forecastTime = forecastTime
        self.iDirectionIncrementInDegrees = iDirectionIncrementInDegrees
        self.name = name
        self.typeOfLevel = typeOfLevel
        self.level = level

    def data(self, lat1=None, lat2=None, lon1=None, lon2=None):
        lat_mask = np.ones(self._lat.shape, dtype=bool)
        lon_mask = np.ones(self._lon.shape, dtype=bool)
        lon_shift = 0.0

        if lat1 is not None and lat2 is not None:
            lo, hi = sorted((float(lat1), float(lat2)))
            lat_mask = (self._lat >= lo) & (self._lat <= hi)
        if lon1 is not None and lon2 is not None:
            lo, hi = sorted((float(lon1), float(lon2)))
            # pygrib/GFS pode trabalhar com 0..360; o código converte de volta
            # para -180..180 depois de ler. Emulamos esse comportamento.
            if lo > 180.0 and hi > 180.0:
                lo -= 360.0
                hi -= 360.0
                lon_shift = 360.0
            lon_mask = (self._lon >= lo) & (self._lon <= hi)

        lat = self._lat[lat_mask]
        lon = self._lon[lon_mask] + lon_shift
        if lat.size == 0 or lon.size == 0:
            raise ValueError("subconjunto vazio no FakeGRIB")

        rows = np.where(lat_mask)[0]
        cols = np.where(lon_mask)[0]
        data = self._data[np.ix_(rows, cols)]
        lons, lats = np.meshgrid(lon, lat)
        return data, lats, lons


class FakePygrib:
    """Registra os arquivos abertos e falha como pygrib.open em arquivo ausente."""

    def __init__(self):
        self.opened: list[Path] = []

    def open(self, filename):
        path = Path(os.path.abspath(filename))
        self.opened.append(path)
        if not path.exists():
            raise OSError(f"arquivo GRIB simulado ausente: {path}")
        return path


def _extract_nodes(source: Path, names):
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            selected.append(node)
    found = {node.name for node in selected}
    missing = set(names) - found
    if missing:
        raise ValueError(f"definições não encontradas em {source}: {sorted(missing)}")
    return selected


def load_definitions(source: Path, names, extra_globals=None):
    """Executa somente as definições pedidas, sem o código de topo do módulo."""

    namespace = {
        "np": np,
        "math": math,
        "csv": csv,
        "os": os,
        "time": time,
        "Basemap": DummyBasemap,
    }
    if extra_globals:
        namespace.update(extra_globals)

    module = ast.Module(body=_extract_nodes(source, names), type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(source), "exec"), namespace)
    return namespace


def grid_values(lat, lon):
    """Valores determinísticos que permitem detectar troca de linhas/colunas."""

    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    return lat[:, None] * 100.0 + lon[None, :]


def read_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def find_one_csv(directory: Path, pattern: str = "*.csv") -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise AssertionError(f"esperava 1 CSV em {directory}, encontrei {len(matches)}: {matches}")
    return matches[0]


def run_scalar_matrix(
    tmp_path: Path,
    *,
    variable: str = "temp",
    level=850,
    lat=None,
    lon=None,
    data=None,
    when=(2026, 10, 22, 1, 0),
):
    lat = np.array([10.0, 0.0, -10.0]) if lat is None else np.asarray(lat, dtype=float)
    lon = np.array([-60.0, -50.0, -40.0, -30.0]) if lon is None else np.asarray(lon, dtype=float)
    data = grid_values(lat, lon) if data is None else np.asarray(data, dtype=float)

    ns = load_definitions(
        CLASSES / "gera_matriz_MET.py",
        ["geraMatriz"],
        {
            "dir_save": FakeDirSave(tmp_path),
            "time": FixedTime(*when),
        },
    )
    fake = FakeGRIB(data, lat, lon, name="Temperature", typeOfLevel="isobaricInhPa", level=level)
    ns["geraMatriz"](
        [fake],
        [[float(lon[0]), float(lon[-1])], [float(lat[0]), float(lat[-1])]],
        variable,
        "SP",
        level,
    )
    return find_one_csv(tmp_path / "matrizGrib")


def run_bluesky_matrix(
    tmp_path: Path,
    *,
    level=20,
    lat=None,
    lon=None,
    u=None,
    v=None,
    when=(2026, 10, 22, 1, 0),
):
    lat = np.array([10.0, 0.0, -10.0]) if lat is None else np.asarray(lat, dtype=float)
    lon = np.array([-60.0, -50.0, -40.0, -30.0]) if lon is None else np.asarray(lon, dtype=float)
    u = np.full((lat.size, lon.size), 10.0) if u is None else np.asarray(u, dtype=float)
    v = np.zeros((lat.size, lon.size)) if v is None else np.asarray(v, dtype=float)

    ns = load_definitions(
        CLASSES / "gera_matriz_vento_MET.py",
        [
            "criaResultante",
            "criaResultanteKnot",
            "criaAngAzMET",
            "criaAngMET",
            "converte_altitude",
            "geraMatriz_Vento_Resu",
        ],
        {
            "dir_save": FakeDirSave(tmp_path),
            "time": FixedTime(*when),
        },
    )
    u_fake = FakeGRIB(u, lat, lon, name="U component of wind", typeOfLevel="heightAboveGround", level=level)
    v_fake = FakeGRIB(v, lat, lon, name="V component of wind", typeOfLevel="heightAboveGround", level=level)
    ns["geraMatriz_Vento_Resu"](
        [u_fake],
        [v_fake],
        [[float(lon[0]), float(lon[-1])], [float(lat[0]), float(lat[-1])]],
        "SP",
        level,
    )
    return find_one_csv(tmp_path / "matrizGrib" / "bluesky")


def run_predi_matrix(
    tmp_path: Path,
    *,
    level=20,
    lat=None,
    lon=None,
    u=None,
    v=None,
    t=None,
    when=(2026, 10, 22, 1, 0),
):
    lat = np.array([10.0, 0.0, -10.0]) if lat is None else np.asarray(lat, dtype=float)
    lon = np.array([-60.0, -50.0, -40.0, -30.0]) if lon is None else np.asarray(lon, dtype=float)
    u = np.full((lat.size, lon.size), 10.0) if u is None else np.asarray(u, dtype=float)
    v = np.zeros((lat.size, lon.size)) if v is None else np.asarray(v, dtype=float)
    t = np.full((lat.size, lon.size), 280.0) if t is None else np.asarray(t, dtype=float)

    ns = load_definitions(
        CLASSES / "gera_matriz_vento_MET.py",
        [
            "criaResultante",
            "criaResultanteKnot",
            "criaAngAzMET",
            "criaAngMET",
            "converte_altitude",
            "geraMatriz_Vento_UVT_predi",
        ],
        {
            "dir_save": FakeDirSave(tmp_path),
            "time": FixedTime(*when),
        },
    )
    u_fake = FakeGRIB(u, lat, lon, name="U component of wind", typeOfLevel="heightAboveGround", level=level)
    v_fake = FakeGRIB(v, lat, lon, name="V component of wind", typeOfLevel="heightAboveGround", level=level)
    t_fake = FakeGRIB(t, lat, lon, name="Temperature", typeOfLevel="surface", level=0)
    ns["geraMatriz_Vento_UVT_predi"](
        [u_fake],
        [v_fake],
        [t_fake],
        [[float(lon[0]), float(lon[-1])], [float(lat[0]), float(lat[-1])]],
        "SP",
        level,
    )
    return find_one_csv(tmp_path / "matrizGrib" / "predi")


def run_man_bluesky(
    tmp_path: Path,
    *,
    level=20,
    lat=None,
    lon=None,
    u=None,
    v=None,
):
    lat = np.array([10.0, 0.0, -10.0]) if lat is None else np.asarray(lat, dtype=float)
    lon = np.array([-60.0, -50.0, -40.0, -30.0]) if lon is None else np.asarray(lon, dtype=float)
    u = np.full((lat.size, lon.size), 10.0) if u is None else np.asarray(u, dtype=float)
    v = np.zeros((lat.size, lon.size)) if v is None else np.asarray(v, dtype=float)

    ns = load_definitions(
        CLASSES / "gera_matriz_vento_MAN_MET.py",
        ["met_gera_matriz_vento_man"],
    )
    obj = ns["met_gera_matriz_vento_man"](
        "wind",
        float(lon.min()),
        float(lon.max()),
        float(lat.min()),
        float(lat.max()),
        2026,
        10,
        22,
        "00",
        "00",
        str(tmp_path) + "/",
        level,
    )
    u_fake = FakeGRIB(u, lat, lon, name="U component of wind", typeOfLevel="heightAboveGround", level=level)
    v_fake = FakeGRIB(v, lat, lon, name="V component of wind", typeOfLevel="heightAboveGround", level=level)
    obj.gera_matriz_vento_bluesky(
        u_fake,
        v_fake,
        float(lon.min()),
        float(lon.max()),
        float(lat.min()),
        float(lat.max()),
        "00",
        "00",
        "SP",
        level,
        str(tmp_path) + "/",
    )
    return find_one_csv(tmp_path, "matriz_vento_bluesky_*.csv")


def run_reader_at(tmp_path: Path, when):
    """Executa leitura_dados_gribs_AUT com uma hora fixa e GRIBs simulados."""

    gribs = tmp_path / "gribs"
    for date, cycle in (("20261023", "00"), ("20261023", "06"), ("20261022", "18")):
        directory = gribs / date / cycle
        directory.mkdir(parents=True, exist_ok=True)
        for forecast in ("00", "06", "12", "18"):
            (directory / f"gfs.t{cycle}z.pgrb2.0p25.f0{forecast}").write_bytes(b"")

    fake_pygrib = FakePygrib()
    ns = load_definitions(
        CLASSES / "leitura_dados_grib_MET.py",
        ["leitura_dados_gribs_AUT"],
        {
            "dir_save": FakeDirSave(tmp_path),
            "pygrib": fake_pygrib,
            "time": FixedTime(*when),
        },
    )

    previous = Path.cwd()
    try:
        reader = ns["leitura_dados_gribs_AUT"]()
        reader.imprime_lista_obj_gribs_AUT()
    finally:
        os.chdir(previous)

    return fake_pygrib.opened
