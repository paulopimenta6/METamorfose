# 09 — Fase 1: correções de cálculo e reprocessamento

Este documento registra a execução da Fase 1 do
[plano de melhorias](06-plano-de-melhorias-e-variaveis.md): as correções
C-05, C-03, C-01, C-02 e C-04, os testes de aceitação T-01 a T-05 e o
reprocessamento da amostra da Fase 0 em diretório separado.

> **Escopo desta entrega**
>
> - A implementação está no worktree `METamorfose`, branch `execucao`, sobre o
>   commit `7954357` (tag `fase-0-concluida`).
> - O checkout principal `servidor_MET` permanece em `main`/`3bf69ee`, sem as
>   correções.
> - `goGribV2.sh`, URLs, ciclos, previsões, resoluções, variáveis e produtos
>   não foram alterados.
> - O baseline da Fase 0 é intencionalmente incorreto e **não** foi
>   sobrescrito; ele continua em `baseline/reports/20261022-00/`.
> - C-06, C-07 e os demais itens da Fase 2 permanecem pendentes.

## 1. Resultado da fase

| Item | Resultado |
|---|---|
| Ordem executada | C-05, C-03, C-01, C-02, C-04 |
| Código alterado | 8 geradores, leitor GRIB, harness e testes |
| Suíte completa | **123 passed**, 0 failed, 0 skip; 3 `deselected` (rede) |
| Aceitação da Fase 1 | **65 testes** em `tests/test_phase1_acceptance.py` |
| Amostra reprocessada | GFS 0.25°, 2026-10-22 00 UTC, `f000`, 20 mensagens |
| Hora local fixa | `2026-10-22T01:00` (ciclo selecionado: `00`) |
| Produtos gerados | **20**: 13 CSVs e 7 PNGs |
| Validação independente | **13/13 CSVs** conferem linha a linha com `pygrib`; 7 mapas presentes |
| Contrato | 20 nomes de produtos e todos os headers iguais ao baseline |
| Diretório de saída | `reprocessamento/reports/20261022-00/` |
| Baseline | Preservado sem alteração |
| `goGribV2.sh` | Congelado (`994ce16c…`) |

## 2. Escopo executado

### 2.1 Ordem e situação

| ID | Correção | Situação |
|---|---|---|
| C-05 | Seleção do ciclo GFS | Concluída |
| C-03 | Orientação norte-sul | Concluída |
| C-01 | Componente V recebendo U | Concluída |
| C-02 | Altura do vento superficial | Concluída |
| C-04 | Normalização de `angMET` | Concluída |

A ordem foi mantida porque C-05 define qual GRIB é lido, C-03 alinha a grade,
C-01 corrige as componentes e C-02/C-04 dependem dos valores já alinhados.

### 2.2 Arquivos alterados

| Arquivo | Correções |
|---|---|
| `classes_MET/leitura_dados_grib_MET.py` | C-05 |
| `classes_MET/gera_mapas_MET.py` | C-03 |
| `classes_MET/gera_mapas_MAN_MET.py` | C-03 |
| `classes_MET/gera_mapas_vento_MET.py` | C-01, C-03 |
| `classes_MET/gera_mapas_vento_MAN_MET.py` | C-03 |
| `classes_MET/gera_matriz_MET.py` | C-03 |
| `classes_MET/gera_matriz_MAN_MET.py` | C-03 |
| `classes_MET/gera_matriz_vento_MET.py` | C-01, C-02, C-03, C-04 |
| `classes_MET/gera_matriz_vento_MAN_MET.py` | C-02, C-03, C-04 |
| `tests/phase0_harness.py` | harness para as novas flags e mapas |
| `tests/test_phase0_*.py` | remoção dos `xfail` dos defeitos corrigidos |
| `tests/test_phase1_acceptance.py` | T-01 a T-05 |

Nenhum arquivo de `bash/`, `environment/`, `METARpy/` ou `goGribV2.sh` foi
alterado.

