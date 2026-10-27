# 10 — Resultados da Fase 2

**Branch:** `execucao` (worktree `METamorfose`)  
**Commit base:** `9288c1f`  
**Data da execução:** 27/10/2026  
**Escopo:** C-06, C-07 e itens D-05, D-07, D-08, D-09, D-10, D-13, D-14,
D-15, D-17, D-24, D-25, D-27 e D-28 do
[plano de melhorias](06-plano-de-melhorias-e-variaveis.md).

## 1. Resultado em uma página

| Verificação | Resultado |
|---|---|
| Testes de aceitação T-06–T-12 | **28 passed** em `tests/test_phase2_acceptance.py` |
| Suíte completa | **154 passed** em ~14,5 s |
| Validação independente | **169 verificações, 0 falhas** |
| Produtos da Fase 1 preservados | **20** |
| `goGribV2.sh` | Congelado, SHA-256 `994ce16c1480b17a62b78e72761307af2000dc47819abbaf48ce042c72023ce0` |
| Baseline da Fase 0 | Intacto no Git |
| Contratos de CSV/JSON | Nomes, headers, ordem de colunas, unidades e schemas preservados |
| Critério de saída | **Atendido** |

Relatórios brutos:

- `reprocessamento/reports/fase-2/validation.json` — 169 verificações;
- `reprocessamento/reports/fase-2/pytest.txt` — saída dos 28 testes.

## 2. O que mudou

### 2.1 C-06 / D-06 — `umidadeRel` em pressão

**Problema:** o campo `Relative humidity` só existe em `isobaricInhPa`. As
chamadas `umidadeRel -ns` do controlador não geravam produto e o MAN podia
levantar `AttributeError`.

**Correção:**

- controlador passou a usar `umidadeRel -n 850` para SP e RJ;
- AUT e MAN validam o tipo de nível antes de ler o GRIB;
- `-ns` retorna código 2 com a mensagem
  `umidadeRel não possui campo em superfície; use -n <hPa> (por exemplo, -n 850)`;
- `-n 850` continua gerando CSV/PNG em 0–100%.

**Arquivos:** `classes_MET/processamento_dados_MET.py`,
`classes_MET/executa_reqs_param.py`, `bash/automatizacao_controle_MET.sh`.

### 2.2 C-07 / D-05 — ativação de `winds`

**Problema:** as chamadas `winds` sem `-ns` e o bloco duplicado de `wind` em
1000/200 hPa eram no-op.

**Correção:**

- controlador chama `winds -ns` para SP e RJ;
- permanece apenas um bloco de `wind` em 1000/200 hPa;
- wrappers rejeitam chamadas sem `-v` ou sem `-n`/`-ns`;
- os produtos usam U/V reais, `hMET = metros × 3,28084` e `angMET` em
  `[0, 360)`, conforme as correções da Fase 1.

**Arquivos:** `bash/automatizacao_controle_MET.sh`,
`bash/automatiza_vento_MET.sh`.

### 2.3 D-07 / D-08 — JSON METAR

**Problema:** o arquivo era aberto em modo append sem separador; em reexecuções
o JSON ficava inválido. O timestamp usava ano/mês correntes, sem rollover.

**Correção:**

- `grava_json_atomico` grava em `.tmp` com `"w"`, faz `flush`/`fsync` e
  `os.replace`;
- a mesma estação + timestamp é sobrescrita, sem concatenar;
- `resolve_data_metar` usa uma referência UTC única
  (`METAR_REFERENCIA_UTC`, ou `date -u`) e resolve a virada de mês/ano;
- o diretório e o nome do arquivo usam a mesma referência;
- `automatizaMetar.sh` cria o diretório com `mkdir -p` e compartilha a
  referência entre os dois scripts Python.

**Arquivos:** `METARpy/metar_common.py`, `METARpy/METARpy.py`,
`METARpy/METARpy_traduzido.py`, `METARpy/automatizaMetar.sh`.

**Limite:** os 12 JSONs históricos inválidos continuam no acervo; a correção
não os repara retroativamente.

### 2.4 D-09 — intervalo do MAN

**Problema:** o intervalo exigia `min > max` e a ordem natural causava
`UnboundLocalError`.

**Correção:**

- `cria_intervalo_niveis` ordena os índices e aceita `200→500` e `500→200`;
- o resultado é sempre crescente;
- níveis iguais produzem um único elemento;
- extremos fora de 150–1000 hPa retornam código 2 com mensagem clara.

**Arquivo:** `classes_MET/executa_reqs_param.py`.

