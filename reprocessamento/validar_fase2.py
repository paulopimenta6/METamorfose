#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valida a Fase 2 (T-06 a T-12) de forma independente.

A validação combina quatro tipos de evidência:

- leitura do código e dos scripts entregues;
- execução do CLI e dos wrappers com um ``python3`` falso no ``PATH`` para
  registrar exatamente quais geradores seriam chamados;
- execução das funções reais de METAR, intervalo e validação de nível;
- comparação dos produtos de ``winds`` já reprocessados na Fase 1 com a
  amostra GFS lida diretamente por ``pygrib``.

Escreve ``reprocessamento/reports/fase-2/validation.json`` e
``reprocessamento/reports/fase-2/pytest.txt``. Retorna código 1 se qualquer
verificação falhar.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import importlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pygrib

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ROOT / "classes_MET"
BASH = ROOT / "bash"
METAR_DIR = ROOT / "METARpy"
SAMPLE = ROOT / "baseline" / "samples" / "gfs.20261022.00.0p25.subset.grb2"
PHASE1_REPORT = ROOT / "reprocessamento" / "reports" / "20261022-00"
REPORT = ROOT / "reprocessamento" / "reports" / "fase-2"
FREEZE = ROOT / "baseline" / "freeze.json"

LAT1, LAT2 = -28.0, -18.0
LON1_360, LON2_360 = 304.0, 318.0
WIND_HEIGHTS = (20, 30, 40, 50, 80)
NIVEIS_INTERVALO = [200, 250, 300, 350, 400, 450, 500]

if str(CLASSES) not in sys.path:
    sys.path.insert(0, str(CLASSES))
if str(METAR_DIR) not in sys.path:
    sys.path.insert(0, str(METAR_DIR))


class Checks:
    def __init__(self):
        self.items = []
        self.failures = 0

    def check(self, name: str, condition: bool, detail=None):
        status = "ok" if condition else "falha"
        if not condition:
            self.failures += 1
        self.items.append({"name": name, "status": status, "detail": detail})
        print(f"[{'OK' if condition else 'FALHA'}] {name}")
        return condition

    def report(self):
        return {
            "status": "ok" if self.failures == 0 else "falha",
            "checks": len(self.items),
            "failures": self.failures,
            "items": self.items,
        }


class FakePython:
    """Um ``python3`` falso que registra os argumentos recebidos."""

    def __init__(self, base: Path):
        self.base = base
        self.bin_dir = base / "bin"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.log = base / "python.log"
        executavel = self.bin_dir / "python3"
        executavel.write_text(
            "#!/bin/bash\n"
            'printf "%s\\n" "$*" >> "${FAKE_PYTHON_LOG}"\n'
            "exit 0\n",
            encoding="utf-8",
        )
        executavel.chmod(0o755)

    def ambiente(self):
        env = os.environ.copy()
        env["PATH"] = "%s:%s" % (self.bin_dir, env.get("PATH", ""))
        env["FAKE_PYTHON_LOG"] = str(self.log)
        return env

    def limpar(self):
        if self.log.exists():
            self.log.unlink()

    def linhas(self):
        if not self.log.exists():
            return []
        return self.log.read_text(encoding="utf-8").splitlines()


@contextlib.contextmanager
def diretorio(caminho: Path):
    anterior = os.getcwd()
    os.chdir(caminho)
    try:
        yield
    finally:
        os.chdir(anterior)


