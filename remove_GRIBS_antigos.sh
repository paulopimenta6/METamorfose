#!/bin/bash
#
# Remove os GRIBs e produtos de uma data alvo (hoje - 2 dias).
# Remove as resolucoes 0p25 e 1p00, os arquivos legados e os diretorios de
# mapas/matrizes da mesma data. Dados de outras datas nao sao tocados.
#
# Variaveis de ambiente (opcionais, usadas em testes):
#   MET_BASE_DIR  diretorio base do servidor (padrao /media/MET/servidor_MET)
#   MET_HOJE      data de referencia AAAAMMDD (padrao: hoje)
#   MET_DATA_ALVO data alvo explicita AAAAMMDD (sobrepoe MET_HOJE)

set -euo pipefail

BASE_DIR="${MET_BASE_DIR:-/media/MET/servidor_MET}"
dir_gribs="${BASE_DIR}/gribs"
dir_mapas="${BASE_DIR}/mapasGrib"
dir_matrizes="${BASE_DIR}/matrizGrib"
dir_matrizes_bluesky="${BASE_DIR}/matrizGrib/bluesky"
dir_matrizes_predi="${BASE_DIR}/matrizGrib/predi"

calcula_data_alvo() {
    if [ -n "${MET_DATA_ALVO:-}" ]; then
        printf '%s\n' "${MET_DATA_ALVO}"
    elif [ -n "${MET_HOJE:-}" ]; then
        date -d "${MET_HOJE} -2 days" +"%Y%m%d"
    else
        date -d "-2 days" +"%Y%m%d"
    fi
}

valida_data() {
    case "${1}" in
        [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])
            ;;
        *)
            echo "erro: data alvo invalida: '${1}' (use AAAAMMDD)" >&2
            exit 2
            ;;
    esac
}

remove_gribs_do_dia() {
    local data_alvo="$1"
    local diretorio="${dir_gribs}/${data_alvo}"
    local tAnalise tPrev resolucao arquivo

    echo "==============================================================="
    echo "    verificando gribs    "
    echo "Data alvo: ${data_alvo}"

    if [ ! -d "${diretorio}" ]; then
        echo "O diretorio nao existe: ${diretorio}"
        return 0
    fi

    echo "Removendo GRIBs 0p25, 1p00 e legados de ${diretorio}"

    for tAnalise in 00 06 12 18; do
        [ -d "${diretorio}/${tAnalise}" ] || continue
        for tPrev in 00 06 12 18; do
            for resolucao in 0p25 1p00; do
                arquivo="${diretorio}/${tAnalise}/gfs.t${tAnalise}z.pgrb2.${resolucao}.f0${tPrev}"
                [ -e "${arquivo}" ] && rm -f -- "${arquivo}"
            done
        done
        find "${diretorio}/${tAnalise}" -maxdepth 1 -type f \
            -name 'gfs????????????_???.grb' -delete
    done

    find "${diretorio}" -maxdepth 1 -type f \
        -name 'gfs????????????_???.grb' -delete

    echo "==============================================================="
}

remove_diretorio() {
    local rotulo="$1"
    local caminho="$2"

    echo "==============================================================="
    echo "    verificando ${rotulo}    "
    echo "Data alvo: ${caminho##*/}"

    if [ -d "${caminho}" ]; then
        echo "Removendo ${caminho}"
        rm -rf -- "${caminho}"
    else
        echo "O diretorio nao existe: ${caminho}"
    fi

    echo "==============================================================="
}

main() {
    local data_alvo
    data_alvo="$(calcula_data_alvo)"
    valida_data "${data_alvo}"

    remove_gribs_do_dia "${data_alvo}"
    remove_diretorio "mapas" "${dir_mapas}/${data_alvo}"
    remove_diretorio "matrizes" "${dir_matrizes}/${data_alvo}"
    remove_diretorio "matrizes bluesky" "${dir_matrizes_bluesky}/${data_alvo}"
    remove_diretorio "matrizes predi" "${dir_matrizes_predi}/${data_alvo}"

    return 0
}

main "$@"