## 3. Correções aplicadas

### 3.1 C-05 — seleção do ciclo GFS

**Arquivo:** `classes_MET/leitura_dados_grib_MET.py:49-109`.

O leitor automático agora:

- escolhe o ciclo por intervalo semiaberto `[ciclo, próximo)`:
  `00 → [00,06)`, `06 → [06,12)`, `12 → [12,18)`, `18 → [18,24)`;
- usa a lista explícita `(0, 6, 12, 18)`, sem derivar ciclos da lista de
  previsões;
- monta caminhos com `os.path.join()` a partir do diretório de GRIB, sem
  `os.chdir()` relativo;
- falha com `FileNotFoundError` quando o diretório do ciclo selecionado não
  existe, em vez de usar silenciosamente o ciclo anterior;
- mantém os fallbacks de resolução `0p25 → 0p50 → 1p00 → legado`, na mesma
  ordem e com os mesmos nomes de arquivo.

Fronteiras verificadas:

| Hora local | Ciclo |
|---|---|
| 00:00–05:59 | `00` |
| 06:00–11:59 | `06` |
| 12:00–17:59 | `12` |
| 18:00–23:59 | `18` |

O nome de saída continua usando o ciclo `hh_analise` calculado pelos geradores.
Essa lógica já usava intervalo semiaberto e não foi alterada.

### 3.2 C-03 — orientação norte-sul

**Arquivos e linhas principais:**

- `classes_MET/gera_mapas_MET.py:116,128,138`;
- `classes_MET/gera_mapas_MAN_MET.py:92,104,114`;
- `classes_MET/gera_mapas_vento_MET.py:86-87,96-97,106-107`;
- `classes_MET/gera_mapas_vento_MAN_MET.py:66-67,81-82,91-92` (método LC) e
  equivalentes nos métodos barb e LCbarb;
- `classes_MET/gera_matriz_MET.py:84,97,104`;
- `classes_MET/gera_matriz_MAN_MET.py:65,78,85`;
- `classes_MET/gera_matriz_vento_MET.py:130-131,146-147,156-157,252-254,270-272,282-284`;
- `classes_MET/gera_matriz_vento_MAN_MET.py:99-100` e equivalentes nos três
  métodos.

A correção inverte `data` junto com `lat` (`data[::-1, :]`), mantendo a ordem
crescente das linhas do CSV. No ramo `flag == 3` (cruzamento do dateline), a
inversão é aplicada a `data_ini` e `data_fim` **antes** da concatenação. Nos
produtos de vento, U, V e temperatura são invertidos com a mesma máscara.

O contrato de linha não mudou: todos os CSVs continuam de `lat=-28.0` a
`lat=-18.0`, com 2337 linhas na grade 41 × 57. O que mudou foi o valor
associado a cada latitude.

Evidência no ponto `(-28, -56)` para `temp` em 850 hPa:

| Versão | Valor no CSV | Leitura independente |
|---|---:|---:|
| Baseline | 26,0934 °C | 15,7734 °C no GFS em `(-28, -56)` |
| Fase 1 | 15,7734 °C | 15,7734 °C no GFS em `(-28, -56)` |

No baseline, 26,0934 °C é o valor do GFS em `(-18, -56)`, confirmando o
espelhamento norte-sul.

### 3.3 C-01 — componente V recebendo U

**Arquivos e linhas:**

- `classes_MET/gera_mapas_vento_MET.py:220-221` — o mapa superficial AUT passou
  a ler `vSupe` para `v_comp`;
- `classes_MET/gera_matriz_vento_MET.py:335-339` — o preditor AUT passou a
  receber `v_comp_supe` no lugar de `u_comp_supe` como V.

O fluxo manual já usava `uSupe` e `vSupe` corretamente. O fluxo BlueSky AUT já
recebia o V correto; o defeito estava no mapa superficial AUT e na matriz do
preditor.

