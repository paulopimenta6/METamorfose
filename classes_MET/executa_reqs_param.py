#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov  6 02:27:07 2021

@author: phpimenta

CLI do fluxo manual (MAN). As flags historicas foram preservadas, mas a
validacao passou a ser feita por argparse e o codigo de saida e sempre
diferente de zero quando a chamada e invalida.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# =============================================================================
# Catalogo de variaveis e niveis
# =============================================================================

NIVEIS_HPA = (
    150, 200, 250, 300, 350, 400, 450, 500, 550, 600,
    650, 700, 750, 800, 850, 900, 925, 950, 975, 1000,
)

VARIAVEIS_SUPERFICIE = (
    "ps", "prnm", "temps", "chuvaConvec", "chuvaNaoConvec",
)
VARIAVEIS_PRESSAO = (
    "temp", "nuvem", "umidadeRel", "u", "v",
)
VARIAVEIS_VENTO = ("wind", "winds")
VARIAVEIS_VALIDAS = VARIAVEIS_SUPERFICIE + VARIAVEIS_PRESSAO + VARIAVEIS_VENTO

ANALISES_PREVISOES = ("00", "06", "12", "18")


# =============================================================================
# Funcoes base
# =============================================================================

def converte_feet_to_hPa(halt):
    """Converte altitude em pes para pressao em hPa (formula barometrica)."""

    return ((1 - (float(halt) / 145366.45)) ** (1 / 0.19028)) * 1013.25


def validada_data(data):
    """Valida AAAAMMDD + analise + previsao e devolve os campos separados."""

    if not isinstance(data, str):
        raise ValueError("data invalida: use o formato AAAAMMDDAAANAPR")
    if len(data) != 12 or not data.isdigit():
        raise ValueError(
            "data invalida: %r; use 12 digitos no formato AAAAMMDDAAANAPR "
            "(por exemplo, 202111020006)" % (data,)
        )

    try:
        datetime.strptime(data[0:8], "%Y%m%d")
    except ValueError as exc:
        raise ValueError("data invalida: %s (%s)" % (data, exc)) from exc

    ano = data[0:4]
    mes = data[4:6]
    dia = data[6:8]
    ana = data[8:10]
    prev = data[10:12]

    if ana not in ANALISES_PREVISOES:
        raise ValueError(
            "analise invalida: %r; use uma de: %s"
            % (ana, ", ".join(ANALISES_PREVISOES))
        )
    if prev not in ANALISES_PREVISOES:
        raise ValueError(
            "previsao invalida: %r; use uma de: %s"
            % (prev, ", ".join(ANALISES_PREVISOES))
        )

    return ano, mes, dia, ana, prev


def define_nivel(nivel):
    """Arredonda um nivel para o valor suportado mais proximo (em hPa)."""

    try:
        valor = float(nivel)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "nivel invalido: %r; use um numero entre %d e %d hPa"
            % (nivel, NIVEIS_HPA[0], NIVEIS_HPA[-1])
        ) from exc

    if not NIVEIS_HPA[0] <= valor <= NIVEIS_HPA[-1]:
        raise ValueError(
            "nivel fora da faixa suportada (%d a %d hPa): %s"
            % (NIVEIS_HPA[0], NIVEIS_HPA[-1], nivel)
        )

    for i in range(len(NIVEIS_HPA) - 1):
        inferior = NIVEIS_HPA[i]
        superior = NIVEIS_HPA[i + 1]
        if inferior <= valor < superior:
            media = (inferior + superior) / 2
            return superior if valor >= media else inferior

    return NIVEIS_HPA[-1]


def cria_intervalo_niveis(nivelminConvertido, nivelmaxConvertido):
    """Devolve os niveis entre os dois extremos, sempre em ordem crescente.

    Aceita tanto 200->500 quanto 500->200. Niveis iguais devolvem um unico
    elemento. Valores fora da faixa suportada levantam ValueError.
    """

    nivelmin = define_nivel(nivelminConvertido)
    nivelmax = define_nivel(nivelmaxConvertido)
    i0, i1 = sorted((NIVEIS_HPA.index(nivelmin), NIVEIS_HPA.index(nivelmax)))
    return list(NIVEIS_HPA[i0:i1 + 1])


