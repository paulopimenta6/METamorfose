#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Funcoes comuns do fluxo METAR.

Este modulo nao importa GoMETAR/PythonMETAR, portanto pode ser testado sem a
dependencia externa e sem executar chamadas de rede. As rotinas de escrita
usam sobrescrita atomica (`arquivo.tmp` + `os.replace`) para nunca deixar um
JSON truncado ou concatenado.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Aerodromos importantes para obter METAR:
# SP: SBGR
# RJ: SBGL
# CW: SBCT
# PA: SBPA
# BH: SBCF
# Belem: SBBE
# Manaus: SBEG
# Recife: SBRF
# Fortaleza: SBFZ
AERODROMOS = {
    "SP": "SBGR",  # Aeroporto de Guarulhos
    "RJ": "SBGL",  # Aeroporto do Galeao
    "CW": "SBCT",  # Aeroporto de Curitiba
    "PA": "SBPA",  # Aeroporto de Porto Alegre
    "BH": "SBCF",  # Aeroporto de Belo Horizonte
    "BE": "SBBE",  # Aeroporto de Belem
    "MA": "SBEG",  # Aeroporto de Manaus
    "RF": "SBRF",  # Aeroporto de Recife
    "FZ": "SBFZ",  # Aeroporto de Fortaleza
}

VARIAVEL_REFERENCIA_UTC = "METAR_REFERENCIA_UTC"


def agora_utc():
    """Devolve a referencia UTC do ciclo.

    O shell exporta `METAR_REFERENCIA_UTC` para que o diretorio e o nome dos
    arquivos usem exatamente o mesmo instante, mesmo se a execucao atravessar
    a meia-noite. Sem a variavel, usa o relogio UTC atual.
    """

    valor = os.environ.get(VARIAVEL_REFERENCIA_UTC)
    if valor:
        try:
            referencia = datetime.strptime(valor, "%Y%m%d%H%M")
        except ValueError as exc:
            raise ValueError(
                "%s invalida: %r; use AAAAMMDDHHMM em UTC"
                % (VARIAVEL_REFERENCIA_UTC, valor)
            ) from exc
        return referencia.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc)


def data_diretorio_utc(referencia=None):
    """Data (AAAAMMDD) usada no diretorio do ciclo METAR."""

    referencia = referencia or agora_utc()
    return referencia.strftime("%Y%m%d")