Evidência no primeiro ponto do preditor de 20 m (`lat=-28`, `lon=-56`):

| Versão | `vento U` | `vento V` | Leitura do GFS |
|---|---:|---:|---|
| Baseline | -1,8505 | -1,8505 | U=-2,3005; V=-2,0097 |
| Fase 1 | -2,3005 | -2,0097 | U=-2,3005; V=-2,0097 |

No baseline, U e V eram idênticos em todas as linhas dos níveis 20/30/40/50/80.
Na Fase 1, as duas colunas voltam a ser independentes e conferem com o GRIB.

### 3.4 C-02 — altura do vento superficial

**Arquivos e linhas:**

- `classes_MET/gera_matriz_vento_MET.py:45-56,183,338,376`;
- `classes_MET/gera_matriz_vento_MAN_MET.py:56-66,156,270,420-421` e chamadas
  correspondentes.

`converte_altitude()` voltou a implementar apenas a fórmula barométrica, que
espera pressão em hPa. A nova função `calcula_hmet(nivel, eh_vento_superficie)`
decide explicitamente:

```python
def calcula_hmet(nivel, eh_vento_superficie):
    if eh_vento_superficie:
        return float(nivel) * 3.28084
    return converte_altitude(nivel)
```

O fluxo `winds` passa `True`; o fluxo `wind` passa `False`. Não há mais
inferência pelo valor `20/30/40/50/80`, que poderia confundir um nível de
pressão com uma altura em metros.

| Nível | Baseline (`hMET`) | Fase 1 (`hMET`) |
|---:|---:|---:|
| 20 m | 76.487,0118 ft | **65,6168 ft** |
| 30 m | 70.962,3367 ft | **98,4252 ft** |
| 40 m | 66.775,8167 ft | **131,2336 ft** |
| 50 m | 63.366,9483 ft | **164,0420 ft** |
| 80 m | 55.695,4568 ft | **262,4672 ft** |
| 850 hPa | 4.779,1936 ft | **4.779,1936 ft** (inalterado) |

O header `nivel<hPa>` da matriz manual e o header `hMET` da matriz BlueSky
foram preservados. Para `winds`, o valor de `nivel` é uma altura em metros,
apesar do rótulo histórico `<hPa>`; essa limitação de nomenclatura permanece e
está documentada em [08-contratos-e-consumidores.md](08-contratos-e-consumidores.md).

### 3.5 C-04 — normalização de `angMET`

**Arquivos e linhas:**

- `classes_MET/gera_matriz_vento_MET.py:40-43`;
- `classes_MET/gera_matriz_vento_MAN_MET.py:51-54`.

A fórmula passou de `arctan2(-U, -V)` em graus, com intervalo
`[-180, 180]`, para:

```python
angResult = (np.degrees(np.arctan2(-data_u, -data_v)) + 360.0) % 360.0
```

Quadrantes verificados:

| U | V | Direção |
|---:|---:|---:|
| 10 | 0 | 270° |
| -10 | 0 | 90° |
| 0 | 10 | 180° |
| 0 | -10 | 0° |

Faixas antes e depois nos produtos reprocessados:

| Nível | Baseline | Fase 1 |
|---|---|---|
| 20 m | -179,2747° a 179,5409° | **4,5137° a 355,3496°** |
| 30 m | -179,7557° a 178,9861° | **1,0903° a 357,9310°** |
| 40 m | -179,6896° a 178,7832° | **4,4828° a 357,4269°** |
| 50 m | -178,7447° a 179,5595° | **8,4340° a 357,6730°** |
| 80 m | -179,1760° a 178,8495° | **3,6521° a 351,7587°** |
| 850 hPa | -179,3825° a 174,7260° | **0,3595° a 359,8037°** |

Todos os valores ficaram em `[0, 360)`. A função `criaAngAzMET()` permanece
como estava; ela não é usada nos produtos.

## 4. Testes

