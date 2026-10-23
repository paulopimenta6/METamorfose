# 03 — Dados e saídas

Este documento descreve os dados de entrada, as variáveis suportadas, os níveis, as regiões, os padrões de nomes e os schemas de saída.

> Os diretórios `gribs/`, `mapasGrib/` e `matrizGrib/` deste checkout estão vazios. Os dados METAR históricos estão presentes e foram inventariados. As informações de GRIB e de produtos foram extraídas do código e validadas com uma amostra real de GFS 0.25° do NOMADS.

## 1. Estrutura de diretórios

```text
/media/MET/servidor_MET/
├── bash/
│   ├── automatizacao_controle_MET.sh
│   ├── automatiza_MET.sh
│   ├── automatiza_vento_MET.sh
│   └── reqs_MAN_MET.sh
├── classes_MET/
│   ├── controla_env.py
│   ├── leitura_dados_grib_MET.py
│   ├── processamento_dados_MET.py
│   ├── parse_param_MET.py
│   ├── regioes_predefinidas_MET.py
│   ├── ponto_regiao_MET.py
│   ├── poligono_regiao_MET.py
│   ├── gera_mapas_MET.py
│   ├── gera_matriz_MET.py
│   ├── gera_mapas_vento_MET.py
│   ├── gera_matriz_vento_MET.py
│   ├── executa_reqs_param.py
│   ├── gera_mapas_MAN_MET.py
│   ├── gera_matriz_MAN_MET.py
│   ├── gera_mapas_vento_MAN_MET.py
│   └── gera_matriz_vento_MAN_MET.py
├── environment/
│   └── path.conf
├── gribs/
│   └── AAAAMMDD/
│       └── CC/
│           ├── gfs.tCCz.pgrb2.0p25.f0FF
│           ├── gfs.tCCz.pgrb2.1p00.f0FF
│           └── (opcional) gfs.tCCz.pgrb2.0p50.f0FF
├── mapasGrib/
│   └── AAAAMMDD/
│       └── HH/
│           └── *.png
├── matrizGrib/
│   ├── AAAAMMDD/
│   │   └── HH/
│   │       └── *.csv
│   ├── bluesky/
│   │   └── AAAAMMDD/
│   │       └── HH/
│   │           └── *.csv
│   └── predi/
│       └── AAAAMMDD/
│           └── HH/
│               └── *.csv
├── METARpy/
│   ├── AAAAMMDD/
│   │   ├── <ICAO><AAAAMMDDHHMM>.json
│   │   └── <ICAO><AAAAMMDDHHMM>_traduzido.json
│   ├── METARpy.py
│   ├── METARpy_traduzido.py
│   ├── GoMETAR.py
│   ├── automatizaMetar.sh
│   └── (vendor PythonMETAR)
├── goGribV2.sh
└── remove_GRIBS_antigos.sh
```

### Configuração

`environment/path.conf`:

```ini
dir_gribs=/media/MET/servidor_MET/gribs
dir_mapas=/media/MET/servidor_MET/mapasGrib
dir_matrizes=/media/MET/servidor_MET/matrizGrib
dir_matrizes_predi=/media/MET/servidor_MET/matrizGrib/predi
dir_matrizes_bluesky=/media/MET/servidor_MET/matrizGrib/bluesky
```

`controla_env.py` lê esse arquivo por caminho relativo (`../environment/path.conf`), portanto os processos Python devem ser executados a partir de `classes_MET/` ou de `bash/`. O diretório de trabalho importa.

## 2. Dados de entrada GFS

### 2.1 Nome dos arquivos

```text
gfs.tCCz.pgrb2.0p25.f0FF
gfs.tCCz.pgrb2.1p00.f0FF
gfs.tCCz.pgrb2.0p50.f0FF   (opcional, não baixado)
gfsAAAAMMDDCC00_000.grb    (legado)
```

- `CC` = ciclo (`00`, `06`, `12`, `18`).
- `FF` = previsão (`00`, `06`, `12`, `18`).
- `f000` é a análise; `f006`, `f012`, `f018` são previsões.
- O script de download grava `0p25` e `1p00`. A leitura tenta `0p25`, `0p50`, `1p00` e o legado, nessa ordem.

