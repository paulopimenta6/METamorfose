# 08 — Contratos e consumidores

Este documento inventaria os contratos de saída que os consumidores já usam e
que **não devem ser quebrados** pelas correções de cálculo. Ele foi escrito a
partir do código, dos produtos do baseline e dos schemas descritos em
`docs/03-dados-e-saidas.md`.

> **Regra da Fase 1:** corrigir valores e lógica, preservando nomes de colunas,
> ordem de colunas, ordem das linhas, padrões de nome de arquivo e unidades.
> Mudança de schema é uma decisão separada (schema v2), não um efeito colateral
> de correção.
>
> **Estado:** as correções C-01, C-02, C-03, C-04 e C-05 (Fase 1) e C-06/C-07 e
> os itens D-05, D-07, D-08, D-09, D-10, D-13, D-14, D-15, D-17, D-24, D-25,
> D-27 e D-28 (Fase 2) já foram aplicadas na branch `execucao`; o contrato abaixo
> foi preservado. As descrições marcadas como “hoje” referem-se ao código
> original em `main`. Os resultados estão em
> [09-fase-1-resultados.md](09-fase-1-resultados.md) e
> [10-fase-2-resultados.md](10-fase-2-resultados.md).

## 1. Regras gerais dos CSV

Todos os CSV de produtos GFS:

- são texto UTF-8, separados por vírgula, com cabeçalho na primeira linha;
- usam CRLF (`\r\n`) como terminador de linha e não incluem índice;
- têm `lat` e `lon` em graus decimais nas duas primeiras colunas;
- são gravados com `csv.writer`, sem aspas especiais;
- percorrem as linhas com `i` (latitude) e as colunas com `j` (longitude).

### 1.1 Ordem das linhas e orientação

No baseline, todos os CSVs começam em `lat=-28.0` e terminam em `lat=-18.0`,
com longitude de `-56.0` a `-42.0`. Ou seja, a **coluna** `lat` já está em ordem
crescente e a **coluna** `lon` também.

O defeito D-01 não é a ordem da coluna `lat`; é o desalinhamento entre `lat` e
`data`. Exemplo do baseline (`temp` em 850 hPa):

| Linha do CSV | `lat` | `lon` | `temp` | Valor real do GFS no ponto |
|---|---:|---:|---:|---|
| primeira | -28,0 | -56,0 | 26,0934 °C | 15,7734 °C em (-28, -56) |
| última | -18,0 | -42,0 | 6,7534 °C | 6,7534 °C em (-28, -42) |

A primeira linha contém o valor do norte; a última, o valor do sul. A correção
deve **alinhar os dados à coluna `lat`**, mantendo a ordem crescente e o mesmo
schema. Não se deve simplesmente inverter a coluna `lat` de volta: isso mudaria
a ordem das linhas que os consumidores já recebem.

### 1.2 Longitude

Os produtos usam a longitude na convenção do recorte de origem. No baseline da
região SP, os valores são negativos (`-56.0` a `-42.0`). O GFS internamente usa
0–360; o código converte para o recorte. Consumidores não devem assumir 0–360
para todos os produtos.

## 2. Fluxo automático (AUT)

### 2.1 Mapas

```text
mapasGrib/AAAAMMDD/HH/GFS_<res>_<REGIAO>_N<nivel>_<var>_<ana>_<dataDate>_<ff>.png
```

Exemplo do baseline:

```text
mapas/GFS_0.25_SP_N850_temp_00_20261022_00.png
mapas/GFS_0.25_SP_N850_CampoVento_00_20261022_00.png
mapas/GFS_0.25_SP_N20_CampoVento_00_20261022_00.png
```

- `<REGIAO>` é `str(regiao).upper()` nos mapas. Nas matrizes, o nome usa
  `str(regiao)` sem `upper()`; para regiões predefinidas como `SP` o resultado é
  igual, mas para `-ll` o mapa e a matriz podem diferir em maiúsculas/minúsculas.
- `<var>` é a chave (`temp`, `temps`, `nuvem`, `chuvaConvec`,
  `chuvaNaoConvec`, `prnm`, etc.) ou `CampoVento` nos mapas de vento.
- `<nivel>` é `N850`, `N20`, `Nsuperficie`, `Nsurface`, etc. O rótulo de
  superfície pode variar entre mapa e matriz (ver `docs/03-dados-e-saidas.md`).