def ler(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def executa(comando, *, env=None, cwd=ROOT, timeout=600):
    return subprocess.run(
        comando,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def executa_bash(script: Path, *args, env=None, cwd=ROOT):
    return executa(["bash", str(script), *args], env=env, cwd=cwd)


def carrega_modulo(caminho: Path, nome: str):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def importa_cli():
    return carrega_modulo(CLASSES / "executa_reqs_param.py", "executa_reqs_param_fase2")


def importa_processamento():
    """Importa o módulo de processamento sem executar leitura de GRIB.

    O módulo importa ``controla_env``, que lê ``../environment/path.conf``.
    Por isso a importação é feita a partir de ``classes_MET``. Usar a classe
    diretamente permite verificar a validação de nível sem abrir arquivos.
    """

    saida = io.StringIO()
    with contextlib.redirect_stdout(saida), diretorio(CLASSES):
        if "processamento_dados_MET" in sys.modules:
            return sys.modules["processamento_dados_MET"]
        return importlib.import_module("processamento_dados_MET")


def importa_metar():
    return carrega_modulo(METAR_DIR / "metar_common.py", "metar_common_fase2")


def argumentos_man(tmp: Path):
    return [
        "-lonmin", "-56",
        "-lonmax", "-42",
        "-latmin", "-28",
        "-latmax", "-18",
        "-datetime", "202111020006",
        "-out", str(tmp),
    ]


def captura_cli(cli, argumentos):
    """Executa ``cli.main`` sem trocar de diretório e captura os geradores."""

    chamadas = []
    original_chdir = cli.os.chdir
    original_escalar = cli._gera_escalar
    original_vento = cli._gera_vento
    cli.os.chdir = lambda caminho: None
    cli._gera_escalar = lambda *args: chamadas.append(("escalar", args))
    cli._gera_vento = lambda *args: chamadas.append(("vento", args))
    try:
        codigo = cli.main(argumentos)
    except SystemExit as exc:
        codigo = exc.code
    finally:
        cli.os.chdir = original_chdir
        cli._gera_escalar = original_escalar
        cli._gera_vento = original_vento
    return codigo, chamadas


def cli_com_erro(cli, argumentos):
    erro = io.StringIO()
    with contextlib.redirect_stderr(erro), contextlib.redirect_stdout(io.StringIO()):
        codigo, _ = captura_cli(cli, argumentos)
    return codigo, erro.getvalue()


def load_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    header = rows[0]
    data = np.array([[float(value) for value in row] for row in rows[1:]])
    return header, data


def independente(grb):
    values, lats, lons = grb.data(
        lat1=LAT1, lat2=LAT2, lon1=LON1_360, lon2=LON2_360
    )
    values = np.asarray(values, dtype=float)[::-1, :]
    lats = np.asarray(lats, dtype=float)[:, 0][::-1]
    lons = np.asarray(lons, dtype=float)[0, :] - 360.0
    return values, lats, lons


def seleciona(grib, nome, tipo, nivel=None):
    if nivel is None:
        return grib.select(name=nome, typeOfLevel=tipo)[0]
    return grib.select(name=nome, typeOfLevel=tipo, level=nivel)[0]


def angulo(u, v):
    return ((180 / np.pi) * np.arctan2(-u, -v) + 360) % 360


def compara_grid(checks, rotulo, dados, lats, lons):
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    checks.check(
        f"{rotulo}: lat alinhada e crescente",
        np.allclose(dados[:, 0], lat_grid.ravel(), atol=1e-12),
        [float(dados[:, 0].min()), float(dados[:, 0].max())],
    )
    checks.check(
        f"{rotulo}: lon alinhada",
        np.allclose(dados[:, 1], lon_grid.ravel(), atol=1e-12),
        [float(dados[:, 1].min()), float(dados[:, 1].max())],
    )


def compara_coluna(checks, rotulo, dados, indice, nome, esperado):
    checks.check(
        f"{rotulo}: coluna {nome}",
        np.allclose(dados[:, indice], np.asarray(esperado).ravel(), rtol=1e-12, atol=1e-9),
    )


# ---------------------------------------------------------------------------
# Invariantes das fases anteriores
# ---------------------------------------------------------------------------


def valida_invariantes(checks: Checks):
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    esperado = freeze["files"]["goGribV2.sh"]["sha256"]
    atual = hashlib.sha256((ROOT / "goGribV2.sh").read_bytes()).hexdigest()
    checks.check("invariante: goGribV2.sh congelado", atual == esperado, atual)

    validation = PHASE1_REPORT / "validation.json"
    if validation.exists():
        dados = json.loads(validation.read_text(encoding="utf-8"))
        checks.check(
            "invariante: validação da Fase 1 continua ok",
            dados.get("status") == "ok" and dados.get("failures") == 0,
            {"status": dados.get("status"), "checks": dados.get("checks")},
        )
    else:
        checks.check("invariante: validação da Fase 1 continua ok", False, "arquivo ausente")

    produtos = [
        caminho
        for caminho in PHASE1_REPORT.rglob("*")
        if caminho.is_file()
        and caminho.name not in {"summary.json", "validation.json", "pytest.txt"}
    ]
    checks.check(
        "invariante: 20 produtos da Fase 1 preservados",
        len(produtos) == 20,
        len(produtos),
    )

    status = executa(["git", "status", "--porcelain", "--", "baseline"], cwd=ROOT)
    checks.check(
        "invariante: baseline sem alterações no Git",
        status.returncode == 0 and not status.stdout.strip(),
        status.stdout.strip() or None,
    )


# ---------------------------------------------------------------------------
# T-06 — umidadeRel
# ---------------------------------------------------------------------------


def valida_t06(checks: Checks, fake: FakePython, tmp: Path):
    controle = ler(BASH / "automatizacao_controle_MET.sh")
    chamadas = [
        linha.strip()
        for linha in controle.splitlines()
        if linha.strip().startswith("./automatiza_MET.sh")
        and '"umidadeRel"' in linha
    ]
    checks.check(
        "T-06: controlador tem duas chamadas de umidadeRel",
        len(chamadas) == 2,
        chamadas,
    )
    checks.check(
        "T-06: nenhuma chamada umidadeRel usa -ns",
        all('"-ns"' not in linha for linha in chamadas),
        chamadas,
    )
    checks.check(
        "T-06: chamadas usam -n 850",
        all('"-n" "850"' in linha for linha in chamadas),
        chamadas,
    )

    try:
        modulo = importa_processamento()
        classe = modulo.processamento_dados_met_AUT
        classe._valida_nivel("umidadeRel", "isobaricInhPa", "surface")
        erro = "nenhum erro"
        rejeitou = False
    except Exception as exc:  # noqa: BLE001 - o teste precisa da mensagem real
        erro = str(exc)
        rejeitou = True
    checks.check(
        "T-06: classe rejeita umidadeRel em superfície com mensagem clara",
        rejeitou and "850" in erro,
        erro,
    )

    try:
        modulo = importa_processamento()
        modulo.processamento_dados_met_AUT._valida_nivel(
            "umidadeRel", "isobaricInhPa", 850
        )
        aceitou = True
        erro = None
    except Exception as exc:  # noqa: BLE001
        aceitou = False
        erro = str(exc)
    checks.check(
        "T-06: classe aceita umidadeRel em 850 hPa",
        aceitou,
        erro,
    )

    cli = importa_cli()
    codigo, stderr = cli_com_erro(
        cli, ["-v", "umidadeRel", "-ns"] + argumentos_man(tmp)
    )
    checks.check(
        "T-06: CLI MAN rejeita umidadeRel -ns",
        codigo == 2 and "850" in stderr,
        {"codigo": codigo, "stderr": stderr.strip()[-200:]},
    )

    fake.limpar()
    resultado = executa_bash(
        BASH / "automatiza_MET.sh",
        "-v", "umidadeRel", "-n", "850", "-r", "SP",
        env=fake.ambiente(),
    )
    checks.check(
        "T-06: wrapper AUT aceita umidadeRel -n 850",
        resultado.returncode == 0,
        resultado.stderr.strip()[-200:],
    )
    checks.check(
        "T-06: wrapper AUT entrega mapas e matrizes",
        fake.linhas()
        == [
            "gera_mapas_MET.py -v umidadeRel -n 850 -r SP",
            "gera_matriz_MET.py -v umidadeRel -n 850 -r SP",
        ],
        fake.linhas(),
    )

    fake.limpar()
    resultado = executa_bash(
        BASH / "automatiza_MET.sh",
        "-v", "umidadeRel", "-ns", "-r", "SP",
        env=fake.ambiente(),
    )
    checks.check(
        "T-06: wrapper AUT rejeita umidadeRel -ns",
        resultado.returncode == 2 and "850" in resultado.stderr,
        {"codigo": resultado.returncode, "stderr": resultado.stderr.strip()[-200:]},
    )

    fonte_mapas = ler(CLASSES / "gera_mapas_MET.py")
    checks.check(
        "T-06: mapa de umidadeRel conserva o nível de pressão no rótulo",
        'if variavelMET=="temps" or variavelMET=="ps" or variavelMET=="prnm":'
        in fonte_mapas
        and 'if variavelMET=="umidadeRel" or' not in fonte_mapas,
        "Nsuperficie não deve ser aplicado a umidadeRel",
    )


# ---------------------------------------------------------------------------
# T-07 — winds
# ---------------------------------------------------------------------------


def valida_t07(checks: Checks, fake: FakePython):
    controle = ler(BASH / "automatizacao_controle_MET.sh")
    linhas = [
        linha.strip()
        for linha in controle.splitlines()
        if linha.strip().startswith("./automatiza_vento_MET.sh")
    ]
    winds = [linha for linha in linhas if '"winds"' in linha and '"-ns"' in linha]
    checks.check(
        "T-07: controlador tem duas chamadas winds -ns",
        len(winds) == 2,
        winds,
    )
    checks.check(
        "T-07: controlador cobre SP e RJ",
        any('"-r" "SP"' in linha for linha in winds)
        and any('"-r" "RJ"' in linha for linha in winds),
        winds,
    )
    checks.check(
        "T-07: chamadas no-op de vento foram removidas",
        not any(linha.startswith('./automatiza_vento_MET.sh "-n"') for linha in linhas),
        linhas,
    )
    checks.check(
        "T-07: wind 1000 hPa aparece duas vezes",
        sum('"wind" "-n" "1000"' in linha for linha in linhas) == 2,
        linhas,
    )
    checks.check(
        "T-07: wind 200 hPa aparece duas vezes",
        sum('"wind" "-n" "200"' in linha for linha in linhas) == 2,
        linhas,
    )

    fake.limpar()
    resultado = executa_bash(
        BASH / "automatiza_vento_MET.sh",
        "-v", "winds", "-ns", "-r", "SP",
        env=fake.ambiente(),
    )
    checks.check(
        "T-07: wrapper de vento executa sem erro",
        resultado.returncode == 0,
        resultado.stderr.strip()[-200:],
    )
    checks.check(
        "T-07: wrapper entrega mapas e matrizes de winds",
        fake.linhas()
        == [
            "gera_mapas_vento_MET.py -v winds -ns -r SP",
            "gera_matriz_vento_MET.py -v winds -ns -r SP",
        ],
        fake.linhas(),
    )

    with pygrib.open(str(SAMPLE)) as grib:
        superficie = independente(seleciona(grib, "Temperature", "surface"))[0]
        for nivel in WIND_HEIGHTS:
            u = independente(
                seleciona(grib, "U component of wind", "heightAboveGround", nivel)
            )[0]
            v = independente(
                seleciona(grib, "V component of wind", "heightAboveGround", nivel)
            )[0]
            lats = independente(
                seleciona(grib, "U component of wind", "heightAboveGround", nivel)
            )[1]
            lons = independente(
                seleciona(grib, "U component of wind", "heightAboveGround", nivel)
            )[2]

            mapa = (
                PHASE1_REPORT
                / "mapas"
                / f"GFS_0.25_SP_N{nivel}_CampoVento_00_20261022_00.png"
            )
            checks.check(
                f"T-07: mapa de winds N{nivel} presente e não vazio",
                mapa.exists() and mapa.stat().st_size > 0,
                str(mapa.relative_to(ROOT)),
            )

            bluesky_path = (
                PHASE1_REPORT
                / "bluesky"
                / f"GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N{nivel}_00_20261022_00.csv"
            )
            header, dados = load_csv(bluesky_path)
            checks.check(
                f"T-07: header BlueSky N{nivel}",
                header == ["lat", "lon", "hMET", "angMET", "vento_resultante"],
                header,
            )
            compara_grid(checks, f"T-07 BlueSky N{nivel}", dados, lats, lons)
            compara_coluna(
                checks,
                f"T-07 BlueSky N{nivel}",
                dados,
                2,
                "hMET",
                np.full_like(u, nivel * 3.28084),
            )
            compara_coluna(
                checks,
                f"T-07 BlueSky N{nivel}",
                dados,
                3,
                "angMET",
                angulo(u, v),
            )
            compara_coluna(
                checks,
                f"T-07 BlueSky N{nivel}",
                dados,
                4,
                "vento_resultante",
                np.sqrt(u**2 + v**2) * 1.943,
            )

            predi_path = (
                PHASE1_REPORT
                / "predi"
                / f"GFS_0.25_matriz_lat_lon_Vento_UVT_Predi_SP_N{nivel}_00_20261022_00.csv"
            )
            header, dados = load_csv(predi_path)
            checks.check(
                f"T-07: header preditor N{nivel}",
                header == ["lat", "lon", "vento U", "vento V", "temp"],
                header,
            )
            compara_grid(checks, f"T-07 preditor N{nivel}", dados, lats, lons)
            compara_coluna(checks, f"T-07 preditor N{nivel}", dados, 2, "vento U", u)
            compara_coluna(checks, f"T-07 preditor N{nivel}", dados, 3, "vento V", v)
            compara_coluna(
                checks,
                f"T-07 preditor N{nivel}",
                dados,
                4,
                "temp",
                superficie,
            )
            checks.check(
                f"T-07: preditor N{nivel} usa U e V distintos",
                not np.allclose(dados[:, 2], dados[:, 3]),
            )


# ---------------------------------------------------------------------------
# T-08 — METAR
# ---------------------------------------------------------------------------


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


class FakeMetarComNuvem(FakeMetar):
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


def valida_t08(checks: Checks, fake: FakePython, tmp: Path):
    metar = importa_metar()

    referencia = datetime(2026, 3, 1, 0, 10, tzinfo=timezone.utc)
    checks.check(
        "T-08: diretório usa a data UTC da referência",
        metar.data_diretorio_utc(referencia) == "20260301",
        metar.data_diretorio_utc(referencia),
    )
    checks.check(
        "T-08: rollover de mês (28/02 23:50 UTC)",
        metar.resolve_data_metar(("28", "23", "50"), referencia)
        == "202602282350",
        metar.resolve_data_metar(("28", "23", "50"), referencia),
    )
    referencia_ano = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)
    checks.check(
        "T-08: rollover de ano (31/12 23:50 UTC)",
        metar.resolve_data_metar(("31", "23", "50"), referencia_ano)
        == "202512312350",
        metar.resolve_data_metar(("31", "23", "50"), referencia_ano),
    )
    checks.check(
        "T-08: data no mesmo mês",
        metar.resolve_data_metar(("01", "00", "10"), datetime(2026, 3, 2, 0, 20, tzinfo=timezone.utc))
        == "202603010010",
    )

    anterior = os.environ.get("METAR_REFERENCIA_UTC")
    os.environ["METAR_REFERENCIA_UTC"] = "202603010010"
    try:
        checks.check(
            "T-08: referência UTC vem do ambiente",
            metar.agora_utc() == datetime(2026, 3, 1, 0, 10, tzinfo=timezone.utc),
            metar.agora_utc().isoformat(),
        )
    finally:
        if anterior is None:
            os.environ.pop("METAR_REFERENCIA_UTC", None)
        else:
            os.environ["METAR_REFERENCIA_UTC"] = anterior

    destino = tmp / "metar"
    destino.mkdir(parents=True, exist_ok=True)

    def fabrica(aerodromo):
        return FakeMetar(aerodromo)

    def cria_bruto(sigla, data, cod, mensagem):
        return metar.cria_dict_metar_bruto(sigla, data, mensagem)

    codigo = metar.executa_estacoes(
        fabrica, cria_bruto, "", referencia, destino
    )
    checks.check("T-08: execução METAR retorna 0", codigo == 0, codigo)
    arquivos = sorted(destino.glob("*.json"))
    checks.check(
        "T-08: um JSON por estação",
        len(arquivos) == len(metar.AERODROMOS),
        len(arquivos),
    )
    checks.check(
        "T-08: nenhum arquivo temporário permanece",
        not list(destino.glob("*.tmp")),
    )

    caminho = destino / "SBGR202602282350.json"
    if caminho.exists():
        primeiro = json.loads(caminho.read_text(encoding="utf-8"))
        checks.check(
            "T-08: JSON bruto preserva as chaves históricas",
            primeiro
            == {
                "data": [
                    {
                        "id_localidade ": "SBGR",
                        "data ": "202602282350",
                        "mensagem_metar ": "SBGR 282350Z 08003KT 9000 NSC 13/10 Q1023",
                    }
                ]
            },
            primeiro,
        )
    else:
        checks.check("T-08: JSON bruto preserva as chaves históricas", False, "SBGR ausente")

    codigo = metar.executa_estacoes(
        fabrica, cria_bruto, "", referencia, destino
    )
    if caminho.exists():
        segundo = json.loads(caminho.read_text(encoding="utf-8"))
        checks.check(
            "T-08: reexecução sobrescreve sem concatenar",
            codigo == 0 and segundo == primeiro,
            {"codigo": codigo, "igual": segundo == primeiro},
        )
    else:
        checks.check("T-08: reexecução sobrescreve sem concatenar", False, "SBGR ausente")

    traduzido = metar.cria_dict_metar_traduzido(
        "SBGR",
        "202602282350",
        FakeMetar(),
        FakeMetar().imprime_metar(),
    )
    checks.check(
        "T-08: JSON traduzido mantém o schema",
        traduzido["data"][0]["estacao"] == "SBGR"
        and traduzido["data"][0]["visibilidade [m]"] == "10000"
        and traduzido["data"][0]["condicao_nuvem"] == "informacao ausente",
        traduzido["data"][0],
    )

    base_metar = tmp / "METARpy"
    env = fake.ambiente()
    env["METAR_BASE_DIR"] = str(base_metar)
    env["METAR_REFERENCIA_UTC"] = "202603010010"
    fake.limpar()
    resultado = executa_bash(METAR_DIR / "automatizaMetar.sh", env=env)
    checks.check(
        "T-08: script METAR executa sem erro",
        resultado.returncode == 0,
        resultado.stderr.strip()[-200:],
    )
    checks.check(
        "T-08: script METAR cria o diretório da data UTC",
        (base_metar / "20260301").is_dir(),
        str(base_metar / "20260301"),
    )
    checks.check(
        "T-08: script METAR chama bruto e traduzido",
        fake.linhas() == ["../METARpy.py", "../METARpy_traduzido.py"],
        fake.linhas(),
    )

    fonte = ler(METAR_DIR / "automatizaMetar.sh")
    checks.check(
        "T-08: script METAR usa set -euo pipefail",
        "set -euo pipefail" in fonte,
    )
    checks.check(
        "T-08: script METAR usa uma única referência UTC",
        "date -u +%Y%m%d%H%M" in fonte
        and "export METAR_REFERENCIA_UTC" in fonte
        and "data_hora" not in fonte
        and "data_min" not in fonte,
    )


# ---------------------------------------------------------------------------
# T-09 — intervalo MAN
# ---------------------------------------------------------------------------


def valida_t09(checks: Checks, tmp: Path):
    cli = importa_cli()
    checks.check(
        "T-09: 200->500 produz a lista esperada",
        cli.cria_intervalo_niveis(200, 500) == NIVEIS_INTERVALO,
        cli.cria_intervalo_niveis(200, 500),
    )
    checks.check(
        "T-09: 500->200 produz a mesma lista",
        cli.cria_intervalo_niveis(500, 200) == NIVEIS_INTERVALO,
        cli.cria_intervalo_niveis(500, 200),
    )
    checks.check(
        "T-09: níveis iguais produzem um elemento",
        cli.cria_intervalo_niveis(500, 500) == [500],
        cli.cria_intervalo_niveis(500, 500),
    )

    for minimo, maximo in ((149, 500), (200, 1001), (-10, 300)):
        codigo, stderr = cli_com_erro(
            cli,
            [
                "-v", "temp",
                "-altminhpa", str(minimo),
                "-altmaxhpa", str(maximo),
            ]
            + argumentos_man(tmp),
        )
        checks.check(
            f"T-09: intervalo {minimo}..{maximo} falha claramente",
            codigo == 2 and "fora da faixa" in stderr,
            {"codigo": codigo, "stderr": stderr.strip()[-200:]},
        )

    for ordem in ((200, 500), (500, 200)):
        codigo, chamadas = captura_cli(
            cli,
            [
                "-v", "temp",
                "-altminhpa", str(ordem[0]),
                "-altmaxhpa", str(ordem[1]),
            ]
            + argumentos_man(tmp),
        )
        checks.check(
            f"T-09: execução {ordem[0]}->{ordem[1]} retorna 0",
            codigo == 0 and bool(chamadas),
            {"codigo": codigo, "chamadas": len(chamadas)},
        )
        if chamadas:
            _, args = chamadas[-1]
            checks.check(
                f"T-09: execução {ordem[0]}->{ordem[1]} usa níveis crescentes",
                args[4] == "interval" and args[5] == NIVEIS_INTERVALO,
                {"modo": args[4], "niveis": args[5]},
            )


# ---------------------------------------------------------------------------
# T-10 — limpeza
# ---------------------------------------------------------------------------


def cria_fixture_limpeza(base: Path, data_alvo: str, outra_data: str = "20250101"):
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

    for diretorio in (
        "mapasGrib",
        "matrizGrib",
        "matrizGrib/bluesky",
        "matrizGrib/predi",
    ):
        for data in (data_alvo, outra_data):
            caminho = base / diretorio / data / "produto.txt"
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text("x", encoding="utf-8")
    return outra_data


def valida_t10(checks: Checks, tmp: Path):
    for hoje, alvo in (
        ("20260301", "20260227"),
        ("20260302", "20260228"),
        ("20260315", "20260313"),
    ):
        base = tmp / f"limpeza-{hoje}"
        outra = cria_fixture_limpeza(base, alvo)
        env = os.environ.copy()
        env["MET_BASE_DIR"] = str(base)
        env["MET_HOJE"] = hoje
        resultado = executa_bash(ROOT / "remove_GRIBS_antigos.sh", env=env)
        checks.check(
            f"T-10: limpeza de {hoje} retorna 0",
            resultado.returncode == 0,
            resultado.stderr.strip()[-200:],
        )
        restantes = sorted(
            str(caminho.relative_to(base / "gribs" / alvo))
            for caminho in (base / "gribs" / alvo).rglob("*")
            if caminho.is_file()
        )
        checks.check(
            f"T-10: {hoje} remove 0p25, 1p00 e legados do dia alvo",
            restantes == ["06/outro.txt"],
            restantes,
        )
        checks.check(
            f"T-10: {hoje} preserva outra data",
            (
                base / "gribs" / outra / "00" / "gfs.t00z.pgrb2.0p25.f000"
            ).exists(),
        )
        for diretorio in (
            "mapasGrib",
            "matrizGrib",
            "matrizGrib/bluesky",
            "matrizGrib/predi",
        ):
            checks.check(
                f"T-10: {hoje} remove produtos de {diretorio}",
                not (base / diretorio / alvo).exists(),
            )
            checks.check(
                f"T-10: {hoje} preserva {diretorio} de outra data",
                (base / diretorio / outra / "produto.txt").exists(),
            )

    base = tmp / "limpeza-data-invalida"
    base.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MET_BASE_DIR"] = str(base)
    env["MET_DATA_ALVO"] = "2026-03-01"
    resultado = executa_bash(ROOT / "remove_GRIBS_antigos.sh", env=env)
    checks.check(
        "T-10: data alvo inválida retorna 2",
        resultado.returncode == 2 and "data alvo invalida" in resultado.stderr,
        {"codigo": resultado.returncode, "stderr": resultado.stderr.strip()[-200:]},
    )

    for data in ("20260231", "20260229"):
        base = tmp / f"limpeza-data-invalida-{data}"
        base.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["MET_BASE_DIR"] = str(base)
        env["MET_DATA_ALVO"] = data
        resultado = executa_bash(ROOT / "remove_GRIBS_antigos.sh", env=env)
        checks.check(
            f"T-10: data alvo {data} fora do calendário retorna 2",
            resultado.returncode == 2
            and "data alvo invalida" in resultado.stderr
            and "calendario" in resultado.stderr,
            {
                "codigo": resultado.returncode,
                "stderr": resultado.stderr.strip()[-200:],
            },
        )

    base = tmp / "limpeza-referencia-invalida"
    base.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MET_BASE_DIR"] = str(base)
    env["MET_HOJE"] = "20260231"
    resultado = executa_bash(ROOT / "remove_GRIBS_antigos.sh", env=env)
    checks.check(
        "T-10: data de referência fora do calendário retorna 2",
        resultado.returncode == 2
        and "data de referencia invalida" in resultado.stderr,
        {"codigo": resultado.returncode, "stderr": resultado.stderr.strip()[-200:]},
    )

    fonte = ler(ROOT / "remove_GRIBS_antigos.sh")
    checks.check(
        "T-10: limpeza calcula a data com date -d -2 days",
        'date -d "-2 days" +"%Y%m%d"' in fonte,
    )
    checks.check(
        "T-10: limpeza cobre 0p25 e 1p00",
        "0p25" in fonte and "1p00" in fonte,
    )


# ---------------------------------------------------------------------------
# T-11 — CLI
# ---------------------------------------------------------------------------


def valida_t11(checks: Checks, fake: FakePython, tmp: Path):
    argumentos = [
        "-v", "temp",
        "-nhpa", "500",
        "-lonmin", "-56",
        "-lonmax", "-42",
        "-latmin", "-28",
        "-latmax", "-18",
        "-datetime", "202111020006",
        "-out", str(tmp),
    ]
    fake.limpar()
    resultado = executa_bash(
        BASH / "reqs_MAN_MET.sh", *argumentos, env=fake.ambiente()
    )
    linhas = fake.linhas()
    checks.check(
        "T-11: wrapper MAN executa sem erro",
        resultado.returncode == 0,
        resultado.stderr.strip()[-200:],
    )
    checks.check(
        "T-11: wrapper MAN não duplica argumentos",
        len(linhas) == 1
        and linhas[0].endswith("executa_reqs_param.py " + " ".join(argumentos))
        and linhas[0].count("-v ") == 1
        and linhas[0].count("-nhpa ") == 1,
        linhas,
    )
    fonte = ler(BASH / "reqs_MAN_MET.sh")
    checks.check(
        "T-11: wrapper MAN é fino e validado",
        "set -euo pipefail" in fonte
        and '"${4}"' not in fonte
        and 'exec python3 "${PYTHON_SCRIPT}" "$@"' in fonte,
    )

    fake.limpar()
    resultado = executa_bash(
        BASH / "automatiza_MET.sh",
        "-v", "chuva", "-ns", "-r", "SP",
        env=fake.ambiente(),
    )
    checks.check(
        "T-11: wrapper AUT rejeita 'chuva' com mensagem clara",
        resultado.returncode == 2
        and "chuvaConvec" in resultado.stderr
        and "chuvaNaoConvec" in resultado.stderr,
        {"codigo": resultado.returncode, "stderr": resultado.stderr.strip()[-200:]},
    )

    cli = importa_cli()
    codigo, stderr = cli_com_erro(
        cli, ["-v", "chuva", "-ns"] + argumentos_man(tmp)
    )
    checks.check(
        "T-11: CLI MAN rejeita 'chuva' com mensagem clara",
        codigo == 2
        and "chuvaConvec" in stderr
        and "chuvaNaoConvec" in stderr,
        {"codigo": codigo, "stderr": stderr.strip()[-200:]},
    )

    fake.limpar()
    resultado = executa_bash(
        BASH / "automatiza_MET.sh",
        "-v", "temp", "-n", "500", "-r", "MN",
        env=fake.ambiente(),
    )
    checks.check(
        "T-11: região MN falha indicando AM",
        resultado.returncode == 2
        and "MN" in resultado.stderr
        and "AM" in resultado.stderr,
        {"codigo": resultado.returncode, "stderr": resultado.stderr.strip()[-200:]},
    )

    for script, variavel in (
        ("automatiza_MET.sh", "temp"),
        ("automatiza_vento_MET.sh", "wind"),
    ):
        fake.limpar()
        resultado = executa_bash(
            BASH / script,
            "-v", variavel, "-n", "50", "-r", "SP",
            env=fake.ambiente(),
        )
        checks.check(
            f"T-11: {script} rejeita nível abaixo de 150 hPa",
            resultado.returncode == 2
            and "150 e 1000" in resultado.stderr
            and fake.linhas() == [],
            {
                "codigo": resultado.returncode,
                "stderr": resultado.stderr.strip()[-200:],
                "chamadas": fake.linhas(),
            },
        )

    fake.limpar()
    resultado = executa_bash(
        BASH / "automatiza_MET.sh",
        "-v", "temp", "-n", "150", "-r", "SP",
        env=fake.ambiente(),
    )
    checks.check(
        "T-11: limite inferior de 150 hPa é aceito",
        resultado.returncode == 0
        and fake.linhas()
        == [
            "gera_mapas_MET.py -v temp -n 150 -r SP",
            "gera_matriz_MET.py -v temp -n 150 -r SP",
        ],
        {
            "codigo": resultado.returncode,
            "stderr": resultado.stderr.strip()[-200:],
            "chamadas": fake.linhas(),
        },
    )

    cli = importa_cli()
    originais = (
        cli.VARIAVEIS_SUPERFICIE,
        cli.VARIAVEIS_PRESSAO,
        cli.VARIAVEIS_VENTO,
    )
    try:
        cli.VARIAVEIS_SUPERFICIE = ("sentinel_superficie",)
        cli.VARIAVEIS_PRESSAO = ("sentinel_pressao",)
        cli.VARIAVEIS_VENTO = ("vento_pressao", "vento_superficie")
        ajuda = cli.cria_parser().format_help()
    finally:
        (
            cli.VARIAVEIS_SUPERFICIE,
            cli.VARIAVEIS_PRESSAO,
            cli.VARIAVEIS_VENTO,
        ) = originais
    checks.check(
        "T-11: help MAN é gerado a partir do catálogo",
        "sentinel_superficie" in ajuda
        and "sentinel_pressao" in ajuda
        and "vento_pressao" in ajuda
        and "vento_superficie" in ajuda,
    )

    argumentos_fora_de_ordem = [
        "-out", str(tmp),
        "-datetime", "202111020006",
        "-latmax", "-18",
        "-latmin", "-28",
        "-lonmax", "-42",
        "-lonmin", "-56",
        "-nhpa", "500",
        "-v", "temp",
    ]
    codigo, chamadas = captura_cli(cli, argumentos_fora_de_ordem)
    checks.check(
        "T-11: CLI MAN aceita flags fora de ordem",
        codigo == 0 and len(chamadas) == 1,
        {"codigo": codigo, "chamadas": len(chamadas)},
    )
    if chamadas:
        _, args = chamadas[0]
        checks.check(
            "T-11: flags fora de ordem preservam variável, coordenadas e nível",
            args[0] == "temp"
            and args[1] == (-56.0, -42.0, -28.0, -18.0)
            and args[4] == "single"
            and args[5] == 500,
            {"variavel": args[0], "coords": args[1], "modo": args[4], "nivel": args[5]},
        )


# ---------------------------------------------------------------------------
# T-12 — visibilidade METAR
# ---------------------------------------------------------------------------


def valida_t12(checks: Checks):
    metar = importa_metar()

    for nuvem, esperado in (
        (None, "10000"),
        ([], "superior a 10000"),
        ([{"code": "BKN"}], "superior a 10000"),
    ):
        obtido = metar.cria_resultado_visibilidade(False, nuvem, "9999")
        checks.check(
            f"T-12: visibilidade com nuvem={nuvem!r}",
            obtido == esperado,
            obtido,
        )

    checks.check(
        "T-12: visibilidade não 9999 é preservada",
        metar.cria_resultado_visibilidade(False, None, 8000) == 8000,
    )
    checks.check(
        "T-12: estação automática preserva 9999",
        metar.cria_resultado_visibilidade(True, None, "9999") == "9999",
    )

    sem_nuvem = metar.cria_dict_metar_traduzido(
        "SBGR", "202602282350", FakeMetar(), FakeMetar().imprime_metar()
    )
    com_nuvem = metar.cria_dict_metar_traduzido(
        "SBGR",
        "202602282350",
        FakeMetarComNuvem(),
        FakeMetarComNuvem().imprime_metar(),
    )
    checks.check(
        "T-12: JSON traduzido classifica ausência de nuvem",
        sem_nuvem["data"][0]["visibilidade [m]"] == "10000"
        and sem_nuvem["data"][0]["condicao_nuvem"] == "informacao ausente",
        sem_nuvem["data"][0],
    )
    checks.check(
        "T-12: JSON traduzido classifica presença de nuvem",
        com_nuvem["data"][0]["visibilidade [m]"] == "superior a 10000"
        and com_nuvem["data"][0]["condicao_nuvem"]["nuvem"][0]["Tipo de nuvem "]
        == "BKN",
        com_nuvem["data"][0],
    )

    fonte = ler(METAR_DIR / "metar_common.py")
    checks.check(
        "T-12: código não usa str(nuvem) nas comparações",
        "str(nuvem) is not None" not in fonte
        and "str(nuvem) is None" not in fonte
        and "nuvem is not None" in fonte
        and "nuvem is None" in fonte,
    )


# ---------------------------------------------------------------------------
# Execução dos testes e relatório
# ---------------------------------------------------------------------------


def valida_pytest(checks: Checks):
    resultado = executa(
        [sys.executable, "-m", "pytest", "-q", "tests/test_phase2_acceptance.py"],
        cwd=ROOT,
        timeout=900,
    )
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "pytest.txt").write_text(
        resultado.stdout + resultado.stderr, encoding="utf-8"
    )
    checks.check(
        "T-06 a T-12: suíte de aceitação da Fase 2 verde",
        resultado.returncode == 0,
        {
            "codigo": resultado.returncode,
            "resumo": (resultado.stdout + resultado.stderr).strip().splitlines()[-1]
            if (resultado.stdout + resultado.stderr).strip()
            else "",
        },
    )


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    checks = Checks()
    tmp = Path(tempfile.mkdtemp(prefix="validar-fase2.", dir="/tmp/opencode"))
    try:
        fake = FakePython(tmp / "fake-python")
        valida_invariantes(checks)
        valida_t06(checks, fake, tmp)
        valida_t07(checks, fake)
        valida_t08(checks, fake, tmp)
        valida_t09(checks, tmp)
        valida_t10(checks, tmp)
        valida_t11(checks, fake, tmp)
        valida_t12(checks)
        valida_pytest(checks)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    relatorio = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Validação independente da Fase 2 (T-06 a T-12).",
        "phase": 2,
        "sample": {
            "path": str(SAMPLE.relative_to(ROOT)),
            "sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),
        },
        "phase1_report": str(PHASE1_REPORT.relative_to(ROOT)),
        **checks.report(),
    }
    (REPORT / "validation.json").write_text(
        json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"\n[validacao] {relatorio['checks']} verificações, "
        f"{relatorio['failures']} falhas"
    )
    print(f"[validacao] relatório: {REPORT / 'validation.json'}")
    return 0 if relatorio["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
