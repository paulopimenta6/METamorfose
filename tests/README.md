# Testes das Fases 0, 1 e 2

Este diretório contém o harness da Fase 0 e as suítes de aceitação das Fases 1
e 2. O harness foi criado antes das correções de cálculo para transformar os
defeitos conhecidos em contratos executáveis; as suítes das fases seguintes
passaram a exigir o comportamento corrigido.

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

# relatório resumido de falhas, skips e xfails
python3 -m pytest -q -ra

# apenas os contratos que não precisam da amostra real
python3 -m pytest -q tests/test_phase0_freeze.py tests/test_phase0_calculations.py \
  tests/test_phase0_orientation.py tests/test_phase0_cycle.py

# apenas a validação com GRIB real
python3 -m pytest -q tests/test_phase0_real_grib.py

# apenas a aceitação da Fase 0 (inclui verificação dos remotos)
python3 -m pytest -q -m acceptance

# apenas a aceitação da Fase 1 (T-01 a T-05)
python3 -m pytest -q tests/test_phase1_acceptance.py

# apenas a aceitação da Fase 2 (T-06 a T-12)
python3 -m pytest -q tests/test_phase2_acceptance.py

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
`skip`. Na Fase 0 a suíte terminava com 40 `passed` e 20 `xfailed`; esses 20
contratos foram corrigidos na Fase 1 e hoje passam sem `xfail`.

## Aceitação da Fase 1

`tests/test_phase1_acceptance.py` cobre os critérios T-01 a T-05 do
[plano](../docs/06-plano-de-melhorias-e-variaveis.md):

- T-01: orientação norte-sul em CSVs e mapas, AUT e MAN, inclusive `flag == 3`;
- T-02: componentes U/V, resultante e regressões estruturais do mapa e do
  preditor automáticos;
- T-03: `hMET`/`halt` para 20/30/40/50/80 m e para níveis de pressão;
- T-04: `angMET` nos quatro quadrantes e em toda a grade;
- T-05: fronteiras de ciclo, meia-noite, ciclo ausente e fallback de resolução.

A suíte tem **65 testes** (27 funções, várias parametrizadas) e não usa `xfail`
para os defeitos corrigidos. A suíte completa, sem os testes de rede, termina
com **123 passed** e 3 `deselected`. O resultado detalhado da fase está em
[docs/09-fase-1-resultados.md](../docs/09-fase-1-resultados.md).

## Aceitação da Fase 2

`tests/test_phase2_acceptance.py` cobre os critérios T-06 a T-12 do
[plano](../docs/06-plano-de-melhorias-e-variaveis.md):

- T-06: `umidadeRel -ns` falha com mensagem clara; `-n 850` funciona no AUT e
  no MAN;
- T-07: controlador ativa `winds` sem bloco duplicado; mapas e matrizes são
  gerados; produtos reais de 20/30/40/50/80 m são conferidos;
- T-06: `umidadeRel` rejeita superfície, aceita 850 hPa e preserva `N850` no mapa;
- T-08: referência UTC com rollover, sobrescrita atômica e ausência de
  concatenação;
- T-09: intervalo MAN nas duas ordens, níveis iguais e limites 150–1000 hPa;
- T-10: limpeza do dia `hoje - 2` em viradas de mês, `0p25`/`1p00`/legados,
  diretórios de produtos e datas de calendário inválidas;
- T-11: `-v chuva` e `MN` rejeitados; limites 150–1000 hPa; help derivado do
  catálogo; flags fora de ordem; sem argumento duplicado;
- T-12: visibilidade METAR com nuvem ausente/presente e valores não `9999`.

A suíte tem **36 testes** (29 funções, algumas parametrizadas). A suíte completa
termina com **162 passed**. O resultado detalhado está em
[docs/10-fase-2-resultados.md](../docs/10-fase-2-resultados.md).

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

## Histórico dos `xfail` e contratos da Fase 1