### 2.5 D-10 — limpeza de GRIBs e produtos

**Problema:** a data era montada misturando ano/mês de hoje com o dia anterior;
nos primeiros dias do mês o alvo ficava errado. Apenas `0p25` era removido.

**Correção:**

- data alvo calculada com `date -d "-2 days" +"%Y%m%d"`;
- remoção de `0p25`, `1p00` e legados `gfs????????????_???.grb` do dia alvo;
- remoção dos diretórios de produtos do mesmo dia em `mapasGrib/`,
  `matrizGrib/`, `matrizGrib/bluesky/` e `matrizGrib/predi/`;
- validação de data e retorno 0 em sucesso, 2 para data inválida;
- overrides de teste `MET_BASE_DIR`, `MET_HOJE` e `MET_DATA_ALVO`.

**Arquivo:** `remove_GRIBS_antigos.sh`.

### 2.6 D-13 / D-24 / D-27 — semântica documentada

Nenhum nome, seletor ou produto foi alterado:

- `chuvaNaoConvec` é **precipitação total** (convectiva + estratiforme); não
  subtraia `chuvaConvec` para obter a parcela estratiforme;
- o sufixo `+6` do arquivo de chuva é histórico: em `f000` o produto aparece
  como `_06`, mas o valor é o campo do GRIB naquele passo;
- `temps` é a **temperatura de pele** (`Temperature` em `surface`), não a
  temperatura do ar a 2 m.

**Arquivos:** `docs/03-dados-e-saidas.md`, `docs/08-contratos-e-consumidores.md`.

### 2.7 D-14 / D-28 — CLI e wrappers

**Problema:** o wrapper chamava o Python com `${4}` duplicado e as flags
dependiam de posição fixa; chamadas inválidas podiam sair com sucesso. O help
citava `chuva` e `MN`, que não existem.

**Correção:**

- `classes_MET/executa_reqs_param.py` usa `argparse`;
- `bash/reqs_MAN_MET.sh` é um wrapper fino com
  `exec python3 .../executa_reqs_param.py "$@"`;
- flags podem vir em qualquer ordem;
- validação de variável, coordenadas, data, nível e diretório de saída;
- `-v chuva` é rejeitado indicando `chuvaConvec`/`chuvaNaoConvec`;
- região `MN` é rejeitada; o MAN usa bounding box;
- wrappers AUT/MAN usam `set -euo pipefail`, help e mensagens de erro claras.

**Arquivos:** `classes_MET/executa_reqs_param.py`,
`bash/reqs_MAN_MET.sh`, `bash/automatiza_MET.sh`,
`bash/automatiza_vento_MET.sh`.

### 2.8 D-15 — matriz MAN duplicada

A chamada consecutiva de `gera_matriz` foi removida. O schema e o nome do
arquivo não mudaram.

**Arquivo:** `classes_MET/gera_matriz_MAN_MET.py`.

### 2.9 D-17 — visibilidade METAR

A classificação passou a usar `nuvem is None`/`nuvem is not None`. Com
visibilidade `9999`:

- sem nuvem → `"10000"`;
- com nuvem → `"superior a 10000"`;
- valores diferentes de `9999` são preservados.

**Arquivo:** `METARpy/metar_common.py`.

### 2.10 D-25 — variáveis indefinidas no shell METAR

As variáveis `data_hora`/`data_min`, que não existiam, foram removidas. O shell
usa uma referência UTC única e a repassa aos dois scripts.

**Arquivo:** `METARpy/automatizaMetar.sh`.

## 3. Testes T-06 a T-12

`tests/test_phase2_acceptance.py` contém 28 casos parametrizados:

| Teste | Cobertura | Casos |
|---|---|---:|
| T-06 | `umidadeRel` rejeita superfície, aceita 850 hPa, controlador e wrapper | 5 |
| T-07 | controlador ativa `winds`; wrapper gera mapas e matrizes; produtos reais de 20/30/40/50/80 m | 3 |
| T-08 | rollover UTC, referência do ambiente, sobrescrita sem concatenar, script METAR | 4 |
| T-09 | duas ordens, níveis iguais, níveis inválidos e execução da mesma lista | 3 |
| T-10 | datas de virada de mês (parametrizado), conteúdo removido e data inválida | 4 |
| T-11 | `chuva`, `MN`, ausência de argumento duplicado e flags fora de ordem | 4 |
| T-12 | nuvem ausente/presente (parametrizado), valores não `9999` e JSON traduzido | 5 |

