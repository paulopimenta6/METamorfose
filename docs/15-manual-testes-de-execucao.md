# Testar e executar o METamorfose

Este roteiro confere a instalação e gera produtos reais para BlueSky, preditor
e planilhas. Ao final, você terá os caminhos dos CSVs, mapas e logs.

**Ainda não instalou?** Comece pela [instalação do zero](17-instalacao-do-zero.md).
Os comandos abaixo pressupõem uma release já instalada em `MET_ROOT`.

## 1. Preparar o terminal

Abra o terminal Bash. Ajuste os caminhos se necessário:

```bash
export REPO="$HOME/Documentos/meus_codigos/METamorfose"
export MET_ROOT="$HOME/MET/servidor_MET"
cd "$REPO"
```

Se usou a instalação do zero, ative o Python:

```bash
source "$REPO/.venv/bin/activate"
```

Se já usa Conda, ative o ambiente em que instalou `requirements-dev.txt`.
Confira o Python escolhido:

```bash
python3 -c 'import numpy, pygrib, matplotlib, mpl_toolkits.basemap; print("Dependencias OK")'
```

**Esperado:** `Dependencias OK`.

## 2. Atualizar as ferramentas do ambiente

Execute a partir do código atualizado do projeto:

```bash
python3 reprocessamento/setup_production_env.py --root "$MET_ROOT" --update-tools
```

**Esperado:** `Ferramentas e manuais atualizados` e `Release preservada: <hash>`.
A operação atualiza `tools/`, `bin/`, `docs/`, `LEIA-ME.md` e os READMEs. Código candidato,
GRIBs, produtos, configuração, logs e aceite são preservados.

## 3. Ativar e verificar

```bash
source "$MET_ROOT/bin/ativar.sh"
"$MET_ROOT/bin/verificar.sh"
```

`source` mantém as variáveis no terminal atual. Antes da promoção, `Codigo ativo`
termina em `/app`. Depois da promoção, mostra `releases/<hash curto>/code`.

Para a campanha padrão, espere:

```text
gribs: 12
csv: 1098
png: 3
arquivos verificados: 1140
falhas: 0
status: ok
```

O verificador confere também a cópia imutável da candidata e a release ativa,
quando houver. Em seguida, verifica três contratos e o aceite:

| Bloco | Arquivos esperados na campanha padrão |
|---|---:|
| `bluesky` | 324 |
| `preditor` | 324 |
| `planilhas` | 450 |

Todos devem terminar com `falhas: 0` e `status: ok`. No último bloco,
`state: pending` é normal até a assinatura humana. A contagem de arquivos de
código pode mudar em releases futuras; o inventário da própria release é a referência.

## 4. Gerar as três amostras

```bash
"$MET_ROOT/bin/testar_todos.sh"
```

O script executa as três gerações em sequência e para se alguma falhar.
**Espere terminar antes de executar outro teste:** os geradores compartilham locks.

**Esperado ao final:**

```text
Os tres testes tecnicos passaram. Logs em .../logs
```

Cada teste mostra o SHA-256 da candidata, `codigo em teste: .../app`, o CSV
gerado, a pasta `Saida MAN` e o `Log local`. Uma pasta nova é criada a cada
execução, inclusive quando dois testes começam no mesmo segundo.

Você também pode executar um teste individualmente:

```bash
"$MET_ROOT/bin/testar_bluesky.sh"
```

```bash
"$MET_ROOT/bin/testar_preditor.sh"
```

```bash
"$MET_ROOT/bin/testar_planilhas.sh"
```

### O que cada comando gera

Todos usam **15/12/2022, ciclo 00 UTC, previsão f000**, na área definida no script.

| Teste | Variável/nível | CSV a usar na pasta `Saida MAN` |
|---|---|---|
| BlueSky | `wind`, 200 hPa | `matriz_vento_bluesky_..._N200_...csv` |
| Preditor | `wind`, 500 hPa | `matriz_vento_predi_..._N500_...csv` |
| Planilhas | `temp`, 850 hPa | `GFS_..._N850_temp_...csv` |

