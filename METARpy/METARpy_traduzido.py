#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta os METAR e grava o JSON traduzido (um objeto por arquivo)."""

from __future__ import annotations

import sys

from metar_common import (
    cria_dict_metar_traduzido,
    executa_estacoes,
)


def _cria_dict(sigla, data, cod, mensagem):
    return cria_dict_metar_traduzido(sigla, data, cod, mensagem)


def main(fabrica_metar=None, referencia=None, diretorio=None):
    if fabrica_metar is None:
        from GoMETAR import pegaMETAR as fabrica_metar

    return executa_estacoes(
        fabrica_metar,
        _cria_dict,
        sufixo="_traduzido",
        referencia=referencia,
        diretorio=diretorio,
    )


if __name__ == "__main__":
    sys.exit(main())
