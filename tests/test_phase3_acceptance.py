"""Regressões da auditoria e T-13 a T-15, sem escrita em /media/MET."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
import pytest

from phase0_harness import (CLASSES, FakeDirSave, FakeGRIB, FixedTime,
    load_definitions, run_wind_map, read_csv)
from runtime_MET import atomic_path, atomic_text, product_operation, validate_wind, close_sources

ROOT = CLASSES.parent

def test_missing_day_is_error(tmp_path):
    ns = load_definitions(CLASSES / "leitura_dados_grib_MET.py", ["leitura_dados_gribs_AUT"],
        {"dir_save": FakeDirSave(tmp_path), "time": FixedTime(2026, 10, 22, 1)})
    with pytest.raises(FileNotFoundError):
        ns["leitura_dados_gribs_AUT"]().imprime_lista_obj_gribs_AUT()

def test_decimal_point_and_bounds():
    from parse_param_MET import parse_param
    from ponto_regiao_MET import met_ponto_regiao
    result = parse_param(["p", "-v", "temp", "-n", "850", "-ll", "-46.63", "-23.55"]).imprime_parse()
    assert result[2] == ("-46.63", "-23.55")
    assert met_ponto_regiao(-46.63, -23.55).verifica_longitude() == (-51.63, -41.63)
    assert met_ponto_regiao(179, 89).imprime_longitude_latitude() == [(174, 180), (80, 90)]
    for lon, lat in [(181, 0), (0, 91), (float("nan"), 0)]:
        with pytest.raises(ValueError): met_ponto_regiao(lon, lat)

def test_greenwich_more_rows_than_forecasts(tmp_path):
    _, plot = run_wind_map(tmp_path, lat=np.linspace(2, -2, 9),
        lon=np.array([-2., -1., 0., 1., 2.]), replicas=4)
    assert len(plot.saved) == 4

def message(ft=0, level=850, lon=(-2., -1.)):
    return FakeGRIB(np.ones((2, 2)), [1., 0.], lon, forecastTime=ft, level=level)

@pytest.mark.parametrize("groups", [
    ([message()], []), ([message()], [message(6)]),
    ([message()], [message(level=900)]),
    ([message()], [message(lon=(-3., -2.))]),
    ([message()], [message()], [message(6)])])
def test_mismatched_components_rejected(groups):
    with pytest.raises(ValueError): validate_wind(*groups)

def test_actual_level_in_filename(tmp_path):
    ns = load_definitions(CLASSES / "gera_matriz_MET.py", ["geraMatriz"],
        {"dir_save": FakeDirSave(tmp_path), "time": FixedTime(2026, 10, 22, 1)})
    ns["geraMatriz"]([message(level=900)], [[-2., -1.], [0., 1.]], "temp", "SP", 876)
    assert list(tmp_path.rglob("*N900*.csv"))
    assert not list(tmp_path.rglob("*N876*"))

def test_atomic_failure_keeps_previous_product(tmp_path):
    path = tmp_path / "data.csv"; path.write_text("previous")
    with pytest.raises(RuntimeError):
        with atomic_text(path) as stream:
            stream.write("partial")
            raise RuntimeError("interruption")
    assert path.read_text() == "previous"
    assert list(tmp_path.iterdir()) == [path]

def test_atomic_repeat_is_idempotent_and_permissions(tmp_path):
    path = tmp_path / "data.csv"
    for _ in range(2):
        with atomic_text(path) as stream: stream.write("lat,lon\n0,0\n")
    assert path.read_text().count("lat,lon") == 1
    assert path.stat().st_mode & 0o777 == 0o644

def test_concurrent_atomic_writers(tmp_path):
    path = tmp_path / "data.csv"
    script = """import sys,time
from runtime_MET import atomic_text
with atomic_text(sys.argv[1]) as f:
 f.write(sys.argv[2] * 1000);f.flush();time.sleep(.05);f.write(sys.argv[2] * 1000)