Na Fase 0, os testes que descreviam o comportamento **desejado** usavam
`@pytest.mark.xfail(strict=True)`. Eles falhavam porque o código original tinha
os defeitos diagnosticados; os 20 marcadores foram removidos na Fase 1, quando
cada defeito foi corrigido. Hoje os mesmos testes passam e protegem a correção
permanentemente.

| Defeito | Testes principais | Comportamento exigido |
|---|---|---|
| D-01 | `test_matriz_escalar_primeira_linha_deve_ser_o_sul`, `test_bluesky_primeira_linha_deve_ser_o_sul`, `test_preditor_primeira_linha_deve_ser_o_sul` | A primeira linha do CSV (latitude mínima) deve conter o dado da latitude mínima, não o dado do norte. |
| D-02 | `test_aut_preditor_deve_receber_v_comp_supe`, `test_mapa_vento_superficial_deve_ler_v_supe` | O preditor e o mapa de `winds` devem usar `vSupe` como componente V. |
| D-03 | `test_altura_em_metros_deveria_ser_convertida_por_3_28084`, `test_bluesky_altitude_de_20_metros`, `test_man_bluesky_altitude_de_20_metros` | `hMET` de 20 m deve ser 65,6168 ft (`20 × 3,28084`), não a conversão de pressão. |
| D-04 | `test_ciclo_0630_deve_escolher_o_ciclo_06`, `test_ciclo_0030_usa_o_ciclo_00_do_mesmo_dia` | Às 06:30 deve ser usado o ciclo 06 do mesmo dia; às 00:30, o ciclo 00 do mesmo dia. |
| D-12 | `test_angmet_quadrantes_negativos_devem_ser_normalizados`, `test_bluesky_angulo_de_vento_de_oeste`, `test_man_bluesky_angulo_de_vento_de_oeste` | `angMET` deve estar em `[0, 360)`, inclusive para vento de oeste e noroeste. |

Os testes que nunca foram `xfail` protegem o que **não** pode mudar: nomes de
headers, conversão Kelvin → Celsius, resultante em nós, altitude de pressão em
850/500 hPa e o congelamento do `goGribV2.sh`.

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

## Reprocessamento da Fase 1

O reprocessamento usa o código corrigido, grava em
`reprocessamento/reports/20261022-00/` e nunca sobrescreve o baseline:

```bash
python3 reprocessamento/run_reprocessamento.py
python3 reprocessamento/validar_fase1.py
```

O runner aceita `--resume` para preservar `reprocessamento/run/` e pular os
comandos cujo log já existe. A validação independente é um passo separado: ela
relê a amostra com `pygrib`, compara os 13 CSVs linha a linha e grava
`validation.json`. O resultado esperado é **158 verificações e 0 falhas**,
incluindo o ciclo `00` nos seis logs de execução.

## Validação da Fase 2

A Fase 2 não regera os produtos da Fase 1; ela valida os produtos de `winds` já
reprocessados e os comportamentos de CLI, METAR e limpeza:

```bash
python3 reprocessamento/validar_fase2.py
```

O validador confere os invariantes (Fase 1 `ok`, 20 produtos preservados,
baseline limpo e `goGribV2.sh` congelado), relê os produtos `winds` com
`pygrib`, exercita os wrappers e scripts em diretórios temporários e grava
`reprocessamento/reports/fase-2/validation.json` e `pytest.txt`. O resultado
esperado é **177 verificações e 0 falhas**.

## Limitações

- Os testes sintéticos verificam contratos de código, não a qualidade
  meteorológica dos produtos.
- Os testes reais verificam 20 mensagens e um ponto de São Paulo; não cobrem
  todas as variáveis, níveis ou regiões.
- Os mapas PNG não são comparados pixel a pixel; a evidência de orientação e de
  vento vem dos CSVs e das funções que também alimentam os mapas.
- O baseline é intencionalmente incorreto e não deve ser usado como referência
  operacional.