A suíte completa terminou com **123 passed** e 3 `deselected` (testes de rede),
sem `xfail`, `skip` ou falha. Os `xfail` estritos que documentavam D-01, D-02,
D-03, D-04 e D-12 foram removidos porque os defeitos foram corrigidos; os
testes agora exigem o comportamento correto.

`tests/test_phase1_acceptance.py` reúne **65 testes** (27 funções, várias
parametrizadas) organizados por T-01 a T-05:

| ID | Cobertura | Evidência principal |
|---|---|---|
| T-01 | Orientação N-S | CSVs e mapas escalares/de vento, AUT e MAN, inclusive `flag == 3`; primeira linha é o sul |
| T-02 | U/V | U puro, V puro, diagonal, resultante; mapa AUT lê `vSupe`; preditor AUT recebe `v_comp_supe` |
| T-03 | `hMET`/`halt` | 20/30/40/50/80 m com conversão linear; 100/500/850 hPa com fórmula barométrica; flags explícitas |
| T-04 | `angMET` | Quatro quadrantes em `[0, 360)`; grade inteira dentro do intervalo |
| T-05 | Ciclo | Fronteiras 05:59/06:00, 11:59/12:00, 17:59/18:00, 23:59/00:00; meia-noite; ciclo ausente; fallback de resolução |

Além dos testes de aceitação, o harness `tests/phase0_harness.py` foi ajustado
para:

- aceitar `eh_vento_superficie` nos runners de matriz e mapa;
- capturar a matriz efetivamente entregue ao `Basemap`, em vez de apenas o PNG;
- construir diretórios de GRIB simulados com ciclos e resoluções controladas.

## 5. Reprocessamento

### 5.1 Entrada e configuração

| Item | Valor |
|---|---|
| Amostra | `baseline/samples/gfs.20261022.00.0p25.subset.grb2` |
| SHA-256 da amostra | `7adc84c35743c9fe4884756b938f38c8a18a5278d3b30bb945a300adde908a90` |
| Mensagens | 20 (análise `f000`) |
| Data/ciclo | 2026-10-22 / `00` |
| Hora local fixa | `2026-10-22T01:00` |
| Região | `SP` (`-56` a `-42`, `-28` a `-18`) |
| Saída | `reprocessamento/reports/20261022-00/` |

Comandos executados pelo runner, todos com a hora fixa:

| Rótulo | Script | Argumentos |
|---|---|---|
| `matriz_temp_850` | `gera_matriz_MET.py` | `-v temp -n 850 -r SP` |
| `mapa_temp_850` | `gera_mapas_MET.py` | `-v temp -n 850 -r SP` |
| `matriz_wind_850` | `gera_matriz_vento_MET.py` | `-v wind -n 850 -r SP` |
| `mapa_wind_850` | `gera_mapas_vento_MET.py` | `-v wind -n 850 -r SP` |
| `matriz_winds_20` | `gera_matriz_vento_MET.py` | `-v winds -ns -r SP` |
| `mapa_winds_20` | `gera_mapas_vento_MET.py` | `-v winds -ns -r SP` |

Os dois últimos percorrem 20/30/40/50/80 m. O resultado são 5 CSVs BlueSky,
5 CSVs do preditor e 5 PNGs, além do produto de 850 hPa e do mapa escalar.

### 5.2 Artefatos

```text
reprocessamento/reports/20261022-00/
├── summary.json
├── validation.json
├── pytest.txt
├── mapas/     7 PNGs
├── matrizes/  1 CSV (temp 850)
├── bluesky/   6 CSVs (wind 850 + winds 20/30/40/50/80)
└── predi/     6 CSVs (wind 850 + winds 20/30/40/50/80)
```

Total: **20 produtos**, 13 CSVs e 7 PNGs. O `summary.json` registra:

- hash e tamanho da amostra;
- hashes de todos os produtos;
- cabeçalho, número de linhas, primeira/última latitude e faixas numéricas de
  cada CSV;