- `<ana>` é o ciclo calculado (`00`, `06`, `12`, `18`).
- `<dataDate>` é a data do GRIB (`AAAAMMDD`).
- `<ff>` é `forecastTime` com dois dígitos; para chuva, `forecastTime + 6`.
- Os PNGs não têm contrato de conteúdo programático; são consumidos por pessoas
  e sites. A orientação e os vetores precisam corresponder aos CSVs.

### 2.2 Matrizes escalares

```text
matrizGrib/AAAAMMDD/HH/GFS_<res>_<REGIAO>_N<nivel>_<var>_<ana>_<dataDate>_<ff>.csv
```

Exemplo:

```text
matrizes/GFS_0.25_SP_N850_temp_00_20261022_00.csv
```

Cabeçalho exato:

```csv
lat,lon,<var>
```

Exemplo real:

```csv
lat,lon,temp
-28.0,-56.0,26.093398437500014
```

Unidades efetivas:

| `<var>` | Unidade no CSV | Observação |
|---|---|---|
| `temp`, `temps` | °C | Kelvin convertido por `-273.15` |
| `ps`, `prnm` | hPa | Pascal convertido por `/100` |
| `nuvem` | % | Total cloud cover |
| `chuvaConvec`, `chuvaNaoConvec` | kg m⁻² | Numericamente equivalente a mm; `chuvaNaoConvec` é precipitação **total** e o rótulo `+6` é histórico (D-13/D-24) |
| `umidadeRel` | % | Apenas em pressão; `-ns` é rejeitado com erro claro (D-06) |
| `u`, `v` | m s⁻¹ | Componentes do vento |

Não renomear `chuvaNaoConvec` para `chuvaTotal`, mesmo que o dado seja
precipitação total (D-13). O nome é parte do contrato.

### 2.3 Matriz BlueSky

```text
matrizGrib/bluesky/AAAAMMDD/HH/GFS_<res>_matriz_lat_lon_alt_angMET_VentoResult_<REGIAO>_N<nivel>_<ana>_<dataDate>_<ff>.csv
```

Exemplo:

```text
bluesky/GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_SP_N20_00_20261022_00.csv
```

Cabeçalho exato:

```csv
lat,lon,hMET,angMET,vento_resultante
```

| Coluna | Unidade | Contrato |
|---|---|---|
| `lat` | graus | Latitude do ponto |
| `lon` | graus | Longitude do ponto |
| `hMET` | pés | Para `wind`, altitude de pressão; para `winds`, altura em metros convertida para pés (`metros × 3,28084`, corrigido na Fase 1) |
| `angMET` | graus | Direção meteorológica em `[0, 360)` (corrigido na Fase 1) |
| `vento_resultante` | nós | `sqrt(U² + V²) * 1.943` |

O header não contém unidades; consumidores dependem desta documentação. Não
adicionar `_ft`, `_knot` ou sufixos: isso quebraria o contrato.

### 2.4 Matriz do preditor

```text
matrizGrib/predi/AAAAMMDD/HH/GFS_<res>_matriz_lat_lon_Vento_UVT_Predi_<REGIAO>_N<nivel>_<ana>_<dataDate>_<ff>.csv
```

Exemplo:

```text
predi/GFS_0.25_matriz_lat_lon_Vento_UVT_Predi_SP_N20_00_20261022_00.csv
```

Cabeçalho exato:

```csv
lat,lon,vento U,vento V,temp
```

| Coluna | Unidade | Contrato |
|---|---|---|
| `vento U` | m s⁻¹ | Componente zonal |
| `vento V` | m s⁻¹ | Componente meridional (corrigida na Fase 1; em `winds` usa `vSupe`) |
| `temp` | K | Para `winds`, é a temperatura de superfície (`temps`); não converter para °C |

O header tem espaço em `vento U` e `vento V`; preservar exatamente. O header
`temp` é diferente do `temp` das matrizes escalares, que está em °C.

## 3. Fluxo manual (MAN)

O MAN recebe uma bounding box e monta a string de região com espaços e
dois-pontos:

```text
LonMin:<lonmin> LonMax:<lonmax> LatMin:<latmin> LatMax:<latmax>
```

Exemplo:

