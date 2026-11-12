# Instalação do zero

Ao terminar este guia, você terá **12 GRIBs históricos, 1.098 tabelas CSV,
3 mapas PNG e scripts para testar o sistema**, em uma pasta da sua conta.

Execute **um bloco por vez**, no mesmo terminal Bash. Espere cada comando
terminar. Se houver erro, resolva-o antes de passar ao próximo bloco.
O download depende da conexão; a preparação pode levar vários minutos.

## 1. Preparar o computador

Ambiente de referência: **Linux x86-64, Bash e Python 3.11**. Reserve alguns GB
para dependências, dados e saídas. É necessário acesso à internet para Git,
pacotes Python e o arquivo público NOAA.

Em Debian/Ubuntu, as ferramentas básicas podem ser instaladas com:

```bash
sudo apt update
sudo apt install git curl python3 python3-venv python3-pip util-linux
python3 --version
```

`python3 --version` informa a versão fornecida pelo sistema. Este projeto foi
validado com **3.11**; se a distribuição fornecer outra versão, use um ambiente
Python 3.11 disponível na sua máquina. Por exemplo, se você já usa Conda:

```bash
conda create -n metamorfose python=3.11 -y
conda activate metamorfose
```

Os próximos passos criam uma `.venv` usando o `python3` escolhido.

## 2. Obter o projeto

```bash
mkdir -p "$HOME/Documentos/meus_codigos"
cd "$HOME/Documentos/meus_codigos"
git clone --branch execucao https://github.com/paulopimenta6/METamorfose.git
cd METamorfose
export REPO="$PWD"
export MET_ROOT="$HOME/MET/servidor_MET"
```

**Já tem o código?** Entre na pasta existente e execute apenas as duas linhas
`export` acima. A instalação usa o código presente nessa pasta.

O repositório contém o código e os registros históricos. Os GRIBs e a release
serão criados nos passos 5 e 6.

## 3. Instalar as dependências Python

```bash
cd "$REPO"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` instala as bibliotecas de execução e o pytest.
O pacote PythonMETAR é instalado a partir do código incluído no repositório.

Confira:

```bash
python3 -c 'import numpy, pygrib, matplotlib, mpl_toolkits.basemap, PythonMETAR; print("Dependencias OK")'
```

**Esperado:** `Dependencias OK`. A `.venv` precisa ser ativada em cada novo terminal.

## 4. Conferir o código com os testes portáveis

```bash
python3 -m pytest -q --ignore=tests/test_phase0_acceptance.py -m "not network"
```

**Esperado:** resumo com `passed`, sem `failed` ou `error`. Alguns testes reais
podem aparecer como `skipped` porque dependem da amostra específica da Fase 0.

A suíte `test_phase0_acceptance.py` exige o backup original e os remotos do
ambiente de desenvolvimento histórico. Por isso não faz parte deste comando
para um clone novo. A campanha real do passo 6 valida as amostras de 2022.

## 5. Baixar os dados históricos de teste

```bash
export MPLBACKEND=Agg
export PYTHONDONTWRITEBYTECODE=1
python3 reprocessamento/fetch_phase4_samples.py \
  --output reprocessamento/phase4-data
```

**Esperado ao final:**

```text
DONE 12 ERRORS 0
```

São dados de 15, 16 e 17/12/2022, ciclo 00 UTC, previsões f000/f006/f012/f018.
O script baixa apenas as mensagens necessárias à campanha. Se a conexão cair,
execute o mesmo comando novamente: ele confere e reutiliza os arquivos já
concluídos. Se indicar `hash do cache divergente`, use outra pasta em `--output`
e ajuste o caminho do manifesto no próximo passo.

Esse download histórico é específico da validação; a aquisição operacional
continua em `goGribV2.sh`.

## 6. Gerar, validar e empacotar os produtos

Crie um identificador para esta execução:

```bash
export RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
export CAMPAIGN="$REPO/reprocessamento/phase4-runs/$RUN_ID"
export CANDIDATE="$REPO/reprocessamento/releases/$RUN_ID"
python3 reprocessamento/phase4.py \
  --manifest reprocessamento/phase4-data/manifest.json \
  --output "$CAMPAIGN" --maps
```

