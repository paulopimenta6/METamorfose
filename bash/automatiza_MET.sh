#!/bin/bash
#
# Wrapper do fluxo automatico (AUT): mapas e matrizes escalares.
# Preserva as flags historicas (-v, -n, -ns, -r, -ll), mas valida a chamada
# antes de executar o Python. Qualquer erro retorna codigo diferente de zero.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLASSES_DIR="${SCRIPT_DIR}/../classes_MET"

VARIAVEIS_VALIDAS="ps prnm temp temps nuvem chuvaNaoConvec chuvaConvec umidadeRel u v"
VARIAVEIS_SUPERFICIE="ps prnm temps chuvaNaoConvec chuvaConvec"
REGIOES_VALIDAS="SP RJ AM DF PR RS MG PA PE CE SA"

uso() {
    cat <<'EOF'
Uso: automatiza_MET.sh -v VARIAVEL (-n NIVEL | -ns) (-r REGIAO | -ll LON LAT)

Gera mapas e matrizes do fluxo automatico (AUT) a partir dos GRIBs GFS.

Opcoes:
  -h, --help       Mostra esta ajuda.
  -v VARIAVEL      Variavel MET (obrigatoria).
  -n NIVEL         Nivel de pressao em hPa.
  -ns              Nivel de superficie.
  -r REGIAO        Regiao predefinida.
  -ll LON LAT      Regiao definida por longitude e latitude.

Variaveis de superficie (use -ns):
  ps, prnm, temps, chuvaNaoConvec, chuvaConvec

Variaveis em nivel de pressao (use -n):
  temp, nuvem, umidadeRel, u, v

Regioes:
  SP RJ AM DF PR RS MG PA PE CE SA

Exemplos:
  ./automatiza_MET.sh -v temp -n 1000 -r SP
  ./automatiza_MET.sh -v temps -ns -r RJ
  ./automatiza_MET.sh -v temp -n 500 -ll -56 -30
EOF
}

erro() {
    echo "erro: $*" >&2
    echo "use -h para ver o menu de ajuda" >&2
    exit 2
}

contem() {
    local alvo="$1"
    local lista="$2"
    local item
    for item in ${lista}; do
        [ "${item}" = "${alvo}" ] && return 0
    done
    return 1
}

validalidade_numero() {
    local valor="$1"
    local nome="$2"
    case "${valor}" in
        ''|*[!0-9]*)
            erro "${nome} deve ser um numero inteiro (recebido: '${valor}')"
            ;;
    esac
}

validalidade_coordenada() {
    local valor="$1"
    local nome="$2"
    if ! [[ "${valor}" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
        erro "${nome} deve ser numerico (recebido: '${valor}')"
    fi
}

# -----------------------------------------------------------------------------
# Ajuda e argumentos
# -----------------------------------------------------------------------------
if [ "$#" -eq 0 ]; then
    uso
    exit 2
fi

case "${1}" in
    -h|--help)
        uso
        exit 0
        ;;
esac

variavel=""
modo_nivel=""
nivel=""
regiao=""
lon=""
lat=""

while [ "$#" -gt 0 ]; do
    case "${1}" in
        -v)
            [ "$#" -ge 2 ] || erro "-v exige um valor"
            variavel="${2}"
            shift 2
            ;;
        -n)
            [ "$#" -ge 2 ] || erro "-n exige um valor"
            modo_nivel="pressao"
            nivel="${2}"
            shift 2
            ;;
        -ns)
            modo_nivel="superficie"
            shift
            ;;
        -r)
            [ "$#" -ge 2 ] || erro "-r exige um valor"
            regiao="${2}"
            shift 2
            ;;
        -ll)
            [ "$#" -ge 3 ] || erro "-ll exige longitude e latitude"
            lon="${2}"
            lat="${3}"
            shift 3
            ;;
        -h|--help)
            uso
            exit 0
            ;;
        *)
            erro "opcao desconhecida: '${1}'"
            ;;
    esac
done

[ -n "${variavel}" ] || erro "informe a variavel com -v"
[ -n "${modo_nivel}" ] || erro "informe o nivel com -n ou -ns"
if [ -n "${regiao}" ] && [ -n "${lon}" ]; then
    erro "use apenas uma forma de regiao: -r ou -ll"
fi
if [ -z "${regiao}" ] && [ -z "${lon}" ]; then
    erro "informe a regiao com -r ou -ll"
fi

# -----------------------------------------------------------------------------
# Validacao semantica
# -----------------------------------------------------------------------------
if ! contem "${variavel}" "${VARIAVEIS_VALIDAS}"; then
    if [ "${variavel}" = "chuva" ]; then
        erro "variavel 'chuva' nao existe; use 'chuvaConvec' ou 'chuvaNaoConvec'"
    fi
    if [ "${variavel}" = "wind" ] || [ "${variavel}" = "winds" ]; then
        erro "vento deve ser processado por automatiza_vento_MET.sh"
    fi
    erro "variavel desconhecida: '${variavel}'; use uma de: ${VARIAVEIS_VALIDAS}"
fi

if contem "${variavel}" "${VARIAVEIS_SUPERFICIE}"; then
    [ "${modo_nivel}" = "superficie" ] || erro "a variavel '${variavel}' e de superficie; use -ns"
else
    if [ "${modo_nivel}" = "superficie" ]; then
        if [ "${variavel}" = "umidadeRel" ]; then
            erro "umidadeRel nao possui campo em superficie; use -n <hPa> (por exemplo, -n 850)"
        fi
        erro "a variavel '${variavel}' nao possui campo em superficie; use -n <hPa>"
    fi
fi

if [ "${modo_nivel}" = "pressao" ]; then
    validalidade_numero "${nivel}" "nivel"
    [ "${nivel}" -ge 1 ] && [ "${nivel}" -le 1000 ] || erro "nivel deve estar entre 1 e 1000 hPa"
fi

if [ -n "${regiao}" ]; then
    regiao_upper="$(echo "${regiao}" | tr '[:lower:]' '[:upper:]')"
    if ! contem "${regiao_upper}" "${REGIOES_VALIDAS}"; then
        if [ "${regiao_upper}" = "MN" ]; then
            erro "regiao 'MN' nao existe; para Manaus use 'AM'"
        fi
        erro "regiao desconhecida: '${regiao}'; use uma de: ${REGIOES_VALIDAS}"
    fi
    regiao="${regiao_upper}"
else
    validalidade_coordenada "${lon}" "longitude"
    validalidade_coordenada "${lat}" "latitude"
    awk -v lon="${lon}" -v lat="${lat}" 'BEGIN {
        if (lon < -180 || lon > 180) exit 1
        if (lat < -90 || lat > 90) exit 2
    }' || erro "coordenadas fora da faixa: longitude -180..180, latitude -90..90"
fi

# -----------------------------------------------------------------------------
# Execucao
# -----------------------------------------------------------------------------
cd "${CLASSES_DIR}"

if [ -n "${regiao}" ]; then
    if [ "${modo_nivel}" = "superficie" ]; then
        argumentos=(-v "${variavel}" -ns -r "${regiao}")
    else
        argumentos=(-v "${variavel}" -n "${nivel}" -r "${regiao}")
    fi
else
    if [ "${modo_nivel}" = "superficie" ]; then
        argumentos=(-v "${variavel}" -ns -ll "${lon}" "${lat}")
    else
        argumentos=(-v "${variavel}" -n "${nivel}" -ll "${lon}" "${lat}")
    fi
fi

echo "AUT: ${argumentos[*]}"
python3 gera_mapas_MET.py "${argumentos[@]}"
python3 gera_matriz_MET.py "${argumentos[@]}"
