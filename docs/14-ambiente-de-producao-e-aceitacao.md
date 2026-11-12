# Referência do ambiente de aceitação

Para executar passo a passo, use [instalação](17-instalacao-do-zero.md),
[testes](15-manual-testes-de-execucao.md) e [aceitação](16-manual-de-aceitacao.md).
Esta página explica a configuração e as operações de manutenção.

## Ambiente de referência

| Item | Valor |
|---|---|
| Raiz padrão | `~/MET/servidor_MET` |
| Raiz neste host | `/home/paulo/MET/servidor_MET` |
| Candidata histórica | `reprocessamento/releases/phase4-candidate` |
| SHA-256 de `release.json` | `26fa746b3b7017f626c2121ba19bf416e3751280180cdd0424ad2100e908d196` |
| Inventário histórico | 1.141 arquivos; 1.140 conferidos nas cópias instaladas |
| Dados | 12 GRIBs: 15–17/12/2022, ciclo 00, f000/f006/f012/f018 |
| Produtos | 1.098 CSVs + 3 PNGs |
| Aceite real | Pendente; nenhuma evidência registrada |

As contagens são da campanha padrão. Reconstruir uma release gera outro hash.
Os dados e pacotes são ignorados pelo Git; o guia de instalação explica como
obtê-los. `/media/MET/servidor_MET` não foi criado neste host.

## Layout

| Caminho relativo a `MET_ROOT` | Conteúdo |
|---|---|
| `app/` | Código da candidata usado nos testes |
| `tools/` | Verificador e ferramenta de release, atualizáveis separadamente |
| `bin/` | Ativação, verificações, testes, registro, assinatura, promoção e rollback |
| `docs/`, `LEIA-ME.md` | Manuais copiados do repositório |
| `environment/path.conf` | Cinco caminhos locais de dados e produtos |
| `gribs/AAAAMMDD/CC/` | GRIBs com nomes esperados pelo leitor MAN |
| `matrizGrib/`, `mapasGrib/` | Produtos instalados da candidata |
| `evidence/release/candidate/` | Pacote imutável, manifesto e validação |
| `evidence/samples/` | Manifesto e metadados dos GRIBs |
| `acceptance/acceptance.json` | Estado do aceite da candidata |
| `acceptance/evidence/<consumidor>/` | Cópias dos registros com hashes |
| `aceitacao-manual/`, `logs/` | Saídas e logs dos testes técnicos |
| `run/locks/` | Locks dos geradores e produtos |
| `backups/` | Backup antes da promoção |
| `releases/`, `current`, `previous` | Pacotes e ponteiros criados na promoção |
| `history.jsonl`, `.deployment.lock` | Histórico e lock de promoção/rollback |

Apenas `app/environment/path.conf` é reescrito para os caminhos locais; seu
hash é excluído da comparação da cópia instalada. O `path.conf` dentro de
`evidence/release/candidate/` e de `releases/` permanece original e é conferido.

## Instalar uma release existente

Na raiz do repositório, com Python ativado:

```bash
export MET_ROOT="$HOME/MET/servidor_MET"
python3 reprocessamento/setup_production_env.py \
  --root "$MET_ROOT" \
  --candidate reprocessamento/releases/phase4-candidate \
  --samples reprocessamento/phase4-data
```

O preflight verifica pacote, vínculo do aceite existente, layout das fontes,
manifesto de amostras, datas, ciclos, previsões, duplicatas, hashes e assinatura
GRIB antes de substituir arquivos. Destino e fontes não podem se sobrepor.

Para uma release construída por você, use seu caminho em `--candidate`.

### Atualizar somente ferramentas e manuais

```bash
python3 reprocessamento/setup_production_env.py --root "$MET_ROOT" --update-tools
```

Usa o pacote já instalado em `evidence/release/candidate/`. Não exige as fontes
originais em `reprocessamento/releases/` ou `phase4-data/`. Atualiza `tools/`,
`bin/`, `docs/`, `LEIA-ME.md` e os READMEs do projeto e dos testes;
preserva `app/`, dados, configuração e aceite.

