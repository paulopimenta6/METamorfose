#!/bin/bash
#
# Wrapper fino do CLI manual (MAN). Toda a validacao, o help e a geracao
# ficam em classes_MET/executa_reqs_param.py (argparse). Este script apenas
# encaminha os argumentos, sem depender de posicoes fixas.

set -euo pipefail
LOCK_DIR="${MET_LOCK_DIR:-${TMPDIR:-/tmp}/metamorfose-${UID}}"
mkdir -p "${LOCK_DIR}"
exec 8>"${LOCK_DIR}/products.lock"
flock -n -s 8 || { echo "erro: geracao/limpeza em andamento" >&2; exit 75; }
exec 9>"${LOCK_DIR}/reqs_MAN_MET.lock"
flock -n 9 || { echo "erro: execucao concorrente de reqs_MAN_MET" >&2; exit 75; }


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/../classes_MET/executa_reqs_param.py"

if [ ! -f "${PYTHON_SCRIPT}" ]; then
    echo "erro: script Python nao encontrado: ${PYTHON_SCRIPT}" >&2
    exit 1
fi

exec python3 "${PYTHON_SCRIPT}" "$@"
