# 07 — Fase 0: baseline, amostra e harness

Este documento registra a execução da Fase 0 do plano: backup, snapshot Git,
amostra real de GFS, harness de testes e baseline gerado com o código de
produção **antes** das correções.

> **Aviso:** o baseline é intencionalmente incorreto. Ele preserva o
> comportamento atual, inclusive os defeitos D-01, D-02, D-03, D-04 e D-12.
> Não use os arquivos de `baseline/reports/` como referência operacional.

## 1. Resultado da fase

| Item | Resultado |
|---|---|
| Backup | `/home/paulo/Documentos/meus_codigos/backups/servidor_MET-fase-0-20261023.tar.gz` |
| Snapshot original | `servidor_MET` em `main`, commit `3bf69ee` |
| Repositório de melhorias | `METamorfose`, branch `execucao`, início em `3bf74a1` |
| Amostra GFS | 20 mensagens, 14.852.876 bytes, ponto de São Paulo validado |
| Harness | 22 testes verdes, 20 `xfail` estritos, 0 `skip` com a amostra |
| Aceitação | 18 testes de aceitação; suíte completa com 40 `passed`, 20 `xfailed` e 0 `skip` |
| Baseline | 20 produtos + `summary.json` + `pytest.txt` em `baseline/reports/20261022-00/` |
| Código de produção | Nenhuma alteração; `goGribV2.sh` congelado |
| `/media/MET` | Não foi escrito nem alterado |

## 2. Backup e snapshot Git

### 2.1 Backup

O backup foi criado antes de qualquer alteração:

```text
arquivo: /home/paulo/Documentos/meus_codigos/backups/servidor_MET-fase-0-20261023.tar.gz
bytes:   5.300.650
sha256:  15d9710edbba23d760953436b7e1463177a3d9785da35329b0dedad87cdba3fe
```

Ele contém o snapshot do código, a documentação, a configuração
`environment/path.conf` e os dados METAR versionados. Não havia produtos GFS
históricos em `/media/MET` disponíveis para copiar; o baseline foi gerado a
partir da amostra real descrita na seção 3.

### 2.2 Repositórios e tags

| Repositório | Papel | Branch | Commit/tag |
|---|---|---|---|
| `https://github.com/paulopimenta6/servidor_MET` | Original, privado | `main` | `3bf69ee` (`fase-0-snapshot`) |
| `https://github.com/paulopimenta6/METamorfose` | Melhorias, privado | `main` | idêntica ao original |
| `https://github.com/paulopimenta6/METamorfose` | Melhorias, privado | `execucao` | `3bf74a1` (`fase-0-inicio`) |

As tags são anotadas; o commit apontado por `fase-0-snapshot` é
`3bf69eebf2322df6cb10ac176ca05ed342ef68df` e o apontado por `fase-0-inicio` é
`3bf74a12e190c79c67f7117d6c1d81dcaf3124ac`. A tag `fase-0-concluida` é criada
no commit que contém o baseline, o harness e a suíte de aceitação desta fase.

## 3. Amostra real de GFS

### 3.1 Por que uma amostra parcial

O arquivo `gfs.t00z.pgrb2.0p25.f000` de 2026-10-22/00 tem 489.780.434 bytes.
Baixar o arquivo inteiro só para validar nomes, níveis e um ponto conhecido
seria caro e desnecessário. O script `tests/fetch_gfs_sample.py` usa o `.idx` do
NOMADS e HTTP `Range` para baixar apenas 20 mensagens GRIB2 completas.

```text
fonte:       https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.20261022/00/atmos/gfs.t00z.pgrb2.0p25.f000
índice:      .../gfs.t00z.pgrb2.0p25.f000.idx
resolução:   0p25
ciclo:       00
previsão:    000 (análise)
bytes:       14.852.876
sha256:      7adc84c35743c9fe4884756b938f38c8a18a5278d3b30bb945a300adde908a90
```

O arquivo binário não é versionado (`.gitignore`). O sidecar versionado é
`baseline/samples/gfs.20261022.00.0p25.subset.grb2.json`, com SHA-256
`fc7b1f607b5b91512325591a0d99bda76e70848be9bfd1d1730c4ea9df69e31d`.

### 3.2 Mensagens selecionadas

| Grupo | Mensagens |
|---|---|
| Superfície | `Pressure reduced to MSL`; `Temperature` em `surface` |
| 850 hPa | `Temperature`, `Relative humidity`, `Total Cloud Cover`, `U component of wind`, `V component of wind` |
| 2 m / 10 m | `2 metre temperature`, `10 metre U wind component`, `10 metre V wind component` |
| 20/30/40/50/80 m | `U component of wind` e `V component of wind` em `heightAboveGround` |