def resolve_data_metar(data_metar, referencia=None):
    """Resolve DD/HH/MM do METAR para AAAAMMDDHHMM usando a referencia UTC.

    O METAR informa apenas dia, hora e minuto. Quando o dia observado e maior
    que o dia da referencia, a observacao pertence ao mes anterior (rollover de
    virada de mes/ano). A mesma referencia e usada pelo diretorio.
    """

    if isinstance(data_metar, str):
        partes = (data_metar[0:2], data_metar[2:4], data_metar[4:6])
    else:
        partes = tuple(data_metar)

    if len(partes) != 3:
        raise ValueError("data METAR invalida: esperado (dia, hora, minuto)")

    try:
        dia, hora, minuto = (int(parte) for parte in partes)
    except (TypeError, ValueError) as exc:
        raise ValueError("data METAR invalida: %r" % (data_metar,)) from exc

    if not 1 <= dia <= 31:
        raise ValueError("dia METAR fora da faixa 1..31: %d" % dia)
    if not 0 <= hora <= 23:
        raise ValueError("hora METAR fora da faixa 0..23: %d" % hora)
    if not 0 <= minuto <= 59:
        raise ValueError("minuto METAR fora da faixa 0..59: %d" % minuto)

    referencia = referencia or agora_utc()
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)

    ano = referencia.year
    mes = referencia.month
    if dia > referencia.day:
        mes_anterior = referencia.replace(day=1) - timedelta(days=1)
        ano = mes_anterior.year
        mes = mes_anterior.month

    try:
        observacao = datetime(ano, mes, dia, hora, minuto, tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(
            "data METAR invalida para a referencia %s: %02d/%02d %02d:%02d"
            % (referencia.strftime("%Y-%m-%d %H:%M UTC"), dia, mes, hora, minuto)
        ) from exc

    return observacao.strftime("%Y%m%d%H%M")


def cria_dict_metar_bruto(sigla, data, mensagem):
    """Monta o JSON bruto preservando as chaves historicas (com espaco)."""

    return {
        "data": [
            {
                "id_localidade ": sigla,
                "data ": data,
                "mensagem_metar ": mensagem,
            }
        ]
    }


def cria_dados_nuvem(dados):
    """Converte a tupla de nuvens do PythonMETAR no dicionario historico."""

    if dados is not None:
        dict_nuvem_condicao = {}
        dict_nuvem_condicao["nuvem"] = []
        for i in range(len(dados)):
            dict_nuvem_condicao["nuvem"].append(
                {
                    "Tipo de nuvem ": dados[i]["code"],
                    "Tipo de nuvem (nome completo) ": dados[i]["meaning"],
                    "Cobertura minima de nuvem [em oitavos]": str(dados[i]["oktaMin"]),
                    "Cobertura maxima de nuvem [em oitavos]": str(dados[i]["oktaMax"]),
                    "Altitude da nuvem [ft]": str(dados[i]["altitude"]),
                }
            )
        return dict_nuvem_condicao

    return "informacao ausente"


def cria_resultado_visibilidade(autoOunao, nuvem, visibilidade):
    """Classifica a visibilidade quando o observatorio e automatico.

    A checagem de nuvem usa `is None`/`is not None`; a versao anterior usava
    `str(nuvem)`, que nunca e None e tornava o segundo ramo inalcancavel.
    """

    if str(autoOunao) == "False" and nuvem is not None and str(visibilidade) == "9999":
        return "superior a 10000"
    if str(autoOunao) == "False" and nuvem is None and str(visibilidade) == "9999":
        return "10000"
    return visibilidade


def cria_dict_metar_traduzido(sigla, data, cod, mensagem):
    """Monta o JSON traduzido preservando chaves e ordem historicas."""

    vento = {
        "vento [KT]": cod.imprime_vento_VEL(),
        "rajada [KT]": cod.imprime_vento_RAJ(),
        "direcao_do_vento [graus]": cod.imprime_vento_DIR(),
        "coordenada_da_direcao_do_vento": cod.imprime_vento_DIR_COOR(),
        "variacao_do_vento": cod.imprime_vento_VAR(),
    }

    return {
        "data": [
            {
                "estacao": sigla,
                "data": data,
                "mensagem_metar": mensagem,
                "temperatura [C]": cod.imprime_temp(),
                "temperatura_pto_orvalho [C]": cod.imprime_tempPtoOrvalho(),
                "visibilidade [m]": cria_resultado_visibilidade(
                    cod.imprime_estAuto(), cod.imprime_nuvem(), cod.imprime_visi()
                ),
                "pressao_atmosferica [mb]": cod.imprime_PRES(),
                "condicao_nuvem": cria_dados_nuvem(cod.imprime_nuvem()),
                "vento": vento,
            }
        ]
    }


def grava_json_atomico(caminho, dados):
    """Grava `dados` como JSON, sobrescrevendo o destino atomicamente."""

    caminho = Path(caminho)
    temporario = caminho.with_name(caminho.name + ".tmp")

    try:
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except Exception:
        with suppress(FileNotFoundError):
            temporario.unlink()
        raise

    return caminho


def executa_estacoes(fabrica_metar, cria_dict, sufixo, referencia=None, diretorio=None):
    """Executa uma fabrica de METAR para todas as estacoes.

    `fabrica_metar` recebe o codigo ICAO e devolve um objeto com a interface de
    GoMETAR. `cria_dict` recebe (sigla, data, objeto, mensagem).
    """

    referencia = referencia or agora_utc()
    destino = Path(diretorio) if diretorio is not None else Path.cwd()
    destino.mkdir(parents=True, exist_ok=True)

    falhas = []
    for aerodromo in AERODROMOS.values():
        try:
            cod = fabrica_metar(aerodromo)
            sigla = cod.imprime_aerodromo()
            mensagem = cod.imprime_metar()
            data = resolve_data_metar(cod.imprime_data(), referencia)
            nome = "%s%s%s.json" % (sigla, data, sufixo)
            grava_json_atomico(destino / nome, cria_dict(sigla, data, cod, mensagem))
        except Exception as exc:  # uma estacao com falha nao impede as demais
            falhas.append("%s: %s" % (aerodromo, exc))

    if falhas:
        for falha in falhas:
            print("erro METAR: %s" % falha, file=sys.stderr)
        return 1

    return 0