- comandos, códigos de retorno e logs das seis execuções;
- versões do ambiente.

A validação independente **não** é executada pelo runner e não fica dentro do
`summary.json`; ela é um passo separado que grava `validation.json` no mesmo
diretório do relatório.

Como na Fase 0, a amostra `f000` foi copiada para os nomes `f006/f012/f018`
apenas para satisfazer o loop do leitor. Todas as cópias mantêm
`forecastTime=0`; o reprocessamento representa somente `f000` e não valida
previsões futuras.

### 5.3 Validação independente

`reprocessamento/validar_fase1.py` não importa o código de produção. Ele relê a
amostra com `pygrib`, recalcula os valores esperados e compara todas as linhas
dos 13 CSVs:

- confere a grade 41 × 57 (2337 linhas), com `lat` de `-28` a `-18` e `lon` de
  `-56` a `-42`, em passos de 0,25°;
- confere `temp` escalar em 850 hPa contra `Temperature/isobaricInhPa`;
- confere `vento U`, `vento V` e `temp` do preditor contra os campos do GRIB;
- confere `hMET` superficial contra `nível × 3,28084` e `hMET` de 850 hPa
  contra a fórmula barométrica;
- confere `angMET` contra `(degrees(arctan2(-U, -V)) + 360) % 360`;
- confere `vento_resultante` contra `sqrt(U² + V²) × 1,943`;
- compara o conjunto de 20 nomes de produtos e todos os headers CSV com o
  baseline, sem permitir renomeação ou remoção;
- confere nos seis logs que o ciclo `00` foi selecionado para a hora local
  `1:00`.

Resultado final:

| Verificação | Resultado |
|---|---|
| Verificações executadas | **158** |
| Falhas | **0** |
| CSVs validados | 13/13 |
| Linhas por CSV | 2337 |
| Mapas presentes | 7/7 |
| `hMET` superficial máximo | 262,4672 ft (80 m) |
| `hMET` em 850 hPa | 4.779,1936 ft |
| `angMET` | dentro de `[0, 360)` |
| Produtos no contrato | 20/20 |
| Headers iguais ao baseline | Sim |
| Logs com ciclo `00` | 6/6 |
| `validation.json` | `status: ok` |

A validação é executada separadamente do runner:

```bash
python3 reprocessamento/validar_fase1.py
```

Ela grava `reprocessamento/reports/20261022-00/validation.json` e retorna
código de saída diferente de zero se qualquer verificação falhar. O runner não
chama essa validação.

## 6. Diferenças em relação ao baseline

O baseline foi mantido intacto. As diferenças abaixo são intencionais e
correspondem aos defeitos corrigidos.

| Item | Baseline | Fase 1 |
|---|---|---|
| `temp` 850 hPa em `(-28,-56)` | 26,0934 °C | 15,7734 °C |
| `vento U`/`V` do preditor de 20 m | U = V em todas as linhas | U e V independentes, iguais ao GRIB |
| `hMET` de 20 m | 76.487,0118 ft | 65,6168 ft |
| `hMET` de 80 m | 55.695,4568 ft | 262,4672 ft |
| `angMET` de 20 m | -179,2747° a 179,5409° | 4,5137° a 355,3496° |
| Orientação N-S | dados espelhados em relação à coluna `lat` | dados alinhados à latitude |
| Ciclo na primeira hora | ciclo anterior | ciclo da hora corrente |

O que **não** mudou:

- os 20 nomes de arquivos e a árvore de diretórios;
- os headers e a ordem das colunas;
- o número de linhas, a grade e a ordem crescente de `lat`/`lon`;
- as unidades documentadas;
- `vento_resultante` da matriz BlueSky (o V já estava correto nesse fluxo);
- o mapa escalar de temperatura e os produtos de 850 hPa, exceto pela
  orientação e pelos valores de vento/ângulo quando aplicável;
- `goGribV2.sh`, URLs, ciclos, previsões e resoluções.