```text
LonMin:-56.0 LonMax:-42.0 LatMin:-28.0 LatMax:-18.0
```

Essa string faz parte do nome do arquivo. Consumidores que usam glob ou parsing
precisam lidar com espaços e `:`.

### 3.1 Mapas escalares

```text
<out>/GFS_<res>_<regiao>_N<nivel>_<var>_<ana>_<dataDate>_<prev>.png
```

### 3.2 Matrizes escalares

```text
<out>/GFS_<res>_<regiao>_N<nivel>_<var>_<ana>_<dataDate>_<prev>.csv
```

Cabeçalho:

```csv
lat,lon,<var>
```

Mesmas unidades da matriz escalar AUT. A matriz é gerada uma única vez desde a
Fase 2; a chamada duplicada de `gera_matriz` foi removida (D-15).

### 3.3 Mapas de vento

```text
<out>/GFS_<res>_<regiao>_N<nivel>_CampoVento_LC_<ana>_<dataDate>_<prev>.png
<out>/GFS_<res>_<regiao>_N<nivel>_CampoVento_barb_<ana>_<dataDate>_<prev>.png
<out>/GFS_<res>_<regiao>_N<nivel>_CampoVento_barbLC_<ana>_<dataDate>_<prev>.png
```

### 3.4 Matriz de vento bruta

```text
<out>/matriz_vento_<regiao>_N<nivel>_<ana>_<dataDate>_<prev>.csv
```

Cabeçalho exato:

```csv
lat,lon,nivel<hPa>,halt<feet>,angMET<grau>,vento U<ms**-1>,vento V<ms**-1>,vento_resultante<ms**-1>
```

| Coluna | Unidade | Contrato |
|---|---|---|
| `nivel<hPa>` | hPa | Para `wind`; para `winds`, o valor é a altura em metros, mas o header permanece |
| `halt<feet>` | pés | Para `wind`, altitude de pressão; para `winds`, `metros × 3,28084` (corrigido na Fase 1) |
| `angMET<grau>` | graus | Direção meteorológica em `[0, 360)` (corrigido na Fase 1) |
| `vento U<ms**-1>` | m s⁻¹ | Componente zonal |
| `vento V<ms**-1>` | m s⁻¹ | Componente meridional (corrigida na Fase 1) |
| `vento_resultante<ms**-1>` | m s⁻¹ | Resultante em m/s (diferente do BlueSky, em nós) |

O header `nivel<hPa>` é semanticamente incorreto para `winds`, mas é parte do
contrato. A decisão registrada em `docs/06-plano-de-melhorias-e-variaveis.md` é
mantê-lo e documentar o caveat; mudá-lo seria schema v2.

### 3.5 Matriz BlueSky do MAN

```text
<out>/matriz_vento_bluesky_<regiao>_N<nivel>_<ana>_<dataDate>_<prev>.csv
```

Cabeçalho exato:

```csv
lat,lon,hMET<feet>,angMET<grau>,vento_resultante<knot>
```

Unidades: pés, graus, nós. O `hMET` de `winds` usa `metros × 3,28084` desde a
Fase 1; o header e a unidade não mudaram.

### 3.6 Matriz do preditor do MAN

```text
<out>/matriz_vento_predi_<regiao>_N<nivel>_<ana>_<dataDate>_<prev>.csv
```

Cabeçalho exato:

```csv
lat,lon,vento U,vento V,temperatura K
```

Unidades: m/s, m/s, K. Para `winds`, U/V vêm de `uSupe`/`vSupe`; a temperatura
vem de `temps` (superfície).

## 4. JSON METAR

O fluxo METAR é independente do GFS, mas também tem consumidores. O inventário
completo está em `docs/03-dados-e-saidas.md`, seções 6.2 e 6.3. Resumo:

### 4.1 JSON bruto

```json
{
  "data": [
    {
      "id_localidade ": "SBGR",
      "data ": "202212170300",
      "mensagem_metar ": "SBGR 170300Z 13004KT 9999 FEW013 17/15 Q1012"
    }
  ]
}
```

As três chaves têm **espaço no final**: `id_localidade `, `data `,
`mensagem_metar `. Um consumidor que usa `obj["id_localidade"]` sem o espaço
falha. Isso é contrato atual; não renomear sem schema v2.

### 4.2 JSON traduzido

