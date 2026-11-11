#!/bin/bash
set -euo pipefail
LOCK_DIR="${MET_LOCK_DIR:-${TMPDIR:-/tmp}/metamorfose-${UID}}"
mkdir -p "${LOCK_DIR}"
exec 9>"${LOCK_DIR}/automatizacao_controle_MET.lock"
flock -n 9 || { echo "erro: execucao concorrente de automatizacao_controle_MET" >&2; exit 75; }


#/media/utrecht/12382BE468602ECF/goGrib/bash/automatizacao_matrizes.sh
dir_principal="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/"
dir_bash="bash"

data_ano=`date +"%Y"`
data_mes=`date +"%m"`
data_dia=`date +"%d"`

cd "${dir_principal}${dir_bash}"

#Criar estrutura de diretorio para abrigar os dados de acordo com a localizacao
#############################
# matrizes e mapas de vento #
#############################
./automatiza_vento_MET.sh "-v" "winds" "-ns" "-r" "SP"
./automatiza_vento_MET.sh "-v" "winds" "-ns" "-r" "RJ"

./automatiza_vento_MET.sh "-v" "wind" "-n" "1000" "-r" "SP"
./automatiza_vento_MET.sh "-v" "wind" "-n" "1000" "-r" "RJ"

./automatiza_vento_MET.sh "-v" "wind" "-n" "200" "-r" "SP"
./automatiza_vento_MET.sh "-v" "wind" "-n" "200" "-r" "RJ"

#############################
#   temperatura em niveis   #
#############################
./automatiza_MET.sh "-v" "temp" "-n" "1000" "-r" "SP"
./automatiza_MET.sh "-v" "temp" "-n" "1000" "-r" "RJ"

#################################
#   temperatura em superficie   #
#################################
./automatiza_MET.sh "-v" "temps" "-ns" "-r" "SP"
./automatiza_MET.sh "-v" "temps" "-ns" "-r" "RJ"

################################
# pressao em superficie e prnm #
################################
#./automatiza_MET.sh "-v" "ps" "-ns" "-r" "SP"
./automatiza_MET.sh "-v" "prnm" "-ns" "-r" "SP"
#./automatiza_MET.sh "-v" "ps" "-ns" "-r" "RJ"
./automatiza_MET.sh "-v" "prnm" "-ns" "-r" "RJ"

######################################
#     nuvem e umidade relativa       #
######################################
./automatiza_MET.sh "-v" "nuvem" "-n" "700" "-r" "SP"
./automatiza_MET.sh "-v" "nuvem" "-n" "500" "-r" "SP"
./automatiza_MET.sh "-v" "nuvem" "-n" "200" "-r" "SP"
./automatiza_MET.sh "-v" "umidadeRel" "-n" "850" "-r" "SP"

./automatiza_MET.sh "-v" "nuvem" "-n" "700" "-r" "RJ"
./automatiza_MET.sh "-v" "nuvem" "-n" "500" "-r" "RJ"
./automatiza_MET.sh "-v" "nuvem" "-n" "200" "-r" "RJ"
./automatiza_MET.sh "-v" "umidadeRel" "-n" "850" "-r" "RJ"

#############################
# matrizes e mapas de chuva #
#############################
./automatiza_MET.sh "-v" "chuvaConvec" "-ns" "-r" "SP"
./automatiza_MET.sh "-v" "chuvaConvec" "-ns" "-r" "RJ"
./automatiza_MET.sh "-v" "chuvaNaoConvec" "-ns" "-r" "SP"
./automatiza_MET.sh "-v" "chuvaNaoConvec" "-ns" "-r" "RJ"

exit 0