### 2.2 Mensagens usadas

O GFS 0.25° do NOMADS contém, entre outras, mensagens com `typeOfLevel`:

- `surface`;
- `meanSea`;
- `isobaricInhPa` (níveis de pressão em hPa);
- `heightAboveGround` (alturas de 2, 10, 20, 30, 40, 50, 80, 100 m etc.);
- `isobaricInPa` (níveis em Pa; **não usados** pelo código);
- `planetaryBoundaryLayer`, `hybrid`, `atmosphere` etc. (**não usados**).

O código seleciona por `name` + `typeOfLevel`. Isso significa que ele ignora `isobaricInPa` e outras codificações equivalentes, e depende dos nomes exatos do GFS.

### 2.3 Variáveis suportadas

| Chave usada | Nome GFS (`name`) | `typeOfLevel` | Níveis usados | Conversões | Observação |
|---|---|---|---|---|---|
| `ps` | `Surface pressure` | `surface` | Superfície | Pa → hPa nos mapas/matrizes | Presente no dicionário; comentado no controlador |
| `prnm` | `Pressure reduced to MSL` | `meanSea` | Superfície | Pa → hPa | Usado no controlador |
| `temp` | `Temperature` | `isobaricInhPa` | 150–1000 hPa (snap) | K → °C | Usado no controlador |
| `temps` | `Temperature` | `surface` | Superfície | K → °C | Usado no controlador |
| `nuvem` | `Total Cloud Cover` | `isobaricInhPa` | 150–1000 hPa (snap) | — | Usado no controlador |
| `chuvaNaoConvec` | `Total Precipitation` | `surface` | Superfície | kg m⁻² ≈ mm | **É precipitação total**, apesar do nome |
| `chuvaConvec` | `Convective precipitation (water)` | `surface` | Superfície | kg m⁻² ≈ mm | Precipitação convectiva |
| `umidadeRel` | `Relative humidity` | `isobaricInhPa` | 150–1000 hPa | — | **Não funciona em superfície** |
| `u` | `U component of wind` | `isobaricInhPa` | 150–1000 hPa | — | Componente zonal (m/s) |
| `v` | `V component of wind` | `isobaricInhPa` | 150–1000 hPa | — | Componente meridional (m/s) |
| `uSupe` | `U component of wind` | `heightAboveGround` | 20, 30, 40, 50, 80 m | — | Usado por `winds` |
| `vSupe` | `V component of wind` | `heightAboveGround` | 20, 30, 40, 50, 80 m | — | Usado por `winds` |

Observações:

- A chave `chuva` citada no help do `reqs_MAN_MET.sh:27` **não existe** no dicionário. Use `chuvaConvec` ou `chuvaNaoConvec`.
- O dicionário também não tem `wind`/`winds`; esses nomes são tratados pelas classes de vento, que internamente usam `u`/`v` e `uSupe`/`vSupe`.
- `umidadeRel` só tem mensagens em `isobaricInhPa` no mapeamento atual; no GFS 0.25° o campo de 2 m é `2 metre relative humidity` em `heightAboveGround` (nível 2), mas o código não o mapeia (D-06). Alternativa: calcular a partir de temperatura e ponto de orvalho.

### 2.4 Níveis de pressão aceitos

Lista usada no fluxo manual (`executa_reqs_param.py:52`):

```text
150, 200, 250, 300, 350, 400, 450, 500, 550, 600,
650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 hPa
```

Regras de arredondamento:

- O nível é aproximado para o nível GFS mais próximo.
- Se o ponto médio entre dois níveis for atingido ou ultrapassado, o nível superior é escolhido.
- Valores abaixo de 150 hPa são fixados em 150; valores acima de 1000 hPa são fixados em 1000.
- O AUT usa listas de níveis reais do GRIB, filtradas para `>= 150`, e faz o mesmo tipo de “snap”.

### 2.5 Níveis de altura usados para vento superficial

```text
20 m, 30 m, 40 m, 50 m, 80 m
```

