# Ambiente de produção e aceite da Fase 4

## Objetivo e limite

Este documento descreve como montar o ambiente de aceitação, executar os testes
dos três consumidores externos, registrar as evidências, assinar o aceite,
promover a release e reverter para a versão anterior.

O ambiente montado **não é uma promoção**. Ele contém o código e os produtos da
release candidata, mas `acceptance.json` começa com `approved: false` e sem
evidências. A release só pode ser promovida depois que BlueSky, preditor e
planilhas forem executados de verdade e as três evidências forem registradas.

Os scripts `bin/testar_*.sh` verificam contratos e geram uma amostra nova a
partir de um GRIB real, mas **não** executam os aplicativos externos e **não**
registram evidência automaticamente.

## Release de referência

| Item | Valor |
|---|---|
| Release | `reprocessamento/releases/phase4-candidate` |
| SHA-256 de `release.json` | `26fa746b3b7017f626c2121ba19bf416e3751280180cdd0424ad2100e908d196` |
| Arquivos inventariados | 1.141 (39 de código, 1.101 produtos, 1 de validação) |
| Produtos | 1.098 CSVs e 3 PNGs |
| GRIBs históricos | 12 amostras (15–17/12/2022, ciclos 00/06/12/18) |
| Consumidores | BlueSky, preditor, planilhas |

O aceite é vinculado ao SHA-256 de `release.json`. Se a release for reconstruída,
o hash muda e o aceite anterior deixa de valer.

## Layout do ambiente

O instalador usa por padrão `~/MET/servidor_MET`. O caminho usado neste
ambiente foi `/home/paulo/MET/servidor_MET`.

| Caminho | Conteúdo |
|---|---|
| `app/` | cópia do código da release, usada antes da promoção |
| `environment/path.conf` | configuração de diretórios do ambiente |
| `gribs/AAAAMMDD/HH/` | GRIBs históricos com os nomes esperados pelo fluxo MAN |
| `matrizGrib/` | matrizes escalares e as árvores `bluesky/` e `predi/` |
| `mapasGrib/` | mapas PNG da campanha |
| `evidence/release/candidate/` | cópia imutável da release e do inventário |
| `evidence/samples/` | manifesto e metadados das amostras GFS |
| `acceptance/acceptance.json` | estado do aceite (inicialmente pendente) |
| `acceptance/evidence/<consumidor>/` | evidências registradas |
| `logs/` | logs dos scripts `testar_*` |
| `run/locks/` | locks de promoção e rollback |
| `backups/` | tar.gz criado antes de cada promoção |
| `aceitacao-manual/` | saídas MAN geradas durante os testes |
| `bin/` | scripts operacionais |
| `releases/`, `current`, `previous` | criados somente depois da promoção |

`path.conf` aponta para os diretórios de produtos no topo do ambiente. O arquivo
`code/environment/path.conf` da release é substituído pela versão local; por
isso ele é excluído da conferência de hash do ambiente instalado.

## Instalação

A partir do repositório `METamorfose`:

```bash
python3 reprocessamento/setup_production_env.py
```

Opções:

```bash
python3 reprocessamento/setup_production_env.py \
  --root ~/MET/servidor_MET \
  --candidate reprocessamento/releases/phase4-candidate \
  --samples reprocessamento/phase4-data

# reinstala código, GRIBs e produtos, preservando aceite e evidências
python3 reprocessamento/setup_production_env.py --force
```

Para instalar em `/media/MET/servidor_MET`, crie o diretório com a conta
operacional. Se for necessário usar `sudo`, garanta que o dono do ambiente seja
a conta que executará os testes:

```bash
sudo mkdir -p /media/MET
sudo chown "$USER":"$(id -gn)" /media/MET
python3 reprocessamento/setup_production_env.py --root /media/MET/servidor_MET
```

O instalador verifica a release antes de copiar, recusa um destino que já
contenha um ambiente sem `--force` e não grava aceite aprovado. Com `--force`,
`acceptance.json` e as evidências existentes são preservados; código, GRIBs e
produtos são substituídos pela release indicada.

O verificador instalado é copiado do repositório para
`app/reprocessamento/acceptance_check.py`. Depois de alterar o verificador,
reinstale com `--force` para atualizar a cópia usada pelos scripts.

## Ativação

```bash
source ~/MET/servidor_MET/bin/ativar.sh
```

O script deve ser carregado com `source` (ou `.`), não executado com `bash`,
porque as variáveis precisam permanecer no shell atual. Ele define:

| Variável | Valor |
|---|---|
| `MET_PROD_ROOT` | raiz do ambiente |
| `MET_ACTIVE_CODE` | `current/code` depois da promoção; `app` antes dela |
| `MET_PATH_CONF` | `environment/path.conf` |
| `MET_LOCK_DIR` | `run/locks` |

O `PATH` recebe `$MET_ACTIVE_CODE/bash` e `$MET_PROD_ROOT/bin`.

