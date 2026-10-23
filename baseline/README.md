# Baseline da Fase 0

Artefatos gerados antes das correções de cálculo. O baseline preserva o
comportamento atual, inclusive os defeitos D-01, D-02, D-03, D-04 e D-12; não
use os produtos como referência operacional.

## Conteúdo

| Caminho | Papel |
|---|---|
| `freeze.json` | Hash e invariantes do `goGribV2.sh` congelado |
| `run_with_time.py` | Executa um script de produção com `time.localtime()` fixado |
| `run_baseline.py` | Gera o baseline em `baseline/run/` e copia os produtos |
| `build_manifest.py` | Gera `manifest.json` com hashes, versões e resultados |
| `manifest.json` | Manifesto consolidado da Fase 0 |
| `samples/*.json` | Sidecar da amostra GFS (URL, ranges, hashes, ponto de referência) |
| `reports/20261022-00/` | Produtos, `summary.json` e `pytest.txt` |
| `run/` | Árvore temporária, ignorada pelo Git |

## Comandos

```bash
# a amostra binária não é versionada; baixe uma vez
python3 tests/fetch_gfs_sample.py

# gera o baseline (não escreve em /media/MET)
python3 baseline/run_baseline.py

# atualiza o manifesto
python3 baseline/build_manifest.py
```

O baseline usa a amostra `f000` copiada para `f006/f012/f018` apenas para
satisfazer o loop do leitor atual. Todas as mensagens têm `forecastTime=0`, então
o resultado representa somente `f000`.

Documentação completa: `docs/07-fase-0-baseline.md`.