No GFS 0.25°, esses níveis vêm em `heightAboveGround` e unidades `m s**-1`. O código os trata como “quase-superfície” para o produto `winds`.

## 3. Regiões predefinidas

Definidas em `regioes_predefinidas_MET.py:25-99`:

| Nome | Longitude mín. | Longitude máx. | Latitude mín. | Latitude máx. |
|---|---:|---:|---:|---:|
| SP | -56 | -42 | -28 | -18 |
| RJ | -46 | -36 | -27 | -17 |
| AM | -65 | -55 | -7 | 7 |
| DF | -54 | -44 | -20 | -10 |
| PR | -54 | -44 | -30 | -20 |
| RS | -56 | -46 | -34 | -24 |
| MG | -48 | -38 | -24 | -14 |
| PA | -53 | -43 | -6 | 4 |
| PE | -39 | -29 | -13 | -3 |
| CE | -43 | -33 | -8 | 2 |
| SA | -100 | -20 | -60 | 25 |

Observações:

- A chave de Manaus é `AM`, não `MN`. O help do AUT cita `MN`, mas `MN` não existe no dicionário e causaria `KeyError`.
- A chave `SA` cobre praticamente toda a América do Sul.
- `-ll lon lat` cria uma caixa de ±5° em torno do ponto (`ponto_regiao_MET.py`), não uma caixa arbitrária.
- O nome da região nos produtos AUT é `SP`, `RJ` etc. para regiões predefinidas, ou `lon<lon>_lat<lat>` para `-ll`.
- O MAN não usa regiões predefinidas; recebe bounding box explícita e monta a string `LonMin:... LonMax:... LatMin:... LatMax:...`.

## 4. Saídas do fluxo automático (AUT)

### 4.1 Mapas

```text
mapasGrib/AAAAMMDD/HH/GFS_<res>_<REGIAO>_N<nivel>_<var>_<ana>_<dataDate>_<ff>.png
```

| Campo | Descrição |
|---|---|
| `<res>` | `iDirectionIncrementInDegrees` (ex.: `0.25`, `0.5`, `1.0`) |
| `<REGIAO>` | Nome da região em maiúsculas, ou `lon<lon>_lat<lat>` |
| `<nivel>` | `superficie`, `surface` ou valor em hPa/m |
| `<var>` | Chave da variável (`temp`, `temps`, `nuvem`, `chuvaConvec` etc.) |
| `<ana>` | Ciclo calculado pela hora local (`00`, `06`, `12`, `18`) |
| `<dataDate>` | Data de referência do GRIB (`AAAAMMDD`) |
| `<ff>` | Tempo de previsão; para chuva, `forecastTime + 6` |

Atenção ao rótulo de superfície:

- Mapas de `temps`, `ps`, `prnm` e `umidadeRel` usam `Nsuperficie` (`gera_mapas_MET.py:158`).
- Mapas de `chuvaConvec`/`chuvaNaoConvec` usam `Nsurface`.
- Matrizes de `temps`, `ps` e `prnm` usam `Nsurface`, não `Nsuperficie`, porque `gera_matriz_MET.py` não faz a mesma substituição.
- Assim, para a mesma variável, o mapa e a matriz podem ter nomes de nível diferentes.

### 4.2 Matrizes escalares

```text
matrizGrib/AAAAMMDD/HH/GFS_<res>_<REGIAO>_N<nivel>_<var>_<ana>_<dataDate>_<ff>.csv
```

Colunas:

```csv
lat,lon,<var>
```

Unidades efetivas:

| Variável | Unidade no CSV |
|---|---|
| `temp`, `temps` | °C |
| `ps`, `prnm` | hPa |
| `nuvem` | % |
| `chuvaConvec`, `chuvaNaoConvec` | kg m⁻² (numericamente equivalente a mm) |
| `umidadeRel` | % (quando gerado) |
| `u`, `v` | m s⁻¹ |

### 4.3 Matrizes BlueSky

```text
matrizGrib/bluesky/AAAAMMDD/HH/GFS_<res>_matriz_lat_lon_alt_angMET_VentoResult_<REGIAO>_N<nivel>_<ana>_<dataDate>_<ff>.csv
```