Além dos testes unitários, T-07 compara os produtos `winds` da Fase 1 com
`pygrib` para os níveis N20, N30, N40, N50 e N80, nas matrizes BlueSky e do
preditor: `hMET`, `angMET`, `vento_resultante`, U/V e temperatura do preditor.

## 4. Validação independente

`reprocessamento/validar_fase2.py` não importa os testes da suíte; ele lê os
arquivos e os produtos diretamente. Resultado: **169 verificações, 0 falhas**.

Distribuição:

| Grupo | Verificações |
|---|---:|
| T-06 | 9 |
| T-07 (controlador, wrapper, produtos e matrizes) | 77 |
| T-08 | 16 |
| T-09 | 10 |
| T-10 | 36 |
| T-11 | 8 |
| T-12 | 8 |
| Invariantes (goGrib congelado, Fase 1 ok, 20 produtos, baseline limpo) | 4 |
| Resumo do relatório | 1 |

Invariantes confirmados:

- `goGribV2.sh` com o SHA-256 congelado;
- validação da Fase 1 ainda `ok`, com 158 verificações;
- 20 produtos da Fase 1 preservados em
  `reprocessamento/reports/20261022-00/`;
- baseline da Fase 0 sem alterações no Git.

## 5. Impacto para consumidores

Mudanças de comportamento que um consumidor pode notar:

| Situação | Antes | Depois |
|---|---|---|
| `umidadeRel -ns` | Nenhum produto, silencioso; MAN podia quebrar | Erro 2 com indicação de `-n 850` |
| `winds` no controlador | No-op | Mapas e matrizes para 20/30/40/50/80 m |
| Reexecutar METAR | JSON concatenado, inválido | Sobrescrita atômica, JSON válido |
| Virada de mês/ano no METAR | Timestamp com ano/mês correntes | Referência UTC com rollover |
| Intervalo MAN `200→500` | `UnboundLocalError` | Mesma lista crescente de `500→200` |
| Nível fora de 150–1000 hPa | Fixação silenciosa | Erro 2 |
| `-v chuva` / região `MN` | Podia não chamar o Python e sair com sucesso | Erro claro |
| Ordem das flags do MAN | Posicional | Qualquer ordem |
| Limpeza | Data errada na virada do mês; só `0p25` | Dia `hoje - 2`; `0p25`, `1p00`, legados e produtos |

O que **não** mudou:

- nomes de variáveis e produtos (`chuvaNaoConvec`, `temps`, `winds`, `wind`,
  `CampoVento` etc.);
- headers e ordem das colunas dos CSV;
- schemas e chaves dos JSON METAR;
- unidades efetivas;
- `goGribV2.sh`, URLs, ciclos e resoluções;
- baseline da Fase 0 e produtos da Fase 1.

## 6. Como reproduzir

Na raiz do worktree:

```bash
python3 -m pytest -q
python3 -m pytest -q tests/test_phase2_acceptance.py
python3 reprocessamento/validar_fase2.py
```

A validação grava:

```text
reprocessamento/reports/fase-2/validation.json
reprocessamento/reports/fase-2/pytest.txt
```

Ela exige a amostra real de GFS da Fase 0 e os produtos da Fase 1; se eles não
estiverem presentes, a validação falha explicitamente em vez de aprovar um
resultado parcial.

## 7. Pendências

Continuam para a Fase 3, sem relação com o critério de saída da Fase 2:

- **D-16** — `exit 1` no fim do controlador;
- **D-18** — sanitização de caminho de saída e nome de região;
- **D-19** — artefatos obsoletos e empacotamento;
- **D-20** — logging, lock e idempotência;
- **D-21/D-22/D-23** — robustez de `ponto_regiao`, `varMET` e `controla_env`;
- **D-26** — fechamento explícito de figuras e GRIBs.

**D-11** permanece fora de escopo porque `goGribV2.sh` está congelado.

## 8. Referências

- [06-plano-de-melhorias-e-variaveis.md](06-plano-de-melhorias-e-variaveis.md) — plano e critérios;
- [05-diagnostico.md](05-diagnostico.md) — evidências D-01 a D-28;
- [09-fase-1-resultados.md](09-fase-1-resultados.md) — Fase 1;
- [03-dados-e-saidas.md](03-dados-e-saidas.md) — semântica, schemas e retenção;
- [04-operacao.md](04-operacao.md) — runbook atualizado;
- [08-contratos-e-consumidores.md](08-contratos-e-consumidores.md) — contratos preservados.