**Esperado ao final:** JSON com `"status": "ok"`, `"products": 1101` e
`"pairs": 108`. São comparações numéricas dos CSVs com o GRIB, mais diagnóstico
com observações METAR históricas. Os PNGs são gerados; a inspeção visual é feita
no manual de execução.

Se precisar repetir a campanha, defina outro `RUN_ID` e recalcule `CAMPAIGN` e
`CANDIDATE` com o bloco acima. O comando exige uma pasta de saída nova.

Empacote a campanha que terminou com `status: ok`:

```bash
python3 reprocessamento/release_phase4.py build \
  --validation "$CAMPAIGN" --output "$CANDIDATE"
sha256sum "$CANDIDATE/release.json"
```

**Esperado:** um inventário JSON e uma linha com o SHA-256 de 64 caracteres.
Anote esse hash: ele identifica **a sua release**. Ele será diferente do hash
da candidata histórica `phase4-candidate`, pois a criação de um pacote novo
gera um manifesto novo.

## 7. Instalar o ambiente

```bash
python3 reprocessamento/setup_production_env.py \
  --root "$MET_ROOT" \
  --candidate "$CANDIDATE" \
  --samples "$REPO/reprocessamento/phase4-data"
```

**Esperado no resumo:**

```text
"gribs": 12,
"csv": 1098,
"png": 3,
"approved": false
```

O instalador confere as fontes antes de copiar. Se o destino já contém outra
release, escolha uma pasta nova, por exemplo:

```bash
export MET_ROOT="$HOME/MET/servidor_MET-$RUN_ID"
```

Depois repita o comando de instalação. O aceite de uma release anterior não
será reaproveitado.

## 8. Executar pela primeira vez

```bash
source "$MET_ROOT/bin/ativar.sh"
"$MET_ROOT/bin/verificar.sh"
```

**Esperado:** `falhas: 0`, `status: ok`, `state: pending`.

```bash
"$MET_ROOT/bin/testar_todos.sh"
```

**Esperado:** `Os tres testes tecnicos passaram`. Os caminhos dos resultados
aparecem no terminal. Continue no [manual de execução](15-manual-testes-de-execucao.md)
para inspecioná-los, e depois no [manual de aceitação](16-manual-de-aceitacao.md).

## Quando abrir um novo terminal

```bash
export REPO="$HOME/Documentos/meus_codigos/METamorfose"
export MET_ROOT="$HOME/MET/servidor_MET"
source "$REPO/.venv/bin/activate"
source "$MET_ROOT/bin/ativar.sh"
```

Ajuste `MET_ROOT` se escolheu uma pasta com sufixo. Depois da instalação,
`RUN_ID`, `CAMPAIGN` e `CANDIDATE` só são necessários para construir outra release.

## Se algo falhar

| Mensagem | Ação |
|---|---|
| `externally-managed-environment` no pip | Ative `.venv/bin/activate` e repita o pip. |
| `No module named ...` | Ative a `.venv` e instale `requirements-dev.txt` a partir de `$REPO`. |
| `No matching distribution found` | Confira Python 3.11 e a arquitetura. Em sistemas sem wheels, a instalação de pygrib exige ecCodes e ferramentas de compilação. |
| `DONE ... ERRORS ...` com erros | Confira a rede e repita o download até `DONE 12 ERRORS 0`. |
| `use um diretorio novo` | Defina outro `RUN_ID` para a campanha. |
| `release existente e imutavel` | Use um `CANDIDATE` novo; mantenha o pacote anterior. |
| `ambiente já existe` | Para atualizar scripts, use `--update-tools`; para outra release, escolha outro `MET_ROOT`. |
| `Permission denied` | Use a pasta dentro de `$HOME`, com a sua conta. |

O roteiro de produção diária e METAR está em [04-operacao.md](04-operacao.md).
O modo AUT usa os GRIBs do **dia atual**; para as amostras de 2022 use o modo
MAN descrito aqui e no manual de execução.
