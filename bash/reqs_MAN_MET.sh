#!/bin/bash
#
# Wrapper fino do CLI manual (MAN). Toda a validacao, o help e a geracao
# ficam em classes_MET/executa_reqs_param.py (argparse). Este script apenas
# encaminha os argumentos, sem depender de posicoes fixas.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/../classes_MET/executa_reqs_param.py"

if [ ! -f "${PYTHON_SCRIPT}" ]; then
    echo "erro: script Python nao encontrado: ${PYTHON_SCRIPT}" >&2
    exit 1
fi

exec python3 "${PYTHON_SCRIPT}" "$@"