Colunas (`gera_matriz_vento_MET.py:172`):

```csv
lat,lon,hMET,angMET,vento_resultante
```

| Coluna | Unidade | Observação |
|---|---|---|
| `lat` | graus | Latitude |
| `lon` | graus | Longitude |
| `hMET` | pés | Para `wind`, altitude de pressão; para `winds`, deveria ser a altura em metros convertida para pés, mas o código usa a fórmula de pressão (D-03) |
| `angMET` | graus | Direção meteorológica; pode sair negativa, sem normalização para 0–360 (D-12) |
| `vento_resultante` | nós | `sqrt(U² + V²) * 1.943` |

### 4.4 Matrizes do preditor

```text
matrizGrib/predi/AAAAMMDD/HH/GFS_<res>_matriz_lat_lon_Vento_UVT_Predi_<REGIAO>_N<nivel>_<ana>_<dataDate>_<ff>.csv
```

Colunas (`gera_matriz_vento_MET.py:292`):

```csv
lat,lon,vento U,vento V,temp
```

| Coluna | Unidade |
|---|---|
| `vento U` | m s⁻¹ |
| `vento V` | m s⁻¹ |
| `temp` | K |

Para `winds`, a temperatura usada é a de superfície (`temps`), não a temperatura do nível de 20/30/40/50/80 m.

### 4.5 Produtos de vento automáticos

Os dois scripts de vento têm papéis separados:

- `gera_mapas_vento_MET.py` gera apenas os mapas. Para `wind` (pressão), usa `u` e `v` no nível hPa; para `winds` (quase-superfície), percorre 20/30/40/50/80 m. Os arquivos saem como `..._CampoVento_...png` em `mapasGrib/...`.
- `gera_matriz_vento_MET.py` gera as matrizes BlueSky em `matrizGrib/bluesky/...` e as matrizes do preditor em `matrizGrib/predi/...`.

O controlador gera `wind` em 1000/200 hPa (linhas 20-24), mas as chamadas de `winds` (linhas 17-18) e o bloco duplicado de 1000/200 (linhas 62-65) são no-op (D-05). Portanto, os produtos de vento superficial só aparecem se o wrapper for executado manualmente com `-v winds -ns`; e, mesmo assim, os mapas e a matriz do preditor usam V=U (D-02) e a matriz BlueSky tem altitude errada (D-03).

## 5. Saídas do fluxo manual (MAN)

### 5.1 Mapas escalares

```text
<out>/GFS_<res>_<regiao>_N<nivel>_<var>_<ana>_<dataDate>_<prev>.png
```

`<regiao>` é a string `LonMin:<lonmin> LonMax:<lonmax> LatMin:<latmin> LatMax:<latmax>`, com espaços e dois-pontos. Exemplo:

```text
/tmp/saida/GFS_0.25_LonMin:-56.0 LonMax:-42.0 LatMin:-28.0 LatMax:-18.0_N500_temp_00_20221217_00.png
```

### 5.2 Matrizes escalares

```text
<out>/GFS_<res>_<regiao>_N<nivel>_<var>_<ana>_<dataDate>_<prev>.csv
```

Colunas:

```csv
lat,lon,<var>
```

O código chama `gera_matriz` duas vezes (`gera_matriz_MAN_MET.py:123-124`), sobrescrevendo o mesmo arquivo. O resultado final é igual, mas o trabalho é duplicado (D-15).

### 5.3 Mapas de vento

```text
<out>/GFS_<res>_<regiao>_N<nivel>_CampoVento_LC_<ana>_<dataDate>_<prev>.png
<out>/GFS_<res>_<regiao>_N<nivel>_CampoVento_barb_<ana>_<dataDate>_<prev>.png
<out>/GFS_<res>_<regiao>_N<nivel>_CampoVento_barbLC_<ana>_<dataDate>_<prev>.png
```

### 5.4 Matrizes de vento

