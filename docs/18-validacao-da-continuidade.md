# Continuidade da Fase 4 — validação de 11–12/11/2026

## Implementação

- Preflight de instalação antes da substituição de arquivos.
- `--update-tools` atualiza ferramentas e manuais preservando a candidata,
  código instalado, GRIBs, produtos, configuração e aceite.
- Verificação do pacote candidato e da release ativa; rollback pode apontar
  para outra release íntegra sem transferir o aceite.
- Testes MAN sequenciais, diretórios únicos, logs e indicação do CSV correto.
- Verificação das três evidências por CLI, sem assinatura automática.
- README e guias de instalação, execução e aceitação revisados.

## Testes automatizados

Suíte completa executada no ambiente de desenvolvimento histórico:

```bash
python3 -m pytest -q
```

Resultado em 11/11: **247 passed**, incluindo os testes dos remotos Git.
São 23 regressões novas nesta rodada. A verificação cobre, entre outros casos:

- fontes inválidas antes de `--force`, com preservação byte a byte do destino;
- instalação de amostras cujo caminho original mudou;
- atualização de ferramentas preservando código, dados, configuração e aceite;
- falhas do verificador e do gerador propagadas pelos scripts;
- identificação da candidata mesmo quando outro código está ativo;
- integridade de `current/code`, links inválidos, promoção e rollback;
- registro recusado para hash de aceite divergente e conferência das três evidências.

## Ambiente de referência

Em 12/11, `--update-tools`, `verificar.sh` e `testar_todos.sh` foram executados
em `/home/paulo/MET/servidor_MET`.

| Verificação | Resultado |
|---|---|
| Candidata | `26fa746b3b7017f626c2121ba19bf416e3751280180cdd0424ad2100e908d196` |
| Ambiente | 12 GRIBs, 1.098 CSVs, 3 PNGs; 1.140 hashes das cópias instaladas; zero falhas |
| Contratos AUT | BlueSky 324, preditor 324, planilhas 450; zero falhas |
| Três testes MAN | Sucesso; 7 CSVs e 7 PNGs novos em `aceitacao-manual/` |
| Conteúdo operacional preexistente | 2.332 hashes de código, dados, configuração, aceite e registros; nenhum alterado ou removido |
| Aceite | `pending`, três evidências nulas |
| Ponteiros | `current` e `previous` continuam ausentes |

Logs técnicos desta execução, relativos à raiz instalada:

- `logs/bluesky-20261112T172909Z-pkR39n.log`
- `logs/preditor-20261112T173052Z-Fn27R9.log`
- `logs/planilhas-20261112T173201Z-NBNM1J.log`

Foram inspecionados visualmente o mapa MAN de temperatura em 850 hPa e o mapa
de vento com barbelas/linhas de corrente em 200 hPa: títulos, data, recorte,
orientação e escalas presentes. A conferência visual complementa os testes
numéricos e de contrato.

## Instalação limpa

A instalação é exercitada a partir de uma cópia limpa do conteúdo versionável,
sem os GRIBs locais, a candidata histórica ou a amostra binária da Fase 0.
As dependências foram instaladas em uma `.venv` Python 3.11 nova.

O comando portável documentado foi executado nessa cópia:

```bash
python3 -m pytest -q --ignore=tests/test_phase0_acceptance.py -m "not network"
```

Resultado: **225 passed, 4 skipped**. Os quatro skips são os testes da amostra
binária de 2026 da Fase 0, ausente nessa cópia. A campanha de 2022 é executada
separadamente com dados baixados para esta instalação.

O roteiro completo de instalação foi executado em 12/11:

| Etapa | Resultado |
|---|---|
| Dependências | Instaladas em `.venv`; imports de numpy, pygrib, matplotlib, Basemap e PythonMETAR OK |
| Download novo | `DONE 12 ERRORS 0` |
| Campanha independente | `status: ok`, 1.101 produtos, 108 pares METAR, nenhuma falha |
| Construção e instalação | 12 GRIBs, 1.098 CSVs e 3 PNGs |
| `verificar.sh` | Ambiente e três contratos com zero falhas; aceite pendente |
| `testar_todos.sh` | BlueSky, preditor e planilhas concluídos com dados reais |

Hash da release construída exclusivamente para esse ensaio:
`b36a39122170a165c41cba332bfb9bed034d18419c6ed1649be449d3e23282aa`.
Essa release não substituiu a candidata de referência. O código e os testes
da cópia limpa foram comparados byte a byte aos arquivos atuais do repositório.

Os logs técnicos, manifestos e resumos estão preservados localmente em
`reprocessamento/phase4-runs/continuity-20261112/` (diretório de artefatos
ignorado pelo Git). Os testes do ambiente de referência também mantêm seus
logs na raiz instalada, conforme os caminhos acima.

## Ensaio do código ativo e rollback

Na instalação temporária, com `--rehearsal`:

1. `promover.sh` com aceite pendente retornou **2**, antes de criar backup ou
   ponteiro `current`.
2. Duas releases reais foram promovidas em modo de ensaio. A verificação
   identificou corretamente `candidate-active` para a candidata nova.
3. Após `source ativar.sh`, uma geração MAN foi executada a partir de
   `$MET_ACTIVE_CODE`, produzindo 1 CSV e 1 PNG de temperatura em 850 hPa.
4. O pacote ativo continuou íntegro, sem criação de `.pyc`; o contrato do CSV
   recém-gerado passou.
5. O rollback reativou `26fa746b…` e o verificador mostrou
   `other-release-active`, mantendo o aceite ligado a `b36a3912…`.
6. O arquivo de aceite permaneceu byte a byte igual, com estado `pending`.

Resultado do ensaio: **status: ok**. O resumo está em
`reprocessamento/phase4-runs/continuity-20261112/met-docs-active-check.json`.
O ambiente de referência em `~/MET/servidor_MET` não foi promovido.

## Documentação e preservação

- Nove documentos de entrada/referência: links locais válidos e 73 blocos Bash
  com sintaxe válida.
- Onze scripts gerados: `bash -n` sem erros.
- Vinte e dois documentos instalados: nenhum link local ausente.
- Relatórios históricos das Fases 0–4 preservados.
- `goGribV2.sh` idêntico ao original, SHA-256
  `994ce16c1480b17a62b78e72761307af2000dc47819abbaf48ce042c72023ce0`.

## Aceite real

O aceite dos três usos permanece pendente. Ensaios automatizados usam ambientes
temporários e não constituem evidência de uso real de BlueSky, preditor ou
planilhas. Os relatórios históricos das fases anteriores permanecem preservados.