# =============================================================================
# CLI
# =============================================================================

def cria_parser():
    # O texto de ajuda e montado a partir do catalogo para nao divergir das
    # constantes usadas na validacao.
    epilogo = """\
variaveis:
  superficie : %s  (use -ns)
  pressao    : %s  (use -nhpa/-nf)
  vento      : %s (pressao), %s (superficie, use -ns)

niveis de pressao suportados (hPa):
  %s

exemplos:
  %s -v winds -ns -lonmin -56 -lonmax -42 -latmin -28 -latmax -18 \\
      -datetime 202111020006 -out /home/phpimenta/
  %s -v temp -nhpa 500 -lonmin 3.75 -lonmax 6 -latmin 8 -latmax 9 \\
      -datetime 202111020006 -out /home/phpimenta/
  %s -v temp -altminhpa 500 -altmaxhpa 200 -lonmin 3.75 -lonmax 6 \\
      -latmin 8 -latmax 9 -datetime 202111020006 -out /home/phpimenta/
""" % (
        ", ".join(VARIAVEIS_SUPERFICIE),
        ", ".join(VARIAVEIS_PRESSAO),
        VARIAVEIS_VENTO[0],
        VARIAVEIS_VENTO[1],
        ", ".join(str(n) for n in NIVEIS_HPA),
        "%(prog)s",
        "%(prog)s",
        "%(prog)s",
    )

    parser = argparse.ArgumentParser(
        prog="reqs_MAN_MET.sh",
        description="Gera mapas e matrizes MAN a partir dos GRIBs GFS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilogo,
    )

    parser.add_argument("-v", "--variavel", required=True,
                        help="variavel MET (veja a lista no fim do help)")
    parser.add_argument("-lonmin", type=float, required=True,
                        help="longitude minima (-180 a 180)")
    parser.add_argument("-lonmax", type=float, required=True,
                        help="longitude maxima (-180 a 180)")
    parser.add_argument("-latmin", type=float, required=True,
                        help="latitude minima (-90 a 90)")
    parser.add_argument("-latmax", type=float, required=True,
                        help="latitude maxima (-90 a 90)")

    parser.add_argument("-ns", action="store_true",
                        help="nivel de superficie")
    parser.add_argument("-nhpa", type=float,
                        help="nivel de pressao em hPa")
    parser.add_argument("-nf", type=float,
                        help="altitude em pes (convertida para hPa)")
    parser.add_argument("-altminhpa", type=float,
                        help="primeiro extremo do intervalo em hPa")
    parser.add_argument("-altmaxhpa", type=float,
                        help="segundo extremo do intervalo em hPa")
    parser.add_argument("-altminfeet", type=float,
                        help="primeiro extremo do intervalo em pes")
    parser.add_argument("-altmaxfeet", type=float,
                        help="segundo extremo do intervalo em pes")

    parser.add_argument("-datetime", required=True,
                        help="AAAAMMDD + analise + previsao (12 digitos)")
    parser.add_argument("-out", required=True,
                        help="diretorio existente para mapas e matrizes")
    return parser


def _erro(parser, mensagem):
    parser.error(mensagem)