```text
<out>/matriz_vento_<regiao>_N<nivel>_<ana>_<dataDate>_<prev>.csv
<out>/matriz_vento_bluesky_<regiao>_N<nivel>_<ana>_<dataDate>_<prev>.csv
<out>/matriz_vento_predi_<regiao>_N<nivel>_<ana>_<dataDate>_<prev>.csv
```

Schemas:

| Arquivo | Colunas | Unidades |
|---|---|---|
| `matriz_vento_...csv` | `lat,lon,nivel<hPa>,halt<feet>,angMET<grau>,vento U<ms**-1>,vento V<ms**-1>,vento_resultante<ms**-1>` | O header diz `nivel<hPa>`, mas para `winds` o valor é metros; `halt` usa a conversão errada para `winds`; resultado em m/s |
| `matriz_vento_bluesky_...csv` | `lat,lon,hMET<feet>,angMET<grau>,vento_resultante<knot>` | `hMET` errado para `winds`; direção pode ser negativa |
| `matriz_vento_predi_...csv` | `lat,lon,vento U,vento V,temperatura K` | U/V em m/s; temperatura conforme o nível |

Para `wind` (pressão), o MAN usa `u`/`v` do nível hPa e `temp` do mesmo nível. Para `winds` (superfície), usa `uSupe`/`vSupe` e `temps` de superfície.

### 5.5 Requisição MAN com intervalo

No flag 3:

- variáveis escalares: mapas e matrizes para cada nível do intervalo;
- vento: **somente mapas** (`executa_reqs_param.py:168` tem a chamada de matriz comentada).

O intervalo atual exige `min > max`; a ordem natural `min < max` causa `UnboundLocalError` (D-09).

## 6. Dados METAR

### 6.1 Inventário deste checkout

| Métrica | Valor |
|---|---:|
| Diretórios de data | 158 |
| JSONs totais | 16.044 |
| JSONs brutos | 8.085 |
| JSONs traduzidos | 7.959 |
| Brutos sem traduzido | 127 |
| Traduzidos sem bruto | 1 |
| JSONs inválidos | 12 |
| Período | 14/07/2021 a 17/12/2022 |

O diretório traduzido sem bruto é `SBGR202201010415`. Os brutos sem traduzido concentram-se no início da série (por exemplo, `SBBE20210714...`), sugerindo falha ou interrupção da tradução em parte do período.

Os 12 JSONs inválidos são causados por concatenação de dois objetos JSON no mesmo arquivo:

```text
METARpy/20220201/SBBE202202010300.json
METARpy/20220201/SBBE202202010300_traduzido.json
METARpy/20221125/SBBE202211250300.json
METARpy/20221125/SBBE202211250300_traduzido.json
METARpy/20210815/SBCF202108150300.json
METARpy/20210815/SBCF202108150300_traduzido.json
METARpy/20210719/SBPA202107190300_traduzido.json
METARpy/20210719/SBPA202107190300.json
METARpy/20221010/SBRF202210100300.json
METARpy/20221010/SBRF202210100300_traduzido.json
METARpy/20211219/SBBE202112190300.json
METARpy/20211219/SBBE202112190300_traduzido.json
```

Exemplo de conteúdo inválido:

```json
{"data": [{"id_localidade ": "SBBE", "data ": "202202010300", "mensagem_metar ": "SBBE 010300Z 06002KT CAVOK 25/23 Q1012"}]}{"data": [{"id_localidade ": "SBBE", "data ": "202202010300", "mensagem_metar ": "SBBE 010300Z 06002KT CAVOK 25/23 Q1012"}]}
```

### 6.2 Schema bruto

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

Campos:

| Campo | Tipo | Observação |
|---|---|---|
| `id_localidade ` | string | ICAO; **espaço no final do nome da chave** |
| `data ` | string | `AAAAMMDDHHMM`; **espaço no final** |
| `mensagem_metar ` | string | Texto METAR original; **espaço no final** |