## Verificação inicial

```bash
~/MET/servidor_MET/bin/verificar.sh
```

O comando confere, em sequência:

1. diretórios e scripts obrigatórios;
2. `path.conf` e os cinco diretórios de dados;
3. vínculo entre `acceptance.json` e o SHA-256 da release instalada;
4. hashes de 1.140 arquivos (o `path.conf` local é excluído);
5. contagens de 12 GRIBs, 1.098 CSVs e 3 PNGs;
6. dependências Python (`numpy`, `pygrib`, `matplotlib`, Basemap);
7. contrato das matrizes do BlueSky, do preditor e das planilhas;
8. estado do aceite.

Resultado esperado antes do aceite:

```text
state: pending
falhas: 0
status: ok
```

`state: pending` é o estado correto nesta etapa. O código de saída só é `2`
quando `acceptance --require-approved` é usado, como faz `promover.sh`.

Contagens dos contratos neste ambiente:

| Consumidor | Arquivos | Linhas | Variante |
|---|---:|---:|---|
| BlueSky | 324 | 686.340 | headers AUT da release |
| preditor | 324 | 686.340 | headers AUT da release |
| planilhas | 450 | 953.250 | escalares |

As saídas MAN têm headers com unidade e são aceitas pelo verificador:

- BlueSky: `lat,lon,hMET<feet>,angMET<grau>,vento_resultante<knot>`;
- preditor: `lat,lon,vento U,vento V,temperatura K`;
- escalares: `lat,lon,<variavel>`.

## Teste de cada consumidor

O roteiro é o mesmo para os três. O exemplo usa BlueSky; troque o nome do
consumidor e confira a amostra indicada no log.

### 1. Gerar o material de teste

```bash
~/MET/servidor_MET/bin/testar_bluesky.sh
```

O script:

- ativa o ambiente;
- valida os produtos da release com `acceptance_check.py`;
- gera uma matriz MAN nova com GRIB real em `aceitacao-manual/bluesky-<UTC>/`;
- grava o log em `logs/bluesky-<UTC>.log`;
- termina com o caminho da amostra da release e o comando de registro.

Amostras geradas:

| Script | Geração MAN | Amostra da release |
|---|---|---|
| `testar_bluesky.sh` | vento, f000, 200 hPa | `matrizGrib/bluesky/20221215/00/` |
| `testar_preditor.sh` | vento, f000, 500 hPa | `matrizGrib/predi/20221215/00/` |
| `testar_planilhas.sh` | temperatura, f000, 850 hPa | `matrizGrib/20221215/00/` |

### 2. Executar o aplicativo real

Abra no consumidor real:

- pelo menos uma matriz da amostra da release indicada no log;
- a matriz MAN recém-gerada em `aceitacao-manual/<consumidor>-<UTC>/`.

Confirme o que o consumidor realmente usa:

| Consumidor | Confira |
|---|---|
| BlueSky | orientação lat/lon, `hMET` em pés, `angMET` em graus entre 0 e 360, `vento_resultante` em nós |
| preditor | orientação, `vento U`/`vento V` em m/s, `temp`/`temperatura K` em Kelvin |
| planilhas | orientação, temperatura em °C, nuvem/umidade em %, chuva em mm, pressão em hPa |

Neste aceite, os produtos escalares usam temperatura em Celsius; o preditor usa
Kelvin. `chuvaNaoConvec` continua sendo a precipitação total e `temps` continua
sendo temperatura de pele. Não renomeie nem inverta as linhas no consumidor.

### 3. Salvar uma evidência

A evidência pode ser o log do próprio aplicativo, um recorte de tela, um CSV
exportado ou uma nota de execução. Ela precisa ser um arquivo não vazio que
permita reconstruir o que foi testado. Evite credenciais e dados sensíveis.

### 4. Registrar a evidência

```bash
~/MET/servidor_MET/bin/registrar_evidencia.sh BlueSky ARQUIVO "nota do teste"
```

Nomes aceitos: `BlueSky`, `preditor`, `planilhas`. O script copia o arquivo para
`acceptance/evidence/<consumidor>/` com carimbo UTC, calcula o SHA-256 e grava
em `acceptance.json`:

```json
{
  "path": "acceptance/evidence/BlueSky/20261111T000000Z-log.txt",
  "sha256": "...",
  "notes": "nota do teste",
  "registered_at_utc": "..."
}
```

Há um único registro por consumidor. Registrar novamente antes da assinatura
substitui a evidência anterior. Depois de `approved: true`, o comando recusa a
troca; para refazer um aceite já assinado, restaure o `acceptance.json` do
backup ou edite o arquivo de forma consciente e assine novamente.

Repita o ciclo para os três consumidores. O log do `testar_*` sozinho não é
evidência do consumidor: ele comprova a verificação local e a geração MAN, não a
execução do aplicativo externo.

