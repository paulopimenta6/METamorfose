# Testes da Fase 0

Este diretório contém o harness de testes criado antes de qualquer correção de
cálculo. O objetivo é transformar os defeitos conhecidos em contratos
executáveis, sem alterar o código de produção.

## Pré-requisitos

- Python 3.11 ou compatível.
- `pytest`, `numpy`, `matplotlib`, `pygrib` e `basemap`.
- A amostra GFS de `baseline/samples/` para os testes marcados como reais.
- Para a aceitação da Fase 0: o backup local, a amostra binária e acesso aos
  remotes `melhorias` e `origin`.

No ambiente usado na Fase 0:

```text
Python 3.11.14
pytest 9.0.2
numpy 2.3.5
matplotlib 3.10.0
pygrib 2.1.8
basemap 2.0.0
```

## Comandos

```bash
# suíte completa
python3 -m pytest -q

# mostra o motivo de cada xfail
python3 -m pytest -q -rx

# apenas os contratos que não precisam da amostra real
python3 -m pytest -q tests/test_phase0_freeze.py tests/test_phase0_calculations.py \
  tests/test_phase0_orientation.py tests/test_phase0_cycle.py

# apenas a validação com GRIB real
python3 -m pytest -q tests/test_phase0_real_grib.py

# apenas a aceitação da Fase 0 (inclui verificação dos remotos)
python3 -m pytest -q -m acceptance

# aceitação sem rede
python3 -m pytest -q -m "acceptance and not network"
```

A configuração `pytest.ini` limita a descoberta a `tests/`, adiciona `-ra` ao
relatório final e registra os markers `acceptance` e `network`.

## Aceitação da Fase 0

`tests/test_phase0_acceptance.py` valida os entregáveis da fase, não as
correções futuras. Ele cobre:

- backup, amostra binária, sidecar e `goGribV2.sh` por tamanho e SHA-256;
- os 20 produtos, 13 CSVs e 7 PNGs do baseline, com hashes do `summary.json`;
- headers, quantidade de linhas, ordem `lat`/`lon` e CRLF dos CSVs;
- as evidências congeladas de D-01, D-02, D-03 e D-12;
- documentação, manifesto e ausência de alteração no código de produção;
- presença da amostra binária apenas fora do Git;
- tags e branches nos remotes `melhorias` e `origin`.

A suíte é intencionalmente estrita: se o backup, a amostra ou um remoto
obrigatório estiverem ausentes, o teste **falha** com uma mensagem explícita.
Os testes que consultam a rede usam o marker `network` e podem ser excluídos
com `-m "not network"`; nesse caso eles aparecem como `deselected`, não como
`skip`. A aceitação só é considerada concluída quando a suíte completa termina
com zero falhas, zero `skip` e os 20 `xfail` esperados.

## Amostra real

O arquivo completo `gfs.t00z.pgrb2.0p25.f000` de 2026-10-22/00 tem
489.780.434 bytes. Baixar o arquivo inteiro seria desnecessário para os testes.
O script `tests/fetch_gfs_sample.py` lê o `.idx` do NOMADS e baixa apenas as 20
mensagens usadas, via HTTP `Range`:

```bash
python3 tests/fetch_gfs_sample.py
```

O resultado é:

```text
baseline/samples/gfs.20261022.00.0p25.subset.grb2
baseline/samples/gfs.20261022.00.0p25.subset.grb2.json
```

O `.grb2` é ignorado pelo Git; o sidecar JSON é versionado e registra URL,
ranges, hashes e o ponto de referência de São Paulo. Se a amostra não existir,
os quatro testes de `test_phase0_real_grib.py` são marcados como `skip`, e o
restante da suíte continua funcionando sem rede.

Para forçar um novo download:

```bash
python3 tests/fetch_gfs_sample.py --force
```

## Semântica dos `xfail`

Os testes que descrevem o comportamento **desejado** usam
`@pytest.mark.xfail(strict=True)`. Eles falham hoje porque o código de produção
ainda tem os defeitos da Fase 0. O `strict=True` é intencional:

