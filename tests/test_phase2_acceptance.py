#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aceitação da Fase 2: T-06 a T-12.

Os testes de produto reutilizam o harness da Fase 0/1 para exercitar o código
real sem depender de /media/MET. Os testes de CLI usam um `python3` falso no
PATH para registrar os argumentos que os wrappers entregariam aos geradores.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from phase0_harness import (
    CLASSES,
    load_definitions,
    read_csv,
    run_man_bluesky,
    run_man_predi,
    run_man_wind_map,
    run_scalar_map,
)

ROOT = Path(__file__).resolve().parents[1]
BASH = ROOT / "bash"
METAR_DIR = ROOT / "METARpy"

pytestmark = pytest.mark.acceptance

NIVEIS_INTERVALO = [200, 250, 300, 350, 400, 450, 500]


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def _carrega_modulo(caminho: Path, nome: str):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _executa(script: Path, *args, env=None):
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )


@pytest.fixture
def fake_python(tmp_path):
    """Cria um python3 falso que registra os argumentos recebidos."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "python.log"
    executavel = bin_dir / "python3"
    executavel.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$*" >> "${FAKE_PYTHON_LOG}"\nexit 0\n',
        encoding="utf-8",
    )
    executavel.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = "%s:%s" % (bin_dir, env.get("PATH", ""))
    env["FAKE_PYTHON_LOG"] = str(log)
    return env, log


@pytest.fixture
def cli_man(monkeypatch):
    """Importa o CLI MAN e restaura o diretório de trabalho ao final."""

    modulo = _carrega_modulo(CLASSES / "executa_reqs_param.py", "executa_reqs_param_teste")
    monkeypatch.syspath_prepend(str(CLASSES))
    anterior = os.getcwd()
    yield modulo
    os.chdir(anterior)


def _argumentos_man(tmp_path):
    return [
        "-lonmin",
        "-56",
        "-lonmax",
        "-42",
        "-latmin",
        "-28",
        "-latmax",
        "-18",
        "-datetime",
        "202111020006",
        "-out",
        str(tmp_path),
    ]


class FakeMetar:
    def __init__(self, aerodromo="SBGR", data=("28", "23", "50")):
        self.aerodromo = aerodromo
        self.data = data

    def imprime_aerodromo(self):
        return self.aerodromo

    def imprime_metar(self):
        return "SBGR 282350Z 08003KT 9000 NSC 13/10 Q1023"

    def imprime_data(self):
        return self.data

    def imprime_vento_VEL(self):
        return 3

    def imprime_vento_RAJ(self):
        return "informacao ausente"

    def imprime_vento_DIR(self):
        return 80

    def imprime_vento_DIR_COOR(self):
        return "E"

    def imprime_vento_VAR(self):
        return "informacao ausente"

    def imprime_temp(self):
        return 13

    def imprime_tempPtoOrvalho(self):
        return 10

    def imprime_estAuto(self):
        return False

    def imprime_nuvem(self):
        return None

    def imprime_visi(self):
        return "9999"

    def imprime_PRES(self):
        return 1023


# ---------------------------------------------------------------------------
# T-06 — umidadeRel
# ---------------------------------------------------------------------------


def test_t06_valida_nivel_rejeita_umidade_rel_superficie_com_mensagem_clara():
    ns = load_definitions(
        CLASSES / "processamento_dados_MET.py", ["processamento_dados_met_AUT"]
    )
    classe = ns["processamento_dados_met_AUT"]

    with pytest.raises(ValueError, match="850"):
        classe._valida_nivel("umidadeRel", "isobaricInhPa", "surface")

    # Nível de pressão é aceito sem exceção.
    classe._valida_nivel("umidadeRel", "isobaricInhPa", 850)


def test_t06_cli_umidade_rel_850_executa_gerador(cli_man, tmp_path, monkeypatch):
    chamadas = []
    monkeypatch.setattr(cli_man, "_gera_escalar", lambda *args: chamadas.append(args))

    codigo = cli_man.main(
        ["-v", "umidadeRel", "-nhpa", "850"] + _argumentos_man(tmp_path)
    )

    assert codigo == 0
    assert len(chamadas) == 1
    variavel, coords, data, saida, modo, nivel = chamadas[0]
    assert variavel == "umidadeRel"
    assert coords == (-56.0, -42.0, -28.0, -18.0)
    assert data == ("2021", "11", "02", "00", "06")
    assert saida.endswith(os.sep)
    assert modo == "single"
    assert nivel == 850


def test_t06_cli_rejeita_umidade_rel_superficie(cli_man, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli_man.main(["-v", "umidadeRel", "-ns"] + _argumentos_man(tmp_path))

    assert exc.value.code == 2
    assert "850" in capsys.readouterr().err


def test_t06_wrapper_umidade_rel_850_entrega_os_dois_geradores(fake_python):
    env, log = fake_python
    resultado = _executa(
        BASH / "automatiza_MET.sh",
        "-v",
        "umidadeRel",
        "-n",
        "850",
        "-r",
        "SP",
        env=env,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "gera_mapas_MET.py -v umidadeRel -n 850 -r SP",
        "gera_matriz_MET.py -v umidadeRel -n 850 -r SP",
    ]


def test_t06_wrapper_rejeita_umidade_rel_superficie(fake_python):
    env, _ = fake_python
    resultado = _executa(
        BASH / "automatiza_MET.sh", "-v", "umidadeRel", "-ns", "-r", "SP", env=env
    )

    assert resultado.returncode == 2
    assert "850" in resultado.stderr


def test_t06_mapa_umidade_rel_850_nao_usa_rotulo_de_superficie(tmp_path):
    _, plt = run_scalar_map(tmp_path, variable="umidadeRel", level=850)

    assert plt.saved, "o mapa nao chamou savefig"
    nome = Path(plt.saved[-1][0][0]).name
    assert "_N850_umidadeRel_" in nome
    assert "Nsuperficie" not in nome


# ---------------------------------------------------------------------------
# T-07 — winds
# ---------------------------------------------------------------------------


def test_t07_controlador_ativa_winds_sem_bloco_noop():
    linhas = [
        linha.strip()
        for linha in (BASH / "automatizacao_controle_MET.sh")
        .read_text(encoding="utf-8")
        .splitlines()
        if "automatiza_vento_MET.sh" in linha
    ]

    winds = [linha for linha in linhas if '"winds" "-ns"' in linha]
    assert len(winds) == 2
    assert any('"-r" "SP"' in linha for linha in winds)
    assert any('"-r" "RJ"' in linha for linha in winds)

    # O bloco antigo sem -v era um no-op e foi removido.
    assert not any(
        linha.startswith('./automatiza_vento_MET.sh "-n"') for linha in linhas
    )

    # Chamadas de vento em pressão não estão duplicadas.
    assert sum('"wind" "-n" "1000"' in linha for linha in linhas) == 2
    assert sum('"wind" "-n" "200"' in linha for linha in linhas) == 2


def test_t07_wrapper_winds_executa_mapas_e_matrizes(fake_python):
    env, log = fake_python
    resultado = _executa(
        BASH / "automatiza_vento_MET.sh", "-v", "winds", "-ns", "-r", "SP", env=env
    )

    assert resultado.returncode == 0, resultado.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "gera_mapas_vento_MET.py -v winds -ns -r SP",
        "gera_matriz_vento_MET.py -v winds -ns -r SP",
    ]


def test_t07_produtos_de_vento_superficial_sao_gerados(tmp_path):
    lat = [10.0, 0.0, -10.0]
    lon = [-60.0, -50.0, -40.0, -30.0]
    import numpy as np

    u = 5.0 + np.asarray(lat)[:, None] + np.zeros((3, 4))
    v = np.zeros_like(u)

    _, plt = run_man_wind_map(tmp_path, level=20, lat=lat, lon=lon, u=u, v=v)
    assert len(plt.streamplot_calls) == 1

    bluesky = run_man_bluesky(tmp_path, level=20, lat=lat, lon=lon, u=u, v=v)
    predi = run_man_predi(tmp_path, level=20, lat=lat, lon=lon, u=u, v=v)

    assert bluesky.exists()
    assert predi.exists()
    assert "bluesky" in bluesky.name
    assert "predi" in predi.name
    assert read_csv(bluesky)[0] == [
        "lat",
        "lon",
        "hMET<feet>",
        "angMET<grau>",
        "vento_resultante<knot>",
    ]
    assert read_csv(predi)[0] == ["lat", "lon", "vento U", "vento V", "temperatura K"]
    assert len(read_csv(bluesky)) == 1 + 12
    assert len(read_csv(predi)) == 1 + 12


# ---------------------------------------------------------------------------
# T-08 — METAR: JSON válido, sem concatenação e rollover UTC
# ---------------------------------------------------------------------------


def test_t08_rollover_de_data_usa_utc_e_mes_anterior():
    metar = _carrega_modulo(METAR_DIR / "metar_common.py", "metar_common_teste")

    referencia = datetime(2026, 3, 1, 0, 10, tzinfo=timezone.utc)
    assert metar.data_diretorio_utc(referencia) == "20260301"
    assert metar.resolve_data_metar(("28", "23", "50"), referencia) == "202602282350"

    referencia = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)
    assert metar.resolve_data_metar(("31", "23", "50"), referencia) == "202512312350"

    referencia = datetime(2026, 3, 2, 0, 20, tzinfo=timezone.utc)
    assert metar.resolve_data_metar(("01", "00", "10"), referencia) == "202603010010"


def test_t08_referencia_vem_do_ambiente(monkeypatch):
    metar = _carrega_modulo(METAR_DIR / "metar_common.py", "metar_common_env")
    monkeypatch.setenv("METAR_REFERENCIA_UTC", "202603010010")

    assert metar.agora_utc() == datetime(2026, 3, 1, 0, 10, tzinfo=timezone.utc)


def test_t08_json_e_sobrescrito_sem_concatenar(tmp_path):
    metar = _carrega_modulo(METAR_DIR / "metar_common.py", "metar_common_json")
    referencia = datetime(2026, 3, 1, 0, 10, tzinfo=timezone.utc)

    def fabrica(aerodromo):
        return FakeMetar(aerodromo)

    def cria(sigla, data, cod, mensagem):
        return metar.cria_dict_metar_bruto(sigla, data, mensagem)

    for _ in range(2):
        codigo = metar.executa_estacoes(
            fabrica, cria, "", referencia, tmp_path
        )
        assert codigo == 0

    arquivos = sorted(tmp_path.glob("*.json"))
    assert len(arquivos) == len(metar.AERODROMOS)
    assert not list(tmp_path.glob("*.tmp"))

    caminho = tmp_path / "SBGR202602282350.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados == {
        "data": [
            {
                "id_localidade ": "SBGR",
                "data ": "202602282350",
                "mensagem_metar ": "SBGR 282350Z 08003KT 9000 NSC 13/10 Q1023",
            }
        ]
    }


def test_t08_script_metar_usa_referencia_unica_e_cria_diretorio(tmp_path, fake_python):
    env, log = fake_python
    env["METAR_BASE_DIR"] = str(tmp_path / "METARpy")
    env["METAR_REFERENCIA_UTC"] = "202603010010"

    resultado = _executa(METAR_DIR / "automatizaMetar.sh", env=env)

    assert resultado.returncode == 0, resultado.stderr
    assert (tmp_path / "METARpy" / "20260301").is_dir()
    assert log.read_text(encoding="utf-8").splitlines() == [
        "../METARpy.py",
        "../METARpy_traduzido.py",
    ]

    fonte = (METAR_DIR / "automatizaMetar.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in fonte
    assert "date -u +%Y%m%d%H%M" in fonte
    assert "export METAR_REFERENCIA_UTC" in fonte
    assert "data_hora" not in fonte
    assert "data_min" not in fonte


# ---------------------------------------------------------------------------
# T-09 — intervalo MAN
# ---------------------------------------------------------------------------


def test_t09_intervalo_aceita_as_duas_ordens_e_niveis_iguais(cli_man):
    assert cli_man.cria_intervalo_niveis(200, 500) == NIVEIS_INTERVALO
    assert cli_man.cria_intervalo_niveis(500, 200) == NIVEIS_INTERVALO
    assert cli_man.cria_intervalo_niveis(500, 500) == [500]


def test_t09_intervalo_invalido_falha_claramente(cli_man, tmp_path, capsys):
    for minimo, maximo in [(149, 500), (200, 1001), (-10, 300)]:
        with pytest.raises(SystemExit) as exc:
            cli_man.main(
                [
                    "-v",
                    "temp",
                    "-altminhpa",
                    str(minimo),
                    "-altmaxhpa",
                    str(maximo),
                ]
                + _argumentos_man(tmp_path)
            )
        assert exc.value.code == 2
        assert "fora da faixa" in capsys.readouterr().err


def test_t09_intervalo_executa_a_mesma_lista_nas_duas_ordens(
    cli_man, tmp_path, monkeypatch
):
    chamadas = []
    monkeypatch.setattr(cli_man, "_gera_escalar", lambda *args: chamadas.append(args))

    for ordem in [(200, 500), (500, 200)]:
        codigo = cli_man.main(
            [
                "-v",
                "temp",
                "-altminhpa",
                str(ordem[0]),
                "-altmaxhpa",
                str(ordem[1]),
            ]
            + _argumentos_man(tmp_path)
        )
        assert codigo == 0
        assert chamadas[-1][4] == "interval"
        assert chamadas[-1][5] == NIVEIS_INTERVALO


# ---------------------------------------------------------------------------
# T-10 — limpeza
# ---------------------------------------------------------------------------


def _cria_fixture_limpeza(base: Path, data_alvo: str):
    outra_data = "20250101"
    for data, arquivos in {
        data_alvo: [
            "00/gfs.t00z.pgrb2.0p25.f000",
            "00/gfs.t00z.pgrb2.1p00.f006",
            "00/gfs202602270000_000.grb",
            "06/gfs.t06z.pgrb2.0p25.f012",
            "06/outro.txt",
            "gfs202602270000_000.grb",
        ],
        outra_data: ["00/gfs.t00z.pgrb2.0p25.f000"],
    }.items():
        for arquivo in arquivos:
            caminho = base / "gribs" / data / arquivo
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text("x", encoding="utf-8")

    for diretorio in ["mapasGrib", "matrizGrib", "matrizGrib/bluesky", "matrizGrib/predi"]:
        for data in [data_alvo, outra_data]:
            caminho = base / diretorio / data / "produto.txt"
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text("x", encoding="utf-8")

    return data_alvo, outra_data


@pytest.mark.parametrize(
    "hoje,alvo",
    [
        ("20260301", "20260227"),
        ("20260302", "20260228"),
        ("20260315", "20260313"),
    ],
)
def test_t10_limpeza_remove_o_dia_correto(tmp_path, hoje, alvo):
    alvo, outra_data = _cria_fixture_limpeza(tmp_path, alvo)
    env = os.environ.copy()
    env["MET_BASE_DIR"] = str(tmp_path)
    env["MET_HOJE"] = hoje

    resultado = _executa(ROOT / "remove_GRIBS_antigos.sh", env=env)

    assert resultado.returncode == 0, resultado.stderr
    restantes = sorted(
        str(caminho.relative_to(tmp_path / "gribs" / alvo))
        for caminho in (tmp_path / "gribs" / alvo).rglob("*")
        if caminho.is_file()
    )
    assert restantes == ["06/outro.txt"]
    assert (
        tmp_path / "gribs" / outra_data / "00" / "gfs.t00z.pgrb2.0p25.f000"
    ).exists()

    for diretorio in ["mapasGrib", "matrizGrib", "matrizGrib/bluesky", "matrizGrib/predi"]:
        assert not (tmp_path / diretorio / alvo).exists()
        assert (tmp_path / diretorio / outra_data / "produto.txt").exists()


@pytest.mark.parametrize("data", ["2026-03-01", "20260231", "20260229"])
def test_t10_data_alvo_invalida_retorna_erro(tmp_path, data):
    env = os.environ.copy()
    env["MET_BASE_DIR"] = str(tmp_path)
    env["MET_DATA_ALVO"] = data

    resultado = _executa(ROOT / "remove_GRIBS_antigos.sh", env=env)

    assert resultado.returncode == 2
    assert "data alvo invalida" in resultado.stderr


def test_t10_data_de_referencia_invalida_retorna_erro(tmp_path):
    env = os.environ.copy()
    env["MET_BASE_DIR"] = str(tmp_path)
    env["MET_HOJE"] = "20260231"

    resultado = _executa(ROOT / "remove_GRIBS_antigos.sh", env=env)

    assert resultado.returncode == 2
    assert "data de referencia invalida" in resultado.stderr


# ---------------------------------------------------------------------------
# T-11 — CLI
# ---------------------------------------------------------------------------


def test_t11_variavel_chuva_falha_com_mensagem_clara(fake_python, tmp_path):
    env, _ = fake_python
    resultado = _executa(
        BASH / "automatiza_MET.sh", "-v", "chuva", "-ns", "-r", "SP", env=env
    )
    assert resultado.returncode == 2
    assert "chuvaConvec" in resultado.stderr

    resultado = subprocess.run(
        [
            sys.executable,
            str(CLASSES / "executa_reqs_param.py"),
            "-v",
            "chuva",
            "-ns",
        ]
        + _argumentos_man(tmp_path),
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 2
    assert "chuvaConvec" in resultado.stderr


def test_t11_regiao_mn_falha_indicando_am(fake_python):
    env, _ = fake_python
    resultado = _executa(
        BASH / "automatiza_MET.sh", "-v", "temp", "-n", "500", "-r", "MN", env=env
    )

    assert resultado.returncode == 2
    assert "MN" in resultado.stderr
    assert "AM" in resultado.stderr


@pytest.mark.parametrize(
    "script,variavel",
    [
        ("automatiza_MET.sh", "temp"),
        ("automatiza_vento_MET.sh", "wind"),
    ],
)
def test_t11_wrapper_rejeita_nivel_abaixo_de_150(fake_python, script, variavel):
    env, log = fake_python
    resultado = _executa(BASH / script, "-v", variavel, "-n", "50", "-r", "SP", env=env)

    assert resultado.returncode == 2
    assert "150 e 1000" in resultado.stderr
    assert not log.exists(), "o gerador nao deveria ser chamado"


def test_t11_wrapper_aceita_nivel_150(fake_python):
    env, log = fake_python
    resultado = _executa(
        BASH / "automatiza_MET.sh", "-v", "temp", "-n", "150", "-r", "SP", env=env
    )

    assert resultado.returncode == 0, resultado.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "gera_mapas_MET.py -v temp -n 150 -r SP",
        "gera_matriz_MET.py -v temp -n 150 -r SP",
    ]


def test_t11_help_man_deriva_catalogo(cli_man, monkeypatch):
    monkeypatch.setattr(cli_man, "VARIAVEIS_SUPERFICIE", ("sentinel_superficie",))
    monkeypatch.setattr(cli_man, "VARIAVEIS_PRESSAO", ("sentinel_pressao",))
    monkeypatch.setattr(cli_man, "VARIAVEIS_VENTO", ("vento_pressao", "vento_superficie"))

    texto = cli_man.cria_parser().format_help()

    assert "sentinel_superficie" in texto
    assert "sentinel_pressao" in texto
    assert "vento_pressao" in texto
    assert "vento_superficie" in texto


def test_t11_wrapper_man_nao_duplica_argumentos(fake_python, tmp_path):
    env, log = fake_python
    argumentos = [
        "-v",
        "temp",
        "-nhpa",
        "500",
        "-lonmin",
        "-56",
        "-lonmax",
        "-42",
        "-latmin",
        "-28",
        "-latmax",
        "-18",
        "-datetime",
        "202111020006",
        "-out",
        str(tmp_path),
    ]
    resultado = _executa(BASH / "reqs_MAN_MET.sh", *argumentos, env=env)

    assert resultado.returncode == 0, resultado.stderr
    linhas = log.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1
    assert linhas[0].endswith("executa_reqs_param.py " + " ".join(argumentos))
    assert linhas[0].count("-v ") == 1
    assert linhas[0].count("-nhpa ") == 1

    fonte = (BASH / "reqs_MAN_MET.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in fonte
    assert '"${4}"' not in fonte
    assert 'exec python3 "${PYTHON_SCRIPT}" "$@"' in fonte


def test_t11_cli_man_aceita_flags_fora_de_ordem(cli_man, tmp_path, monkeypatch):
    chamadas = []
    monkeypatch.setattr(cli_man, "_gera_escalar", lambda *args: chamadas.append(args))

    argumentos = [
        "-out",
        str(tmp_path),
        "-datetime",
        "202111020006",
        "-latmax",
        "-18",
        "-latmin",
        "-28",
        "-lonmax",
        "-42",
        "-lonmin",
        "-56",
        "-nhpa",
        "500",
        "-v",
        "temp",
    ]
    codigo = cli_man.main(argumentos)

    assert codigo == 0
    variavel, coords, data, saida, modo, nivel = chamadas[0]
    assert variavel == "temp"
    assert coords == (-56.0, -42.0, -28.0, -18.0)
    assert data == ("2021", "11", "02", "00", "06")
    assert saida.endswith(os.sep)
    assert modo == "single"
    assert nivel == 500


# ---------------------------------------------------------------------------
# T-12 — visibilidade METAR
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nuvem,esperado",
    [
        (None, "10000"),
        ([], "superior a 10000"),
        ([{"code": "BKN"}], "superior a 10000"),
    ],
)
def test_t12_visibilidade_distingue_nuvem_ausente_de_presente(nuvem, esperado):
    metar = _carrega_modulo(METAR_DIR / "metar_common.py", "metar_common_vis")
    assert metar.cria_resultado_visibilidade(False, nuvem, "9999") == esperado


def test_t12_visibilidade_preserva_valores_nao_9999():
    metar = _carrega_modulo(METAR_DIR / "metar_common.py", "metar_common_vis2")
    assert metar.cria_resultado_visibilidade(False, None, 8000) == 8000
    assert metar.cria_resultado_visibilidade(True, None, "9999") == "9999"


def test_t12_json_traduzido_usa_a_classificacao_correta():
    metar = _carrega_modulo(METAR_DIR / "metar_common.py", "metar_common_vis3")

    sem_nuvem = metar.cria_dict_metar_traduzido(
        "SBGR", "202602282350", FakeMetar(), FakeMetar().imprime_metar()
    )
    assert sem_nuvem["data"][0]["visibilidade [m]"] == "10000"
    assert sem_nuvem["data"][0]["condicao_nuvem"] == "informacao ausente"

    class FakeComNuvem(FakeMetar):
        def imprime_nuvem(self):
            return [
                {
                    "code": "BKN",
                    "meaning": "Broken",
                    "oktaMin": 5,
                    "oktaMax": 7,
                    "altitude": 1300,
                }
            ]

    com_nuvem = metar.cria_dict_metar_traduzido(
        "SBGR", "202602282350", FakeComNuvem(), FakeComNuvem().imprime_metar()
    )
    assert com_nuvem["data"][0]["visibilidade [m]"] == "superior a 10000"
    assert com_nuvem["data"][0]["condicao_nuvem"]["nuvem"][0]["Tipo de nuvem "] == "BKN"