## Estado e assinatura

```bash
~/MET/servidor_MET/bin/status.sh
```

Enquanto faltar evidência, o estado continua `pending`. Para assinar:

```bash
~/MET/servidor_MET/bin/assinar.sh "Nome do responsável"
```

A assinatura exige:

- `release_sha256` igual ao SHA-256 da release instalada;
- exatamente os consumidores `BlueSky`, `preditor` e `planilhas`;
- três evidências existentes, não vazias e com hash válido;
- `approved_by` não vazio.

Campos gravados em `acceptance.json`:

```json
{
  "approved": true,
  "approved_by": "Nome do responsável",
  "accepted_at_utc": "2026-11-11T00:00:00+00:00"
}
```

O aceite é uma declaração sobre esta release e este ambiente. Ele não é
transferível para outra release nem para outro conjunto de produtos.

## Promoção

```bash
~/MET/servidor_MET/bin/promover.sh
```

O script:

1. executa `acceptance --require-approved` e aborta se o aceite estiver pendente;
2. cria `backups/pre-promocao-<UTC>.tar.gz` com `environment`, `acceptance`,
   `app`, `matrizGrib` e `mapasGrib`;
3. copia a release candidata para `releases/<20 primeiros hex do SHA-256>`;
4. verifica a cópia e troca `current` atomicamente;
5. registra o evento em `history.jsonl`.

Depois da promoção, ative novamente:

```bash
source ~/MET/servidor_MET/bin/ativar.sh
```

Agora `MET_ACTIVE_CODE` aponta para `current/code`. Os produtos permanecem nas
árvores de topo (`matrizGrib/` e `mapasGrib/`) e o `path.conf` não muda. Neste
ambiente, os produtos instalados já são exatamente os da release; o inventário
é conferido por `verificar.sh`. Ao promover uma release diferente em uma
instalação real, instale/atualize os produtos e confirme os hashes antes de
apontar os consumidores para o novo diretório.

`verificar.sh` depois da promoção também confere se `current` aponta para uma
release dentro de `releases/` e se o `release.json` dessa release é o aceito.

## Rollback

O rollback exige que exista uma release anterior, ou seja, pelo menos duas
promoções. Em um ambiente com apenas uma promoção, `previous` não existe.

```bash
~/MET/servidor_MET/bin/rollback.sh
source ~/MET/servidor_MET/bin/ativar.sh
```

O comando verifica a release anterior, troca `current`/`previous` e registra
`action: rollback` em `history.jsonl`. Ele restaura o código, não os produtos:
os CSVs e PNGs de topo não são versionados por release. Para recuperar também
os produtos, use o backup criado antes da promoção.

## Ensaio local já executado

O fluxo foi validado em diretórios temporários, sem tocar em produção:

- `register`/`sign` com três evidências sintéticas;
- detecção de evidência adulterada por hash;
- promoção com troca atômica de `current`;
- `ativar.sh` apontando para `current/code`;
- rollback com duas releases e registro em `history.jsonl`.

Esses ensaios comprovam o mecanismo, não o aceite. O ambiente real permanece
com `approved: false` até a execução dos três consumidores.

## Problemas comuns

| Sintoma | Causa e ação |
|---|---|
| `ambiente já existe` | O destino já tem `app`, `gribs` ou `matrizGrib`. Use `--force` para reinstalar. |
| `sem permissão` em `/media` | Crie o diretório com a conta operacional ou ajuste o dono após usar `sudo`. |
| `aceite pendente` com código 2 | Esperado em `acceptance --require-approved` antes da assinatura. |
| `evidencia ausente para ...` | Falta registrar o arquivo daquele consumidor. |
| `hash da evidencia diverge` | O arquivo foi alterado depois do registro. Registre uma cópia nova. |
| `sem release anterior` | Só há uma promoção; o rollback precisa de duas. |
| `current invalido` | O symlink foi alterado ou aponta para fora de `releases/`. |
| `modulo Python ausente` | Instale as dependências no mesmo Python usado pelos scripts. |

Não edite arquivos em `evidence/release/candidate/` nem em `matrizGrib/` para
“fazer a verificação passar”. O verificador deve falhar se o conteúdo não for o
da release aceita.

## Checklist de aceite

- [ ] Release com SHA-256 `26fa746...` instalada.
- [ ] `bin/verificar.sh` com `falhas: 0`.
- [ ] BlueSky executado com a amostra da release e a saída MAN.
- [ ] Preditor executado com a amostra da release e a saída MAN.
- [ ] Planilhas executadas com a amostra da release e a saída MAN.
- [ ] Três evidências registradas com hashes válidos.
- [ ] `bin/assinar.sh "Nome"` concluído.
- [ ] `bin/status.sh` mostrando `state: approved`.
- [ ] Backup e janela de manutenção confirmados antes de `promover.sh`.
- [ ] Consumidores apontados para o diretório de produtos correto.