def valida_argumentos(parser, args):
    """Valida a combinacao de flags e normaliza o diretorio de saida."""

    variavel = args.variavel

    if variavel == "chuva":
        _erro(parser, "variavel 'chuva' nao existe; use 'chuvaConvec' ou 'chuvaNaoConvec'")
    if variavel not in VARIAVEIS_VALIDAS:
        _erro(
            parser,
            "variavel desconhecida: %r; use uma de: %s"
            % (variavel, ", ".join(VARIAVEIS_VALIDAS)),
        )

    if not (args.lonmin < args.lonmax):
        _erro(parser, "-lonmin deve ser menor que -lonmax")
    if not (args.latmin < args.latmax):
        _erro(parser, "-latmin deve ser menor que -latmax")
    if not (-180 <= args.lonmin <= 180 and -180 <= args.lonmax <= 180):
        _erro(parser, "longitudes devem estar entre -180 e 180")
    if not (-90 <= args.latmin <= 90 and -90 <= args.latmax <= 90):
        _erro(parser, "latitudes devem estar entre -90 e 90")

    try:
        validada_data(args.datetime)
    except ValueError as exc:
        _erro(parser, str(exc))

    intervalo_hpa = args.altminhpa is not None or args.altmaxhpa is not None
    intervalo_feet = args.altminfeet is not None or args.altmaxfeet is not None

    if (args.altminhpa is None) != (args.altmaxhpa is None):
        _erro(parser, "-altminhpa e -altmaxhpa devem ser informados juntos")
    if (args.altminfeet is None) != (args.altmaxfeet is None):
        _erro(parser, "-altminfeet e -altmaxfeet devem ser informados juntos")

    modos = sum((
        bool(args.ns),
        args.nhpa is not None,
        args.nf is not None,
        intervalo_hpa,
        intervalo_feet,
    ))
    if modos != 1:
        _erro(
            parser,
            "informe exatamente um modo de nivel: -ns, -nhpa, -nf, "
            "-altminhpa/-altmaxhpa ou -altminfeet/-altmaxfeet",
        )

    if variavel in VARIAVEIS_SUPERFICIE and not args.ns:
        _erro(parser, "a variavel %r e de superficie; use -ns" % variavel)
    if variavel == "winds" and not args.ns:
        _erro(parser, "'winds' e vento superficial; use -ns")
    if variavel == "wind" and args.ns:
        _erro(parser, "'wind' e vento em nivel de pressao; use -nhpa, -nf ou intervalo")
    if variavel in VARIAVEIS_PRESSAO and args.ns:
        if variavel == "umidadeRel":
            _erro(
                parser,
                "umidadeRel nao possui campo em superficie; use -nhpa 850",
            )
        _erro(parser, "a variavel %r nao possui campo em superficie; use -nhpa" % variavel)

    if variavel in ("winds",) and (intervalo_hpa or intervalo_feet):
        _erro(parser, "'winds' nao aceita intervalo de niveis de pressao; use -ns")

    if args.nhpa is not None:
        try:
            define_nivel(args.nhpa)
        except ValueError as exc:
            _erro(parser, str(exc))
    if args.nf is not None:
        if not 0 < args.nf <= 145000:
            _erro(parser, "-nf deve estar entre 0 e 145000 pes")
        try:
            define_nivel(converte_feet_to_hPa(args.nf))
        except ValueError as exc:
            _erro(parser, "altitude em pes invalida: %s" % exc)

    if intervalo_hpa:
        try:
            cria_intervalo_niveis(args.altminhpa, args.altmaxhpa)
        except ValueError as exc:
            _erro(parser, str(exc))
    if intervalo_feet:
        if not (0 < args.altminfeet <= 145000 and 0 < args.altmaxfeet <= 145000):
            _erro(parser, "altitudes em pes devem estar entre 0 e 145000")
        try:
            cria_intervalo_niveis(
                converte_feet_to_hPa(args.altminfeet),
                converte_feet_to_hPa(args.altmaxfeet),
            )
        except ValueError as exc:
            _erro(parser, "intervalo em pes invalido: %s" % exc)

    saida = Path(args.out).expanduser()
    if not saida.exists():
        _erro(parser, "diretorio de saida nao existe: %s" % saida)
    if not saida.is_dir():
        _erro(parser, "o caminho de saida nao e um diretorio: %s" % saida)
    if not os.access(saida, os.W_OK):
        _erro(parser, "sem permissao de escrita no diretorio de saida: %s" % saida)
    args.out = str(saida.resolve()) + os.sep