### Reinstalar a mesma release

`--force` substitui `app/`, GRIBs e produtos com as fontes indicadas. Use para
repor uma instalação da **mesma** candidata, após identificar os arquivos que
precisam ser recuperados:

```bash
python3 reprocessamento/setup_production_env.py --root "$MET_ROOT" \
  --candidate reprocessamento/releases/phase4-candidate \
  --samples reprocessamento/phase4-data --force
```

Aceite e evidências são preservados. Outra release é recusada quando o aceite
existente tem hash diferente: instale-a em outro `--root`.
`--force` e `--update-tools` são mutuamente exclusivos.

## Ativação

```bash
source "$MET_ROOT/bin/ativar.sh"
```

| Variável | Finalidade |
|---|---|
| `MET_PROD_ROOT` | Raiz instalada |
| `MET_ACTIVE_CODE` | `app/` ou caminho físico de `current/code` |
| `MET_PATH_CONF` | Configuração local, inclusive ao usar release promovida |
| `MET_LOCK_DIR` | Locks compartilhados pelos processos |
| `PYTHONDONTWRITEBYTECODE=1` | Evita criar `.pyc` nas releases imutáveis |
| `MPLBACKEND=Agg` | Gera PNG sem janela gráfica |

O Python virtual é ativado separadamente. Recarregue `ativar.sh` depois de
promoção/rollback. Um `current` quebrado é tratado como erro.

## Estados exibidos

`verificar.sh` verifica ambiente, contratos e aceite. `status.sh` mostra o
aceite e confere a release ativa quando houver.

| Campo/valor | Significado |
|---|---|
| `release_sha256` | Hash da candidata instalada, ao qual o aceite deve corresponder |
| `active_release_sha256` | Hash da release apontada por `current`, quando existir |
| `deployment: candidate-only` | Sem `current`; ativação usa `app/` |
| `deployment: candidate-active` | `current` aponta à candidata íntegra |
| `deployment: other-release-active` | Outra release íntegra está ativa, por exemplo após rollback |
| `deployment: invalid` | Verificação do ambiente detectou release ativa inválida |
| `rehearsal: True` | Destino de ensaio, não de promoção real |
| `state: pending` | Aceite ainda não assinado |
| `state: approved` | Aceite assinado e evidências conferidas |

O inventário completo da candidata é verificado, além das cópias de código e
produtos instaladas. Na release ativa, arquivos alterados, extras, symlinks
internos ou relatório inválido provocam falha. Um hash ativo diferente após
rollback é informado, sem transferir o aceite da candidata para ele.

Códigos do verificador: `0` para verificação bem-sucedida; `1` para falhas;
`2` para aceite pendente quando se exige `--require-approved`.

## Promoção e rollback

`promover.sh` verifica ambiente e aceite, cria backup de `environment`,
`acceptance`, `app`, `matrizGrib` e `mapasGrib`, copia o pacote para
`releases/<20 primeiros caracteres do hash>` e troca `current` atomicamente.

`rollback.sh` verifica e reativa `previous`. Troca os ponteiros e registra
o evento em `history.jsonl`. Produtos de topo e aceite não são restaurados
automaticamente. A sequência de uso está no [manual de aceitação](16-manual-de-aceitacao.md).

## Caminho operacional `/media/MET`

O downloader preservado usa `/media/MET/servidor_MET/gribs`. Para operar nesse
caminho, a conta operacional precisa ter permissão de escrita. A criação desse
diretório pode exigir administração do sistema. A instalação em `$HOME` atende
ao reprocessamento e aos testes MAN descritos nos guias.

`verificar.sh` é a verificação da campanha instalada. A geração diária pode
acrescentar ou substituir produtos de topo; nesse caso, suas contagens e hashes
divergem da campanha. Mantenha a instalação de aceitação identificável e use
a verificação dos produtos correspondentes à operação diária.

Veja [04-operacao.md](04-operacao.md) para aquisição diária, AUT e METAR,
e [18-validacao-da-continuidade.md](18-validacao-da-continuidade.md) para os
resultados mais recentes de validação.