Os nomes de 2 m e 10 m são diferentes dos nomes em 850 hPa e em 20–80 m. Essa
diferença foi confirmada com `pygrib` e está coberta por
`tests/test_phase0_real_grib.py`.

### 3.3 Ponto de referência

O ponto escolhido é São Paulo, latitude `-23.55`, longitude `313.37` na
convenção 0–360 (`-46.63` em 0–180). Os valores extraídos da amostra são:

| Campo | Valor |
|---|---:|
| Temperatura em 850 hPa | 286,3202734375 K |
| U em 850 hPa | -4,85838623046875 m/s |
| V em 850 hPa | 1,6511474609375 m/s |
| Temperatura de superfície | 290,1187255859375 K |
| U em 20 m | -2,184248046875 m/s |
| V em 20 m | 1,82025390625 m/s |
| Pressão ao nível do mar | 102.170,475 Pa |

O teste `test_ponto_conhecido_de_sao_paulo_e_fisicamente_plausivel` verifica
faixas físicas e a coerência dos valores; ele não fixa uma “verdade”
meteorológica além da amostra.

## 4. Harness de testes

O harness está em `tests/phase0_harness.py`. Ele foi desenhado para testar as
funções reais sem executar os efeitos colaterais dos scripts de produção:

- `parse_param(sys.argv)` não é chamado;
- `controla_env` não é importado no processo de teste;
- as funções são extraídas com `ast` e executadas em um namespace controlado;
- `FakeGRIB` imita a API mínima do `pygrib`;
- `FakeDirSave` redireciona as saídas para `tmp_path`.

Os testes sintéticos usam arrays pequenos e valores conhecidos. Os testes reais
usam a amostra de 20 mensagens. O harness tem 42 casos:

```text
22 passed, 20 xfailed
```

Com a suíte de aceitação, a suíte completa tem 60 casos:

```text
40 passed, 20 xfailed, 0 skipped
```

Os 20 `xfail` são contratos do comportamento **desejado** que o código atual
ainda não cumpre. Eles usam `strict=True`: quando a Fase 1 corrigir um defeito,
o teste correspondente passará a `XPASS(strict)` e a suíte falhará até que o
marcador seja removido. Isso evita que uma correção passe despercebida.

### 4.1 O que está coberto

| Arquivo | Cobertura |
|---|---|
| `tests/test_phase0_freeze.py` | Hash e invariantes do `goGribV2.sh` |
| `tests/test_phase0_calculations.py` | Resultante, ângulo e altitude |
| `tests/test_phase0_orientation.py` | Headers, orientação, U/V, altitude e ângulo nos fluxos AUT e MAN |
| `tests/test_phase0_cycle.py` | Seleção de ciclo/data |
| `tests/test_phase0_real_grib.py` | Amostra real, nomes `pygrib`, grade e ponto de São Paulo |
| `tests/test_phase0_acceptance.py` | Aceitação dos entregáveis, contratos e remotos da Fase 0 |

### 4.2 Como executar

```bash
python3 -m pytest -q
python3 -m pytest -q -rx
python3 -m pytest -q -m acceptance
python3 -m pytest -q -m "acceptance and not network"
python3 tests/fetch_gfs_sample.py   # se a amostra não existir
```

Sem a amostra, os quatro testes reais são `skip`; os demais continuam
executando. A suíte de aceitação é diferente: ela **falha** se o backup, a
amostra ou um remoto obrigatório estiverem ausentes. Instruções detalhadas
estão em `tests/README.md`.

### 4.3 Aceitação automatizada

`tests/test_phase0_acceptance.py` verifica os entregáveis da fase sem alterar o
código de produção:

- hashes e tamanhos do backup, da amostra, do sidecar e do `goGribV2.sh`;
- inventário de 20 produtos, 13 CSVs e 7 PNGs, com os hashes do `summary.json`;
- headers, 2.337 linhas, ordem `lat`/`lon` e CRLF de todos os CSVs;
- reprodução congelada de D-01, D-02, D-03 e D-12;
- documentação, manifesto e `summary.json`;
- ausência de alteração no código de produção desde `fase-0-snapshot`;
- amostra binária e `baseline/run/` fora do Git;
- tag `fase-0-concluida` no remoto `melhorias`;
- `main` do `servidor_MET` ainda em `3bf69ee`;
- branch `execucao` remota igual ao `HEAD` local.

Os três últimos testes usam o marker `network`. Uma execução completa da
aceitação exige rede e os 18 testes verdes; não há `skip` para esconder
artefato ausente.

