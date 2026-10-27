#!/bin/bash
#
# Coleta os METAR de todas as estacoes e grava um JSON bruto e um traduzido.
# A referencia UTC e calculada uma unica vez e compartilhada com o Python,
# garantindo que diretorio e nomes de arquivo usem o mesmo instante.

set -euo pipefail

REFERENCIA_UTC="${METAR_REFERENCIA_UTC:-$(date -u +%Y%m%d%H%M)}"
export METAR_REFERENCIA_UTC="${REFERENCIA_UTC}"

dir="${METAR_BASE_DIR:-/media/MET/servidor_MET/METARpy}"
dirMetarJson="${dir}/${REFERENCIA_UTC:0:8}"

mkdir -p "${dir}" "${dirMetarJson}"
cd "${dirMetarJson}"

echo "Coletando METAR com referencia UTC ${REFERENCIA_UTC}"
python3 ../METARpy.py
python3 ../METARpy_traduzido.py