### 6.3 Schema traduzido

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
      "condicao_nuvem": {
        "nuvem": [
          {
            "Tipo de nuvem ": "FEW",
            "Tipo de nuvem (nome completo) ": "Few",
            "Cobertura minima de nuvem [em oitavos]": "1",
            "Cobertura maxima de nuvem [em oitavos]": "2",
            "Altitude da nuvem [ft]": "1300"
          }
        ]
      },
      "vento": {
        "vento [KT]": 4,
        "rajada [KT]": "informacao ausente",
        "direcao_do_vento [graus]": 130,
        "coordenada_da_direcao_do_vento": "ESE",
        "variacao_do_vento": "informacao ausente"
      }
    }
  ]
}
```

Campos possíveis:

| Campo | Tipo | Observação |
|---|---|---|
| `estacao` | string | ICAO |
| `data` | string | `AAAAMMDDHHMM` |
| `mensagem_metar` | string | Texto original |
| `temperatura [C]` | número | Pode faltar em METAR sem temperatura |
| `temperatura_pto_orvalho [C]` | número | Pode faltar |
| `visibilidade [m]` | número ou string | Ex.: `9999`, `"superior a 10000"`, `"informacao ausente"` |
| `pressao_atmosferica [mb]` | número | QNH |
| `condicao_nuvem` | objeto ou string | `"informacao ausente"` quando não há nuvens |
| `vento` | objeto ou string | `"informacao ausente"` quando não há vento |
| `vento [KT]` | número | Velocidade em nós |
| `rajada [KT]` | número ou string | `"informacao ausente"` quando não há rajada |
| `direcao_do_vento [graus]` | número | Direção |
| `coordenada_da_direcao_do_vento` | string | Rosa dos ventos |
| `variacao_do_vento` | string | Variação, quando presente |

A chave `condicao_nuvem` pode ser um objeto `{"nuvem":[...]}` ou a string `"informacao ausente"`. O mesmo vale para `vento`. Consumidores precisam tratar os dois casos.

### 6.4 Limitações dos dados METAR

- O diretório usa a data local de execução, enquanto o timestamp do arquivo usa a observação. Em execuções perto da meia-noite, o diretório e o timestamp podem ter dias diferentes.
- Não há índice, banco ou catálogo; a descoberta é por varredura de diretórios.
- Não há garantia de que todas as estações tenham arquivo a cada hora.
- O nome da chave bruta tem espaços, o que quebra consumidores que usam `obj["id_localidade"]`.
- O JSON traduzido pode ter observação diferente do bruto, porque cada script consulta a NOAA separadamente.

## 7. Volumes e retenção

- GRIB: cada arquivo `0p25` do GFS completo tem centenas de MB; quatro previsões × quatro ciclos por dia podem consumir dezenas de GB.
- Produtos: PNGs e CSVs por variável, nível, região, análise e previsão.
- METAR: arquivos pequenos (alguns KB), mas milhares por ano.
- A retenção planejada é de 2 dias, implementada com bugs na virada do mês (D-10) e sem remover todas as resoluções/legados.
- Não há quota, alerta de disco ou rotação.

## 8. Qualidade dos dados

| Verificação | Resultado |
|---|---|
| JSONs METAR válidos | 16.032 de 16.044 (12 inválidos) |
| Bruto e traduzido pareados | 7.958 pares prováveis; 127 brutos sem tradução; 1 tradução sem bruto |
| Orientação das grades GFS | Invertida nos produtos: `lat` é revertida sem reverter `data` (D-01) |
| Vento superficial AUT | Mapas e matriz do preditor usam V=U; matriz BlueSky usa V correto, mas altitude errada (D-02/D-03) |
| Direção do vento | Não normalizada para 0–360 (D-12) |
| Ciclo GFS | Pode estar um ciclo atrasado na primeira hora (D-04) |
| Umidade superficial | Não há produto (D-06) |
| Precipitação “não convectiva” | É precipitação total (D-13) |

Recomenda-se executar uma validação de sanidade após qualquer correção:

1. Abrir um CSV de `temp` e conferir se a coluna `lat` e os valores são coerentes com um ponto conhecido do GFS.
2. Comparar U, V e direção de vento com um ponto de referência.
3. Conferir `hMET` para 20/30/40/50/80 m.
4. Validar todos os JSONs com `json.load`.
5. Conferir o ciclo usado no início de cada janela de 6 horas.