## 5. Baseline

### 5.1 Data, ciclo e recorte

| Parâmetro | Valor |
|---|---|
| Data/ciclo | 2026-10-22 / 00 |
| Hora local fixada | 2026-10-22T01:00 |
| Região | `SP` (lon -56..-42, lat -28..-18) |
| Nível de pressão | 850 hPa |
| Alturas de vento | 20, 30, 40, 50, 80 m |
| Resolução | 0.25° |

A hora local foi fixada em 01:00 para que `controla_env` escolhesse o ciclo
`00` e o diretório `20261022/00`. O wrapper `baseline/run_with_time.py` faz
`patch` de `time.localtime()` e executa o script de produção.

### 5.2 Isolamento

O baseline **não** usa `/media/MET`:

1. `baseline/run_baseline.py` cria `baseline/run/`.
2. Copia `classes_MET/` para `baseline/run/classes_MET/` (cópia real, não
   symlink, para que `../environment/path.conf` resolva dentro da árvore).
3. Escreve `baseline/run/environment/path.conf` apontando para
   `baseline/run/gribs`, `mapasGrib` e `matrizGrib`.
4. Copia a amostra para `baseline/run/gribs/20261022/00/`.
5. Executa os scripts a partir de `baseline/run/classes_MET/`.

`baseline/run/` é ignorado pelo Git. O relatório final é copiado para
`baseline/reports/20261022-00/`.

### 5.3 Comandos executados

```bash
python3 baseline/run_baseline.py
```

O runner executa seis comandos, todos com a hora fixa:

| Rótulo | Script | Argumentos |
|---|---|---|
| `matriz_temp_850` | `gera_matriz_MET.py` | `-v temp -n 850 -r SP` |
| `mapa_temp_850` | `gera_mapas_MET.py` | `-v temp -n 850 -r SP` |
| `matriz_wind_850` | `gera_matriz_vento_MET.py` | `-v wind -n 850 -r SP` |
| `mapa_wind_850` | `gera_mapas_vento_MET.py` | `-v wind -n 850 -r SP` |
| `matriz_winds_20` | `gera_matriz_vento_MET.py` | `-v winds -ns -r SP` |
| `mapa_winds_20` | `gera_mapas_vento_MET.py` | `-v winds -ns -r SP` |

Os dois últimos percorrem 20/30/40/50/80 m: a matriz gera cinco CSVs
BlueSky e cinco CSVs do preditor; o mapa gera cinco PNGs.

### 5.4 Artefatos

`baseline/reports/20261022-00/` contém:

```text
summary.json
pytest.txt
mapas/     7 PNGs
matrizes/  1 CSV escalar (temp 850)
bluesky/   6 CSVs (wind 850 + winds 20/30/40/50/80)
predi/     6 CSVs (wind 850 + winds 20/30/40/50/80)
```

Total: 20 produtos, 13 CSVs e 7 PNGs, além de `summary.json` e `pytest.txt`
(22 arquivos). O relatório ocupa aproximadamente 7 MB.

O `summary.json` registra:

- hash e tamanho da amostra e do sidecar;
- hashes de todos os produtos;
- cabeçalho, número de linhas, primeira/última latitude e faixas numéricas de
  cada CSV;
- comandos, códigos de retorno e logs de cada execução;
- versões de Python, NumPy, Matplotlib, `pygrib` e Basemap;
- hash do `goGribV2.sh` congelado.

O manifesto consolidado fica em `baseline/manifest.json` e reúne backup, tags,
commits, amostra, hashes dos produtos, versões, contagem do pytest e hashes dos
arquivos de código/documentação. Ele é gerado por `baseline/build_manifest.py`.

### 5.5 Evidências dos defeitos

Os valores abaixo vêm dos CSVs do baseline. Eles confirmam os defeitos já
descritos em `docs/05-diagnostico.md` e são a referência para a Fase 1.