Os testes de vento também geram outras matrizes e três mapas cada. Use o CSV indicado
para a família desejada. O teste de planilhas gera **somente temperatura**;
nuvem, chuva, pressão e demais escalares devem ser conferidos nos produtos da release.

Nos mapas de vento, a escala é **m/s**. No CSV BlueSky, a resultante é em
**nós**; confira a unidade indicada no produto que estiver analisando.

Os testes `testar_*` executam o código candidato em `app/` mesmo depois de um
rollback. Assim, o log sempre identifica a versão que está sendo avaliada.

## 5. Abrir e inspecionar os arquivos

Liste os arquivos criados:

```bash
find "$MET_ROOT/aceitacao-manual" -type f \( -name '*.csv' -o -name '*.png' \)
```

O caminho exato do CSV também aparece após `CSV gerado para ...` no log.
Nomes MAN contêm espaços: mantenha o caminho inteiro entre aspas ao usá-lo.

Abra os PNGs no visualizador de imagens. Confira região, orientação,
nível e horário do título. Nos CSVs, confira cabeçalho e números conforme o
[manual de aceitação](16-manual-de-aceitacao.md). Para planilhas, importe com
**vírgula como separador** e **ponto como separador decimal**.

Os logs ficam em `$MET_ROOT/logs/`. As pastas começam com `bluesky-`,
`preditor-` e `planilhas-`, seguidas de data UTC e sufixo único.

## 6. Fazer uma requisição MAN própria

Este exemplo usa a release ativa, cria uma pasta nova e gera temperatura em
850 hPa para uma data disponível na instalação padrão:

```bash
OUT="$(mktemp -d "$MET_ROOT/aceitacao-manual/temperatura-XXXXXX")"
bash "$MET_ACTIVE_CODE/bash/reqs_MAN_MET.sh" \
  -v temp -nhpa 850 \
  -lonmin -51.75 -lonmax -41.5 -latmin -28.25 -latmax -17.75 \
  -datetime 202212150000 -out "$OUT"
find "$OUT" -maxdepth 1 -type f
```

`-datetime` é **AAAAMMDDCCPP**: data, ciclo e horas de previsão. No exemplo,
`20221215` + `00` + `00`. Para f006 do mesmo ciclo, use `202212150006`.
`-out` precisa ser um diretório existente; `mktemp -d` o cria.

Para ver todas as opções:

```bash
bash "$MET_ACTIVE_CODE/bash/reqs_MAN_MET.sh" --help
```

O modo AUT escolhe os dados do dia atual. Para as amostras históricas,
continue usando MAN. A operação diária está no [guia operacional](04-operacao.md).

## 7. Testes automatizados do código

Na pasta do repositório, com o Python ativado:

```bash
cd "$REPO"
python3 -m pytest -q --ignore=tests/test_phase0_acceptance.py -m "not network"
```

Esse é o comando portável para clones novos. A suíte completa histórica
(`python3 -m pytest -q`) também exige backup original, amostra da Fase 0 e
remotos Git específicos; veja [tests/README.md](../tests/README.md).

| Resultado | Significado |
|---|---|
| `passed` | Teste executado com sucesso |
| `failed` / `error` | Falha que precisa ser investigada |
| `skipped` | Teste não executado; confira a razão com `-ra` |
| `deselected` | Teste excluído pela seleção usada |
| `state: pending` | Falta assinar o aceite |

## Problemas comuns

| Mensagem | Ação |
|---|---|
| `ambiente incompleto` / `release.json ausente` | Confira `MET_ROOT`; se ainda não instalou, siga o guia do zero. |
| `hash divergente` | Identifique o arquivo listado. A cópia instalada deve corresponder à candidata; atualizar ferramentas não repara dados. |
| `execucao concorrente`, saída 75 | Espere o outro gerador terminar e repita. |
| `current/release ativa invalida` | Confira o destino de `readlink "$MET_ROOT/current"` e a integridade da release apontada. |
| `No module named ...` | Ative o mesmo Python em que instalou as dependências. |
| `state: pending`, `status: ok` | Esperado antes do aceite; prossiga com os testes. |

Quando os testes técnicos passarem e você conferir os arquivos, siga para
[aceitação dos resultados](16-manual-de-aceitacao.md).
