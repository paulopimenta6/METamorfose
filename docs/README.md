# Documentação do METamorfose

## Guias para executar

Leia na ordem correspondente à sua situação:

1. [Instalação do zero](17-instalacao-do-zero.md): obter o código, preparar
   Python, baixar dados históricos, construir e instalar uma release.
2. [Testes de execução](15-manual-testes-de-execucao.md): atualizar ferramentas,
   verificar arquivos e gerar produtos reais.
3. [Aceitação](16-manual-de-aceitacao.md): conferir BlueSky, preditor e planilhas,
   registrar evidências, assinar, promover e fazer rollback.

[Referência do ambiente](14-ambiente-de-producao-e-aceitacao.md) explica cada
pasta, opção e estado. [Validação da continuidade](18-validacao-da-continuidade.md)
registra os testes desta entrega.

## Entenda o sistema

| Documento | Assunto |
|---|---|
| [01 — Arquitetura](01-arquitetura.md) | Componentes e dependências |
| [02 — Fluxos](02-fluxos.md) | Diagramas de GFS, AUT, MAN e METAR |
| [03 — Dados e saídas](03-dados-e-saidas.md) | Variáveis, níveis, nomes e formatos |
| [04 — Operação](04-operacao.md) | Referência dos fluxos AUT/MAN, METAR e agendamento |
| [05 — Diagnóstico original](05-diagnostico.md) | Defeitos encontrados antes das correções |
| [06 — Plano de melhorias](06-plano-de-melhorias-e-variaveis.md) | Escopo e decisões |
| [08 — Contratos](08-contratos-e-consumidores.md) | Headers, unidades e consumidores |
| [13 — Comunicação](13-comunicacao-consumidores.md) | Mudanças que afetam os usos dos dados |

Os documentos de diagnóstico e arquitetura incluem descrições do sistema
original. Para executar a versão atual, comece pelos guias acima.

## Histórico de implementação e validação

| Fase | Registro |
|---|---|
| 0 — Backup e baseline | [07-fase-0-baseline.md](07-fase-0-baseline.md) |
| 1 — Cálculos meteorológicos | [09-fase-1-resultados.md](09-fase-1-resultados.md) |
| 2 — Produtos, CLI e METAR | [10-fase-2-resultados.md](10-fase-2-resultados.md) |
| 3 — Robustez operacional | [11-fase-3-resultados.md](11-fase-3-resultados.md) |
| 4 — Reprocessamento e release | [12-fase-4-resultados.md](12-fase-4-resultados.md) |

As contagens desses relatórios descrevem as execuções de cada época.
O ambiente de referência segue com aceite pendente, vinculado à release
`26fa746b3b7017f626c2121ba19bf416e3751280180cdd0424ad2100e908d196`.

Voltar ao [README principal](../README.md).