| Defeito | Evidência no baseline | Interpretação |
|---|---|---|
| D-01 | Todos os CSVs começam em `lat=-28.0` e terminam em `lat=-18.0`. A primeira linha (`lat=-28,lon=-56`) tem `temp=26,0934 °C`, que é exatamente o valor do GFS em `lat=-18,lon=-56`; o GFS em `lat=-28,lon=-56` vale 15,7734 °C. A última linha (`lat=-18,lon=-42`) tem 6,7534 °C, que é o valor do GFS em `lat=-28,lon=-42`. | A coluna `lat` foi revertida, mas a matriz `data` não. A ordem das linhas é ascendente (-28 → -18), porém os dados continuam na ordem norte-sul do GFS. Não é correto dizer que o CSV tem “latitude decrescente”; o defeito é o desalinhamento entre `lat` e `data`. |
| D-02 | Nos preditores de 20/30/40/50/80 m, `vento U` e `vento V` são idênticos em todas as linhas. Em 850 hPa, U e V diferem. | `geraMatrizVentoSup` passa `u_comp_supe` também como V. O mapa superficial tem o mesmo problema. |
| D-03 | `hMET` de 20 m = 76.487,0118 ft; 30 m = 70.962,3367 ft; 80 m = 55.695,4568 ft. | A fórmula de pressão é aplicada a níveis em metros. O correto seria `20 × 3,28084 = 65,6168 ft`, `30 × 3,28084 = 98,4252 ft`, etc. |
| D-04 | Com hora local 06:30, o leitor abre o diretório `20261023/00/` em vez de `20261023/06/`. Com 00:30, abre `20261023/00/` em vez do `18` do dia anterior. | A comparação inclusiva de horas escolhe o ciclo anterior durante toda a primeira hora. |
| D-12 | `angMET` mínimo -179,27° (20 m), -179,76° (30 m), -179,69° (40 m), -178,74° (50 m), -179,18° (80 m), -179,38° (850 hPa). | A direção não é normalizada para `[0, 360)`. |

Outros números úteis do baseline:

| Produto | Faixa |
|---|---|
| `temp` 850 hPa | 6,7534 °C a 26,4234 °C |
| `vento_resultante` 20 m | 0,4090 a 21,8501 nós |
| `vento_resultante` 850 hPa | 0,5263 a 28,5676 nós |
| `temp` do preditor (superfície) | 283,1000 K a 304,8000 K |

### 5.6 Cópias de `f006/f012/f018`

O leitor atual não tolera a ausência de uma das quatro previsões: ele tenta
abrir `f000`, `f006`, `f012`, `f018` e cai em fallbacks se alguma faltar. Para
gerar o baseline sem baixar 4 × 15 MB, o runner copia a amostra `f000` para os
nomes `f006`, `f012` e `f018` dentro de `baseline/run/gribs/20261022/00/`.

Todas as mensagens copiadas continuam com `forecastTime=0`. Consequências:

- os quatro objetos abertos têm os mesmos dados;
- o nome de saída usa `ft=00` e é sobrescrito quatro vezes;
- o produto final corresponde a `f000`;
- **o baseline não representa `f006`, `f012` ou `f018`**.

Essa limitação está registrada no `LEIA-ME.txt` da árvore de execução e no
`summary.json`. Uma validação de previsões futuras exigirá baixar amostras
reais de cada previsão.

### 5.7 Limitações

- O baseline cobre apenas a região SP, 850 hPa e vento em 20–80 m. Não cobre
  todas as variáveis, regiões ou níveis.
- Os PNGs foram gerados, mas não são comparados pixel a pixel. A evidência
  numérica de orientação e vento vem dos CSVs e das funções que alimentam os
  mapas.
- O baseline usa uma hora local fixa; não valida a passagem real do relógio.
- A amostra é uma análise `f000`; não valida previsões `f006+`.
- O código de produção não foi alterado. O baseline é um retrato do
  comportamento anterior, não uma correção.

## 6. Reprodutibilidade

```bash
# 1. baixar a amostra (uma vez)
python3 tests/fetch_gfs_sample.py

# 2. rodar a suíte
python3 -m pytest -q

# 3. gerar o baseline
python3 baseline/run_baseline.py

# 4. regenerar o manifesto
python3 baseline/build_manifest.py
```

O baseline é determinístico para a mesma amostra, a mesma hora fixa e as mesmas
versões de biblioteca. O campo `generated_at` muda a cada execução; os nomes e
os valores numéricos não, desde que a amostra e a hora sejam as mesmas.

## 7. Critério de saída da Fase 0

| Critério | Situação |
|---|---|
| Backup criado e identificado por hash | Concluído |
| Snapshot Git e tag do original | Concluído |
| Baseline em diretório separado | Concluído |
| Harness com arrays sintéticos | Concluído |
| Suíte de aceitação automatizada | Concluído: 18 testes; 40 `passed`, 20 `xfailed`, 0 `skip` |
| Amostra real de GFS 0.25° | Concluído |
| Comparação de ponto conhecido | Concluído |
| Inventário de consumidores e contratos | Concluído em `docs/08-contratos-e-consumidores.md` |
| `goGribV2.sh` congelado | Concluído (`994ce16c…`) |
| Nenhum código de produção alterado | Concluído |