```json
{
  "data": [
    {
      "estacao": "SBGR",
      "data": "202212170300",
      "mensagem_metar": "SBGR 170300Z 13004KT 9999 FEW013 17/15 Q1012",
      "temperatura [C]": 17,
      "temperatura_pto_orvalho [C]": 15,
      "visibilidade [m]": "superior a 10000",
      "pressao_atmosferica [mb]": 1012,
      "condicao_nuvem": {"nuvem": []},
      "vento": {"vento [KT]": 4, "direcao_do_vento [graus]": 130}
    }
  ]
}
```

Campos podem faltar. `condicao_nuvem` e `vento` podem ser objeto ou a string
`"informacao ausente"`. Consumidores precisam tratar os dois casos.

### 4.3 JSONs inválidos

Doze arquivos do acervo histórico contêm dois objetos JSON concatenados, sem
separador. Eles não passam em `json.load`; a lista e o exemplo estão em
`docs/03-dados-e-saidas.md` (seção 6.1). Desde a Fase 2, novas execuções gravam
com `"w"` em `.tmp`, `fsync` e `os.replace`, sobrescrevendo a mesma estação +
timestamp, e o timestamp é resolvido contra uma referência UTC com rollover
(D-07/D-08). O consumidor ainda deve decidir entre rejeitar, reparar ou ignorar
os 12 arquivos antigos; eles não são corrigidos retroativamente.

## 5. Consumidores conhecidos

| Consumidor | Entrada | O que espera |
|---|---|---|
| BlueSky | `matrizGrib/bluesky/AAAAMMDD/HH/*.csv` | `lat,lon,hMET,angMET,vento_resultante`; pés, graus, nós; linhas na ordem atual |
| Preditor | `matrizGrib/predi/AAAAMMDD/HH/*.csv` | `lat,lon,vento U,vento V,temp`; m/s, m/s, K |
| Planilhas/sites/usuários | `matrizGrib/AAAAMMDD/HH/*.csv` e PNGs | `lat,lon,<var>`; °C para temperatura, hPa para pressão; nomes e ordem estáveis |
| Parsers METAR | `METARpy/AAAAMMDD/*.json` | Chaves com espaço no bruto; campos opcionais no traduzido; JSON válido |
| Agendador/cron | Nomes de arquivos e diretórios | Padrões `AAAAMMDD/HH` e prefixos `GFS_`; retenção por nome |

O código dos consumidores externos (BlueSky e preditor) não está neste
repositório. Os contratos acima são inferidos dos schemas gerados e da
documentação existente; qualquer mudança deve ser confirmada com os
responsáveis antes de alterar o schema.

## 6. O que não pode mudar

1. Nomes e ordem das colunas de todos os CSV.
2. Ordem das linhas: `lat` crescente e `lon` crescente no recorte atual.
3. Padrões de nome de arquivo e diretório.
4. Unidades efetivas: °C, hPa, %, kg m⁻², m/s, nós, pés, K.
5. Nomes das variáveis e produtos: `temp`, `temps`, `prnm`, `nuvem`,
   `chuvaNaoConvec`, `winds`, `wind`, `CampoVento`, etc.
6. `goGribV2.sh`, suas URLs, ciclos, previsões e resoluções.
7. Chaves METAR existentes, inclusive os espaços no JSON bruto.

## 7. Mudanças permitidas nas Fases 1 e 2

- Corrigir a ordem/alinhamento dos dados sem mudar a ordem das linhas.
- Corrigir a componente V sem mudar o header `vento V`.
- Corrigir `hMET` para metros → pés sem mudar o header.
- Normalizar `angMET` para `[0, 360)` sem mudar o header.
- Corrigir a seleção de ciclo sem mudar os nomes dos diretórios.
- Corrigir a conversão de unidades onde o valor está errado, mantendo a unidade
  documentada.
- Gerar `winds -ns` no controlador e remover chamadas no-op/duplicadas.
- Trocar `umidadeRel -ns` por `-n 850`, mantendo o nome e o seletor de pressão.
- Reescrever o CLI MAN com `argparse`, mantendo todas as flags e os padrões de
  saída.
- Gravar METAR de forma atômica e com timestamp UTC, mantendo os schemas.
- Documentar a semântica de `chuvaNaoConvec`/`temps` e o rótulo `+6`.
- Adicionar testes e documentação.

