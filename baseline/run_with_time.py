#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Executa um script de produção com `time.localtime()` fixado.

Uso:
    python3 baseline/run_with_time.py 2026-10-22T01:00 gera_matriz_MET.py -v temp -n 850 -r SP

O script é executado no diretório corrente. O wrapper existe porque o código
atual lê a data/ciclo diretamente de `time.localtime()`.
"""

from __future__ import annotations

import os
import runpy
import sys
from datetime import datetime
from unittest.mock import patch


def parse_when(value: str):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M")


def main(argv):
    if len(argv) < 3:
        print(
            "uso: run_with_time.py AAA-MM-DDTHH:MM SCRIPT [args...]",
            file=sys.stderr,
        )
        return 2

    when = parse_when(argv[1])
    script = argv[2]
    script_args = argv[3:]
    fixed = when.timetuple()

    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.path.insert(0, os.getcwd())
    sys.argv = [script] + script_args

    with patch("time.localtime", return_value=fixed):
        runpy.run_path(script, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
