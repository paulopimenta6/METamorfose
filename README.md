# METamorfose

Repositório de execução do plano de melhorias do `servidor_MET`.

O nome é uma junção de **MET** (meteorologia) com **metamorfose**: a ideia é transformar o sistema sem alterar seu catálogo de variáveis, seus produtos ou sua aquisição GRIB.

## Repositórios

| Repositório | Papel |
|---|---|
| [`servidor_MET`](https://github.com/paulopimenta6/servidor_MET) | Snapshot original, preservado na branch `main` |
| [`METamorfose`](https://github.com/paulopimenta6/METamorfose) | Ambiente de execução das melhorias |

## Branches

| Branch | Papel |
|---|---|
| `main` | Cópia fiel do snapshot original |
| `execucao` | Branch de integração das melhorias |

As fases do plano podem ser desenvolvidas em branches próprias (`fase-0`, `fase-1`, etc.) e integradas em `execucao` por pull request.

## Plano

O plano completo está em:

- [`docs/06-plano-de-melhorias-e-variaveis.md`](docs/06-plano-de-melhorias-e-variaveis.md)

Resumo das fases:

0. Preparação, backup, baseline e harness de testes.
1. Correções de cálculo: ciclo, orientação norte-sul, U/V, `hMET` e `angMET`.
2. Produtos, CLI e METAR.
3. Robustez operacional: atomicidade, logs, locks e fechamento de recursos.
4. Reprocessamento, validação e rollout.

## Restrições

- `goGribV2.sh` permanece congelado: ciclos `00/06/12/18`, previsões `f000/f006/f012/f018`, resoluções `0p25`/`1p00`, URLs e escopo não mudam.
- Nenhuma variável ou produto será renomeado, removido ou adicionado.
- Nomes de colunas, schemas e contratos existentes serão preservados, salvo decisão explícita de schema v2.
- Os nomes `chuvaNaoConvec` e `temps` permanecem; seus caveats serão documentados.

## Status

Fases 0–4 implementadas no worktree METamorfose. A Fase 4 foi validada
localmente; o aceite dos consumidores e a promoção em produção permanecem
pendentes. Resultados: [Fase 3](docs/11-fase-3-resultados.md) e
[Fase 4](docs/12-fase-4-resultados.md).

> Repositório privado. Não publique dados, credenciais ou produtos operacionais sem revisão.

## Fase 4

Reprocessamento historico real, validacao de contratos e ferramentas de release/rollback
implementados. O aceite dos consumidores e a promocao de producao continuam pendentes.
Ver [resultados e procedimento](docs/12-fase-4-resultados.md).