def _niveis_para_execucao(args):
    """Devolve (modo, nivel_ou_lista) a partir das flags ja validadas."""

    if args.ns:
        return "surface", "surface"
    if args.nhpa is not None:
        return "single", define_nivel(args.nhpa)
    if args.nf is not None:
        return "single", define_nivel(converte_feet_to_hPa(args.nf))
    if args.altminhpa is not None:
        return "interval", cria_intervalo_niveis(args.altminhpa, args.altmaxhpa)

    return "interval", cria_intervalo_niveis(
        converte_feet_to_hPa(args.altminfeet),
        converte_feet_to_hPa(args.altmaxfeet),
    )


def _gera_vento(varMET, coords, data, saida, modo, nivel):
    from gera_mapas_vento_MAN_MET import met_gera_mapas_vento_man
    from gera_matriz_vento_MAN_MET import met_gera_matriz_vento_man

    lonmin, lonmax, latmin, latmax = coords
    ano, mes, dia, ana, prev = data

    def mapas(nivel_atual):
        met_gera_mapas_vento_man(
            varMET, lonmin, lonmax, latmin, latmax,
            ano, mes, dia, ana, prev, saida, nivel_atual,
        ).processamento_dados_e_gerador_mapas()

    def matrizes(nivel_atual):
        met_gera_matriz_vento_man(
            varMET, lonmin, lonmax, latmin, latmax,
            ano, mes, dia, ana, prev, saida, nivel_atual,
        ).processamento_dados_e_gerador_matrizes()

    if modo == "surface":
        mapas(nivel)
        matrizes(nivel)
    elif modo == "single":
        mapas(nivel)
        matrizes(nivel)
    else:
        # O fluxo historico gera somente mapas para intervalos de vento.
        for nivel_atual in nivel:
            mapas(nivel_atual)


def _gera_escalar(varMET, coords, data, saida, modo, nivel):
    from gera_mapas_MAN_MET import met_gera_mapas_man
    from gera_matriz_MAN_MET import met_gera_matriz_man

    lonmin, lonmax, latmin, latmax = coords
    ano, mes, dia, ana, prev = data

    def mapas(nivel_atual):
        met_gera_mapas_man(
            varMET, lonmin, lonmax, latmin, latmax,
            ano, mes, dia, ana, prev, saida, nivel_atual,
        ).gera_mapas_final()

    def matrizes(nivel_atual):
        met_gera_matriz_man(
            varMET, lonmin, lonmax, latmin, latmax,
            ano, mes, dia, ana, prev, saida, nivel_atual,
        ).gera_matriz_final()

    if modo == "surface":
        mapas(nivel)
        matrizes(nivel)
    elif modo == "single":
        mapas(nivel)
        matrizes(nivel)
    else:
        for nivel_atual in nivel:
            mapas(nivel_atual)
            matrizes(nivel_atual)


def main(argv=None):
    parser = cria_parser()
    args = parser.parse_args(argv)
    valida_argumentos(parser, args)

    # Os geradores usam controla_env, que le ../environment/path.conf. Executar
    # a partir de classes_MET mantem o contrato historico de caminho relativo.
    os.chdir(Path(__file__).resolve().parent)

    try:
        from poligono_regiao_MET import met_poligono_regiao

        data = validada_data(args.datetime)
        coords = met_poligono_regiao(
            args.lonmin, args.lonmax, args.latmin, args.latmax
        ).cria_poligono()
        if coords is None:
            raise ValueError("regiao invalida: verifique longitude e latitude")
        modo, nivel = _niveis_para_execucao(args)

        if args.variavel in VARIAVEIS_VENTO:
            _gera_vento(args.variavel, coords, data, args.out, modo, nivel)
        else:
            _gera_escalar(args.variavel, coords, data, args.out, modo, nivel)
    except (ValueError, FileNotFoundError, KeyError, OSError) as exc:
        print("Erro: %s" % exc, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