- enquanto o defeito existir, o teste é contabilizado como `xfailed`;
- quando a correção for aplicada, o teste passa e o pytest passa a reportar
  `XPASS(strict)`, que é uma falha;
- nesse momento, o marcador deve ser removido e o teste passa a proteger a
  correção permanentemente.

Não remova um `xfail` sem corrigir o código; não marque um teste como `skip`
para esconder uma regressão.

### Grupos de contratos

| Defeito | Testes principais | Comportamento esperado após a correção |
|---|---|---|
| D-01 | `test_matriz_escalar_primeira_linha_deve_ser_o_sul`, `test_bluesky_primeira_linha_deve_ser_o_sul`, `test_preditor_primeira_linha_deve_ser_o_sul` | A primeira linha do CSV (latitude mínima) deve conter o dado da latitude mínima, não o dado do norte. |
| D-02 | `test_aut_preditor_deve_receber_v_comp_supe`, `test_mapa_vento_superficial_deve_ler_v_supe` | O preditor e o mapa de `winds` devem usar `vSupe` como componente V. |
| D-03 | `test_altura_em_metros_deveria_ser_convertida_por_3_28084`, `test_bluesky_altitude_de_20_metros`, `test_man_bluesky_altitude_de_20_metros` | `hMET` de 20 m deve ser 65,6168 ft (`20 × 3,28084`), não a conversão de pressão. |
| D-04 | `test_ciclo_0630_deve_escolher_o_ciclo_06`, `test_ciclo_0030_deve_usar_o_18_do_dia_anterior` | Às 06:30 deve ser usado o ciclo 06 do mesmo dia; às 00:30, o ciclo 18 do dia anterior. |
| D-12 | `test_angmet_quadrantes_negativos_devem_ser_normalizados`, `test_bluesky_angulo_de_vento_de_oeste`, `test_man_bluesky_angulo_de_vento_de_oeste` | `angMET` deve estar em `[0, 360)`, inclusive para vento de oeste e noroeste. |

Os testes que passam hoje protegem o que **não** pode mudar: nomes de headers,
conversão Kelvin → Celsius, resultante em nós, altitude de pressão em 850/500 hPa
e o congelamento do `goGribV2.sh`.

## Harness sem efeitos colaterais

`tests/phase0_harness.py` não importa os scripts de produção diretamente. Isso
evita executar `parse_param(sys.argv)` e instanciar `controla_env` (que lê
`../environment/path.conf` e cria diretórios) durante a coleta de testes.

Em vez disso, o harness:

1. lê o arquivo de produção com `ast`;
2. extrai a função desejada;
3. executa a função em um namespace controlado, com `pygrib` falso quando
   necessário;
4. usa `FakeDirSave` para redirecionar saídas para `tmp_path`.

Os testes de orientação rodam as funções reais `gera_matriz`/`gera_matriz_vento`
com arrays sintéticos. O `FakeGRIB` imita a API mínima usada pelo código:
`data()`, `latlons()`, `dataDate`, `forecastTime`, `iDirectionIncrementInDegrees`,
`name`, `typeOfLevel` e `level`.

## Baseline

O baseline é gerado separadamente, com o código de produção copiado para uma
árvore temporária e `environment/path.conf` apontando para essa árvore:

```bash
python3 tests/fetch_gfs_sample.py   # se a amostra ainda não existir
python3 baseline/run_baseline.py
```

O comando não escreve em `/media/MET`. O resultado fica em
`baseline/reports/20261022-00/`. Para o baseline, a amostra `f000` é copiada
para `f006/f012/f018` apenas para satisfazer o loop do leitor atual; todas as
mensagens têm `forecastTime=0`, então o baseline representa somente `f000`.

## Limitações

- Os testes sintéticos verificam contratos de código, não a qualidade
  meteorológica dos produtos.
- Os testes reais verificam 20 mensagens e um ponto de São Paulo; não cobrem
  todas as variáveis, níveis ou regiões.
- Os mapas PNG não são comparados pixel a pixel; a evidência de orientação e de
  vento vem dos CSVs e das funções que também alimentam os mapas.
- O baseline é intencionalmente incorreto e não deve ser usado como referência
  operacional.
