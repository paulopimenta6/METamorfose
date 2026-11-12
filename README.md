# METamorfose

Transforma dados meteorológicos **GFS/GRIB2 em mapas PNG e tabelas CSV** e coleta
observações **METAR em JSON**. É a evolução do `servidor_MET`, executada em Linux
com Python e Bash.

Os CSVs atendem a três usos: seu código **BlueSky**, o **preditor** e **planilhas**.
Você pode gerar produtos para uma data específica pelo terminal (modo **MAN**)
ou processar os dados do dia (modo **AUT**).

## Comece aqui

| Sua situação | Siga este guia |
|---|---|
| Estou instalando pela primeira vez | [Instalação do zero](docs/17-instalacao-do-zero.md) |
| Já tenho `~/MET/servidor_MET` | [Executar e testar](docs/15-manual-testes-de-execucao.md) |
| Preciso validar os resultados e liberar uma versão | [Aceitação e promoção](docs/16-manual-de-aceitacao.md) |
| Quero entender pastas, configuração e atualização | [Referência do ambiente](docs/14-ambiente-de-producao-e-aceitacao.md) |

**Primeira instalação:** use Linux, Bash, Python 3.11, Git e curl. O guia do
zero inclui ambiente virtual, dependências, download dos dados, geração dos
produtos e instalação. **O clone Git não contém os GRIBs nem uma release pronta.**

## Já está instalado? Execute estes comandos

Abra um terminal **Bash** e execute um bloco por vez. `REPO` é a pasta do código;
`MET_ROOT` é a pasta do ambiente instalado. Ajuste somente esses caminhos se
necessário:

```bash
export REPO="$HOME/Documentos/meus_codigos/METamorfose"
export MET_ROOT="$HOME/MET/servidor_MET"
cd "$REPO"
```

Ative o Python que tem as dependências instaladas. Se seguiu a instalação do zero:

```bash
source "$REPO/.venv/bin/activate"
```

Quem já usa um ambiente Conda com as dependências deve ativá-lo em vez da `.venv`.
Atualize as ferramentas, confira o ambiente e gere as três amostras:

```bash
python3 reprocessamento/setup_production_env.py --root "$MET_ROOT" --update-tools
source "$MET_ROOT/bin/ativar.sh"
"$MET_ROOT/bin/verificar.sh"
```

**Esperado:** `falhas: 0` e `status: ok`. `state: pending` significa que falta
o aceite humano; os testes técnicos podem prosseguir.

```bash
"$MET_ROOT/bin/testar_todos.sh"
```

**Esperado:** `Os tres testes tecnicos passaram`. O terminal mostra os caminhos
dos CSVs, PNGs e logs. Os testes usam dados de **15/12/2022**, mesmo que hoje seja
outra data. Veja os detalhes no [manual de execução](docs/15-manual-testes-de-execucao.md).

## Onde estão os resultados?

Dentro de `$MET_ROOT`:

| Pasta | Conteúdo |
|---|---|
| `matrizGrib/AAAAMMDD/HH/` | CSVs escalares da release |
| `matrizGrib/bluesky/AAAAMMDD/HH/` | CSVs de vento para BlueSky |
| `matrizGrib/predi/AAAAMMDD/HH/` | CSVs para o preditor |
| `mapasGrib/AAAAMMDD/HH/` | Mapas PNG da release |
| `aceitacao-manual/` | Novos CSVs e PNGs dos testes MAN |
| `logs/` | Registro de cada teste técnico |
| `acceptance/` | Aceite e evidências dos três usos reais |

## Como os dados circulam

```text
GFS/GRIB2 → leitura e seleção → mapas PNG + matrizes CSV
                                                ├─ BlueSky
                                                ├─ preditor
                                                └─ planilhas
METAR/NOAA → coleta e tradução → JSON
```

O código BlueSky do projeto inclui `geraMatriz_Vento_Resu` (AUT) e
`met_gera_matriz_vento_man.gera_matriz_vento_bluesky` (MAN). O roteiro de testes
chama essas rotinas pelo fluxo correspondente. O aceite depende também da
conferência dos resultados no uso real.

### Unidades importantes

- BlueSky: altura em **pés**, direção meteorológica em **graus**, vento em **nós**.
- Preditor: U/V em **m/s**, temperatura em **Kelvin**.
- Escalares: `temp` e `temps` em **°C**, pressão em **hPa**, chuva em **mm**.
- `temps` significa **temperatura de pele**; `chuvaNaoConvec` significa
  **precipitação total**. Esses nomes são mantidos por compatibilidade.

## Situação do projeto

Fases 0–3 concluídas. A Fase 4 tem reprocessamento, validação local, instalação,
testes e ferramentas de promoção/rollback. **O aceite real dos três usos e a
promoção do ambiente de referência continuam pendentes.**

Cada aceite pertence ao SHA-256 exato de uma release. Gerar uma nova release
exige um novo aceite. Os resultados técnicos mais recentes ficam no
[relatório de continuidade](docs/18-validacao-da-continuidade.md).

## Para quem desenvolve ou opera o servidor

- [Testes automatizados](tests/README.md)
- [Operação AUT e METAR](docs/04-operacao.md)
- [Arquitetura, fluxos e histórico das fases](docs/README.md)
- [Contratos dos produtos](docs/08-contratos-e-consumidores.md)

O repositório [METamorfose](https://github.com/paulopimenta6/METamorfose) recebe
as melhorias em `execucao`, integradas em sua `main`. O repositório original
[`servidor_MET`](https://github.com/paulopimenta6/servidor_MET) preserva o snapshot.
No ambiente de desenvolvimento histórico, o remoto `melhorias` é METamorfose e
`origin` é o original. Em um clone novo de METamorfose, `origin` é METamorfose.

`goGribV2.sh`, os parâmetros de aquisição, os nomes dos produtos e os contratos
de saída permanecem preservados.