## 8. Testes de contrato

Os testes que protegem headers e unidades passam hoje:

- `test_matriz_escalar_cabecalho_atual`
- `test_bluesky_cabecalho_atual`
- `test_preditor_cabecalho_atual`
- `test_man_bluesky_cabecalho_atual`
- `test_bluesky_resultante_em_nos`
- `test_man_bluesky_*` (headers e schemas)

Os contratos que descrevem as correções da Fase 1 estão verdes e **não** usam
mais `xfail`:

| Defeito | Contrato desejado |
|---|---|
| D-01 | Primeira linha do CSV (latitude mínima) deve conter o dado da latitude mínima. |
| D-02 | `vento V` do preditor e a componente V do mapa superficial devem usar `vSupe`. |
| D-03 | `hMET` de `winds` deve ser `metros × 3,28084`, não a fórmula de pressão. |
| D-04 | 06:30 → ciclo 06; 00:30 → ciclo 00 do mesmo dia. |
| D-12 | `angMET` em `[0, 360)`. |

Na Fase 0 esses contratos estavam marcados com `xfail(strict=True)`; os 20
marcadores foram removidos após as correções e os testes passaram a protegê-las
permanentemente. Detalhes e comandos estão em `tests/README.md` e
[docs/09-fase-1-resultados.md](09-fase-1-resultados.md).

Os contratos da Fase 2 também estão verdes em
`tests/test_phase2_acceptance.py`:

| Item | Contrato desejado |
|---|---|
| D-05 | Controlador chama `winds -ns`; não há bloco duplicado nem chamada no-op; `winds` gera mapas e matrizes. |
| D-06 | `umidadeRel -ns` retorna erro claro com `-n 850`; `umidadeRel -n 850` gera CSV/PNG em 0–100. |
| D-07 | Reexecução do METAR sobrescreve o arquivo, sem concatenar; JSON sempre válido. |
| D-08 | Timestamp e diretório usam a mesma referência UTC e resolvem rollover de mês/ano. |
| D-09 | `200→500` e `500→200` produzem a mesma lista crescente; fora de 150–1000 hPa retorna erro 2. |
| D-10 | Limpeza remove somente o dia `hoje - 2`, incluindo `0p25`, `1p00`, legados e produtos. |
| D-13/D-24 | Nome `chuvaNaoConvec` e rótulo `+6` preservados; semântica documentada. |
| D-14/D-28 | Flags do MAN em qualquer ordem; `chuva`/`MN` rejeitados; help e `set -euo pipefail`. |
| D-15 | Matriz MAN escalar gerada uma única vez. |
| D-17 | `9999` sem nuvem → `"10000"`; com nuvem → `"superior a 10000"`. |
| D-25 | `automatizaMetar.sh` sem variáveis indefinidas e com referência UTC única. |
| D-27 | `temps` documentado como temperatura de pele; seletor preservado. |

## 9. Decisões e pendências

- O header `nivel<hPa>` do MAN para `winds` permanece, apesar de o valor ser em
  metros. Mudança seria schema v2.
- O header `hMET` do AUT/BlueSky não tem unidade; a unidade é pés por contrato
  documentado.
- O header `temp` do preditor é Kelvin; o header `temp` das matrizes escalares é
  Celsius. Não unificar sem schema v2.
- `chuvaNaoConvec` continua com esse nome, embora o dado seja precipitação total
  (D-13), e o rótulo `+6` do arquivo continua sendo histórico (D-24).
- `temps` continua sendo temperatura de pele, não do ar a 2 m (D-27).
- `winds` foi ativado no controlador na Fase 2, depois de D-01, D-02 e D-03
  estarem corrigidos e testados (D-05).
- O JSON METAR bruto mantém as chaves com espaço final; a escrita nova é atômica
  e UTC, mas os 12 arquivos históricos inválidos não são reparados
  automaticamente (D-07/D-08).
- Ainda pendente para a Fase 3: `exit 1` do controlador (D-16), sanitização de
  caminho/região (D-18), limpeza de artefatos (D-19), logging/lock (D-20),
  `ponto_regiao` (D-21), `varMET` global (D-22), `controla_env` (D-23) e
  fechamento de figuras/GRIB (D-26).