"""
    env = dict(os.environ, PYTHONPATH=str(CLASSES), PYTHONDONTWRITEBYTECODE="1")
    jobs = [subprocess.Popen([sys.executable, "-c", script, str(path), value], env=env) for value in ("a", "b")]
    assert all(job.wait(timeout=30) == 0 for job in jobs)
    assert path.read_text() in ("a" * 2000, "b" * 2000)

def test_figures_closed_on_exception():
    import matplotlib.pyplot as plt
    before = set(plt.get_fignums())
    font_before = plt.rcParams["font.size"]
    @product_operation
    def broken():
        plt.rcParams["font.size"] = 99
        plt.figure(); raise RuntimeError("draw failed")
    with pytest.raises(RuntimeError): broken()
    assert set(plt.get_fignums()) == before
    assert plt.rcParams["font.size"] == font_before

def test_sources_closed_on_selection_error():
    class Source:
        closed = False
        def close(self): self.closed = True
    source = Source()
    class Processor:
        obj_GRIBS = [source]
        @close_sources
        def select(self): raise ValueError("field absent")
    with pytest.raises(ValueError): Processor().select()
    assert source.closed

def test_safe_region(tmp_path):
    @product_operation
    def operation(regiao): pass
    with pytest.raises(ValueError): operation("../escape")

def test_config_independent_of_cwd(tmp_path, monkeypatch):
    from controla_env import controla_dirs_MET
    config = tmp_path / "path.conf"
    keys = ("dir_gribs", "dir_mapas", "dir_matrizes", "dir_matrizes_predi", "dir_matrizes_bluesky")
    config.write_text("\n".join(k + "=" + str(tmp_path / k) for k in keys))
    monkeypatch.setenv("MET_PATH_CONF", str(config)); monkeypatch.chdir(tmp_path)
    before = Path.cwd(); dirs = controla_dirs_MET()
    for method in (dirs.imprime_dirMapas, dirs.imprime_dirMatrizes, dirs.imprime_dirMatrizesPredi, dirs.imprime_dirMatrizesBluesky):
        assert Path(method()).is_dir(); assert Path.cwd() == before

def test_controller_stops_on_error_and_success_exit(tmp_path):
    tmp_path = tmp_path / "work tree"
    tmp_path.mkdir()
    (tmp_path / "bash").mkdir()
    script = tmp_path / "bash/automatizacao_controle_MET.sh"
    script.write_text((ROOT / "bash/automatizacao_controle_MET.sh").read_text())
    for name in ("automatiza_MET.sh", "automatiza_vento_MET.sh"):
        wrapper = tmp_path / "bash" / name
        wrapper.write_text('#!/bin/bash\nexit "${TEST_EXIT:-0}"\n'); wrapper.chmod(0o755)
    for code in (0, 9):
        env = dict(os.environ, TEST_EXIT=str(code), MET_LOCK_DIR=str(tmp_path / "locks"))
        assert subprocess.run(["bash", str(script)], env=env).returncode == code

def test_metar_atomic_failure(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "METARpy"))
    import metar_common
    path = tmp_path / "metar.json"; path.write_text('{"old": true}')
    def fail(*args): raise OSError("replace failed")
    monkeypatch.setattr(metar_common.os, "replace", fail)
    with pytest.raises(OSError): metar_common.grava_json_atomico(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}
    assert list(tmp_path.iterdir()) == [path]


def test_cleanup_refuses_active_product_lock(tmp_path):
    import fcntl
    lock_dir = tmp_path / "locks"; lock_dir.mkdir()
    with (lock_dir / "products.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        env = dict(os.environ, MET_LOCK_DIR=str(lock_dir), MET_BASE_DIR=str(tmp_path), MET_HOJE="20260315")
        result = subprocess.run(["bash", str(ROOT / "remove_GRIBS_antigos.sh")], env=env, capture_output=True)
        assert result.returncode == 75

def test_nearest_level_order_and_source_close():
    ns = load_definitions(CLASSES / "processamento_dados_MET.py", ["processamento_dados_met_AUT"])
    class Source:
        closed = False
        def select(self, **kwargs):
            return [SimpleNamespace(level=n) for n in (1000, 850, 900) if "level" not in kwargs or n == kwargs["level"]]
        def close(self): self.closed = True
    source = Source()
    processor = ns["processamento_dados_met_AUT"].__new__(ns["processamento_dados_met_AUT"])
    processor.obj_GRIBS = [source]; processor.varMET = "temp"
    processor.varMET_dict = "Temperature"; processor.tipo_nivel_dict = "isobaricInhPa"; processor.nivel = 875
    assert processor.define_lista_var_com_nivel_pressao()[0].level == 900
    assert source.closed

def test_real_png_export_is_atomic_and_closes(tmp_path):
    import matplotlib.pyplot as plt
    from runtime_MET import save_figure
    before = set(plt.get_fignums())
    @product_operation
    def draw():
        plt.figure(); plt.plot([0, 1], [0, 1]); save_figure(tmp_path / "map.png")
    draw()
    assert (tmp_path / "map.png").read_bytes().startswith(b"\x89PNG")
    assert set(plt.get_fignums()) == before
    assert len(list(tmp_path.iterdir())) == 1


def test_partial_reader_closes_open_sources(tmp_path):
    directory = tmp_path / "gribs/20261022/00"; directory.mkdir(parents=True)
    class Source:
        closed = False
        def close(self): self.closed = True
    source = Source()
    class Reader:
        calls = 0
        def open(self, name):
            self.calls += 1
            if self.calls == 1: return source
            raise OSError("missing")
    ns = load_definitions(CLASSES / "leitura_dados_grib_MET.py", ["leitura_dados_gribs_AUT"],
        {"dir_save": FakeDirSave(tmp_path), "time": FixedTime(2026, 10, 22, 1), "pygrib": Reader()})
    with pytest.raises(FileNotFoundError): ns["leitura_dados_gribs_AUT"]().imprime_lista_obj_gribs_AUT()
    assert source.closed

def test_cycle_label_uses_source_metadata(tmp_path):
    ns = load_definitions(CLASSES / "gera_matriz_MET.py", ["geraMatriz"],
        {"dir_save": FakeDirSave(tmp_path), "time": FixedTime(2026, 10, 22, 1)})
    field = message(); field.dataTime = 600
    ns["geraMatriz"]([field], [[-2., -1.], [0., 1.]], "temp", "SP", 850)
    assert list(tmp_path.rglob("*_temp_06_*.csv"))