Os 7 PNGs foram regerados e têm hashes diferentes do baseline. A validação
numérica de orientação é feita pelos CSVs e pelo harness, que captura a matriz
entregue ao desenho; não há comparação pixel a pixel.

## 7. Contrato preservado e limites

Headers preservados:

```csv
lat,lon,temp
lat,lon,hMET,angMET,vento_resultante
lat,lon,vento U,vento V,temp
lat,lon,nivel<hPa>,halt<feet>,angMET<grau>,vento U<ms**-1>,vento V<ms**-1>,vento_resultante<ms**-1>
lat,lon,hMET<feet>,angMET<grau>,vento_resultante<knot>
```

Caveats que permanecem:

- `nivel<hPa>` na matriz manual de `winds` continua com o rótulo histórico,
  embora o valor seja em metros;
- `hMET`/`halt` continuam sendo o nome da altura em pés, inclusive para
  `winds`;
- `temp` do preditor continua em Kelvin e usa temperatura de pele
  (`Temperature/surface`), não temperatura do ar a 2 m;
- `chuvaNaoConvec` continua mapeando precipitação total;
- nenhuma variável, coluna ou produto foi renomeado.

Limites desta fase:

- a amostra é uma análise `f000`; previsões `f006/f012/f018` não foram
  validadas com dados reais;
- o reprocessamento cobre somente a região SP e os níveis usados na Fase 0;
- mapas não são comparados pixel a pixel;
- C-06 (`umidadeRel -ns`), C-07 (ativação de `winds` no controlador) e os
  demais itens da Fase 2 continuam pendentes;
- o código corrigido ainda não foi promovido ao checkout principal nem a
  `/media/MET`.

## 8. Reprodutibilidade

```bash
# suíte completa (sem rede)
python3 -m pytest -q -m "not network"

# aceitação da Fase 1
python3 -m pytest -q tests/test_phase1_acceptance.py

# reprocessamento da amostra (recria run/ e reports/20261022-00/)
python3 reprocessamento/run_reprocessamento.py

# retomar sem apagar run/ nem repetir comandos já registrados
python3 reprocessamento/run_reprocessamento.py --resume

# validação independente isolada
python3 reprocessamento/validar_fase1.py
```

Sem `--resume`, o runner apaga e recria `reprocessamento/run/` e
`reprocessamento/reports/20261022-00/` antes de executar. Com `--resume`, ele
preserva `run/`, pula os rótulos cujo log já existe e mantém `validation.json` e
`pytest.txt`; os produtos são recopiados e o `summary.json` é regerado. Para
evitar que duas execuções concorrentes corrompam esses diretórios, ele mantém um
lock exclusivo em `reprocessamento/.run.lock` e recusa iniciar se outra execução
estiver ativa. O baseline não é tocado. O campo `generated_at` do `summary.json`
muda a cada execução; os nomes e os valores numéricos são determinísticos para a
mesma amostra, hora fixa e versões de biblioteca.

## 9. Critério de saída da Fase 1

| Critério | Situação |
|---|---|
| T-01 a T-05 passam | Concluído: 65 testes de aceitação |
| Mapas e matrizes conferem com leitura independente do GRIB | Concluído: 13/13 CSVs comparados com `pygrib`; 7 mapas presentes |
| Nenhum nome de variável/produto mudou | Concluído: 20/20 produtos e headers iguais ao baseline |
| Reprocessamento em diretório separado | Concluído: `reprocessamento/reports/20261022-00/` |
| Baseline preservado | Concluído |
| `goGribV2.sh` congelado | Concluído |

## 10. Próximos passos

1. Revisar e aprovar o diff da Fase 1 no worktree `METamorfose`.
2. Decidir a promoção para `main`/produção e o rollback.
3. Executar a Fase 2: C-06, C-07, D-05, METAR, CLI e demais itens.
4. Atualizar `docs/03-dados-e-saidas.md` e o help somente quando a promoção
   operacional for aprovada.
