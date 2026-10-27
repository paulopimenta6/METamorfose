#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta os METAR e grava o JSON bruto (um objeto por arquivo)."""

from __future__ import annotations

import sys

from metar_common import cria_dict_metar_bruto, executa_estacoes


def _cria_dict(sigla, data, cod, mensagem):
    # Mantem a assinatura comum (sigla, data, cod, mensagem); o JSON bruto
    # depende apenas dos tres primeiros campos relevantes.
    return cria_dict_metar_bruto(sigla, data, mensagem)


def main(fabrica_metar=None, referencia=None, diretorio=None):
    if fabrica_metar is None:
        from GoMETAR import pegaMETAR as fabrica_metar

    return executa_estacoes(
        fabrica_metar,
        _cria_dict,
        sufixo="",
        referencia=referencia,
        diretorio=diretorio,
    )


if __name__ == "__main__":
    sys.exit(main())
