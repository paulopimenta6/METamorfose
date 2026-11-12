# Aceitar os resultados e promover a release

O aceite é a confirmação do responsável de que os produtos funcionam nos três
usos reais: **BlueSky, preditor e planilhas**. Ele pertence ao SHA-256 exato da
release testada.

Antes de começar, conclua o [manual de execução](15-manual-testes-de-execucao.md).
Use o mesmo terminal, com Python e ambiente MET ativados.

## 1. Conferir qual versão será aceita

Se abriu um terminal novo, configure os caminhos e ative os ambientes:

```bash
export REPO="$HOME/Documentos/meus_codigos/METamorfose"
export MET_ROOT="$HOME/MET/servidor_MET"
source "$REPO/.venv/bin/activate"
source "$MET_ROOT/bin/ativar.sh"
```

Se usa Conda, ative seu ambiente Python em vez da `.venv`. Ajuste os caminhos
quando sua instalação estiver em outra pasta.

```bash
sha256sum "$MET_ROOT/evidence/release/candidate/release.json"
"$MET_ROOT/bin/verificar.sh"
"$MET_ROOT/bin/status.sh"
```

**Esperado:** o hash mostrado por `sha256sum` deve ser igual a `release_sha256`
no verificador. Antes da assinatura, `state: pending`, `falhas: 0`, `status: ok`.

A candidata histórica tem hash
`26fa746b3b7017f626c2121ba19bf416e3751280180cdd0424ad2100e908d196`.
Se você construiu uma release pelo guia do zero, **o hash será outro**. Aceite
a versão que efetivamente instalou e testou, usando seu próprio hash.

## 2. Gerar o material de conferência

Se já executou os três testes e guardou os resultados, use esses arquivos.
Caso contrário:

```bash
"$MET_ROOT/bin/testar_todos.sh"
```

Espere `Os tres testes tecnicos passaram`. Guarde os caminhos `Log local`,
`Saida MAN` e `CSV gerado para ...` de cada teste.

Os testes técnicos executam a geração e verificam contratos. A evidência de
aceite deve incluir **sua conferência do resultado no uso real**, descrita abaixo.

## 3. Conferir BlueSky — seu código

BlueSky, neste projeto, é código desenvolvido pelo autor. As rotinas de
geração identificadas são:

- **AUT:** `geraMatriz_Vento_Resu`, em `classes_MET/gera_matriz_vento_MET.py`.
- **MAN:** `met_gera_matriz_vento_man.gera_matriz_vento_bluesky`, em
  `classes_MET/gera_matriz_vento_MAN_MET.py`.

`testar_bluesky.sh` já executa a rotina MAN por meio de `reqs_MAN_MET.sh`.
Para validar seu uso, inspecione o resultado da função/classe e execute a
integração que você utiliza com esses dados. Se seu fluxo termina na geração
da matriz, documente a conferência dessa saída. O repositório não define um
comando de inicialização de outro aplicativo chamado BlueSky.

Compare:

1. Um CSV da release, gerado pelo fluxo AUT. Liste as opções de 200 hPa:

   ```bash
   find "$MET_ROOT/matrizGrib/bluesky/20221215/00" -name '*_N200_*.csv'
   ```

2. O CSV MAN mostrado no log de BlueSky:
   `matriz_vento_bluesky_..._N200_...csv`, dentro de `Saida MAN`.

Confira latitude/longitude, altura em **pés**, direção em **[0, 360)** graus
e vento em **nós**. O teste usa **200 hPa**, uma altitude de pressão; esse nível
não significa 200 metros. Nos produtos `winds` de superfície, por exemplo,
20 m correspondem a 65,6168 pés.

Os mapas de vento gerados junto dessas matrizes mostram **m/s**, enquanto o
CSV BlueSky apresenta a resultante em **nós**.

Os headers existentes são diferentes entre AUT e MAN:

```text
AUT: lat,lon,hMET,angMET,vento_resultante
MAN: lat,lon,hMET<feet>,angMET<grau>,vento_resultante<knot>
```

As regiões AUT e MAN podem ter recortes diferentes. Compare pontos com as
mesmas coordenadas, nível, ciclo e previsão; não compare apenas o número da linha.

## 4. Conferir o preditor

Use o comando ou interface habitual do seu preditor para consumir:

- um arquivo da release listado por:

  ```bash
  find "$MET_ROOT/matrizGrib/predi/20221215/00" -name '*_N500_*.csv'
  ```

- o CSV MAN `matriz_vento_predi_..._N500_...csv` mostrado no log do teste.

Confira importação, grade, componentes **U e V em m/s**, temperatura em
**Kelvin** e o resultado do cenário que você normalmente executa.

```text
AUT: lat,lon,vento U,vento V,temp
MAN: lat,lon,vento U,vento V,temperatura K
```

O executável do seu preditor não está definido neste repositório; use sua
integração existente e registre como a executou.

## 5. Conferir as planilhas

Abra o CSV `GFS_..._N850_temp_...csv` indicado no teste de planilhas e um CSV
escalar da release:

```bash
find "$MET_ROOT/matrizGrib/20221215/00" -maxdepth 1 -name '*_temp_*.csv'
```

Na importação do LibreOffice/Excel, selecione **separador vírgula**, **decimal
ponto** e codificação **UTF-8**. Confirme que os valores foram importados como
números. O cabeçalho da temperatura é `lat,lon,temp`, e a unidade é **°C**.

O teste MAN cobre temperatura em 850 hPa. Para conferir outros escalares que
você usa, escolha os respectivos CSVs da release:

| Variável | Interpretação/unidade |
|---|---|
| `temp` | Temperatura do ar, °C |
| `temps` | Temperatura de pele, °C |
| `nuvem`, `umidadeRel` | Porcentagem |
| `ps`, `prnm` | Pressão, hPa |
| `chuvaNaoConvec` | Precipitação **total**, mm |
| `chuvaConvec` | Precipitação convectiva, mm |

As amostras de chuva da campanha estão nas previsões f006/f012/f018.
Confira também orientação geográfica e cálculos usados na sua planilha.

## 6. Salvar e registrar uma evidência de cada uso

Crie uma pasta para seus registros:

```bash
export EVID="$HOME/evidencias-MET"
mkdir -p "$EVID"
```

Depois de executar e conferir cada uso, salve um log, captura ou nota real
nessa pasta. A evidência deve informar:

- responsável e data;
- SHA-256 da release;
- nomes completos dos CSVs avaliados;
- função/classe, comando ou procedimento usado;
- verificações realizadas e resultado observado.

Para usar os comandos abaixo literalmente, salve três notas com os nomes
`bluesky.txt`, `preditor.txt` e `planilhas.txt`. Preencha cada uma com o que
**realmente executou e observou**. Se usar imagens ou logs com outros nomes,
substitua o segundo argumento pelo caminho do arquivo correspondente.

```bash
"$MET_ROOT/bin/registrar_evidencia.sh" BlueSky "$EVID/bluesky.txt" "Conferencia do fluxo BlueSky"
"$MET_ROOT/bin/registrar_evidencia.sh" preditor "$EVID/preditor.txt" "Conferencia do preditor"
"$MET_ROOT/bin/registrar_evidencia.sh" planilhas "$EVID/planilhas.txt" "Conferencia das planilhas"
```

**Esperado em cada comando:** `evidencia registrada: ... (consumidor)`.
O registro copia o arquivo para `acceptance/evidence/` e guarda seu hash.
Antes da assinatura, registrar novamente substitui a referência daquele
consumidor, mantendo as cópias anteriores no disco.

Confira as três evidências:

```bash
python3 "$MET_ROOT/tools/acceptance_check.py" acceptance \
  --root "$MET_ROOT" --require-evidence --json
```

**Esperado:** três caminhos em `evidence`, `"failures": []`, `"status": "ok"`.
O estado ainda será `pending`.

## 7. Assinar o aceite

Quando os três usos estiverem conferidos, substitua o nome abaixo pelo seu:

```bash
"$MET_ROOT/bin/assinar.sh" "Seu Nome Completo"
"$MET_ROOT/bin/status.sh"
```

**Esperado:** `state: approved`, `falhas: 0`, `status: ok`.
O aceite agora identifica responsável, data UTC e release. Os scripts conferem
integridade e presença das evidências; a veracidade do teste é a declaração
do responsável.

## 8. Promover e conferir o código ativo

```bash
"$MET_ROOT/bin/promover.sh"
source "$MET_ROOT/bin/ativar.sh"
"$MET_ROOT/bin/verificar.sh"
```

**Esperado:** caminho do backup, `"action": "promote"` (ou `noop` se já ativa),
`deployment: candidate-active`, `state: approved` e `falhas: 0`.

`Codigo ativo` mostra o caminho físico `releases/<20 caracteres>/code`.
O verificador confere todos os arquivos dessa release, além dos produtos e
código instalados da candidata. O `path.conf` local continua sendo usado via
`MET_PATH_CONF`.

A promoção seleciona código pelo ponteiro `current`. Para executar esse código,
seus comandos devem usar `$MET_ACTIVE_CODE`, após `source ativar.sh`. Um cron
com caminho fixo antigo precisa ser ajustado conforme [04-operacao.md](04-operacao.md).

## 9. Voltar para a versão anterior, quando necessário

É preciso existir `previous`: isso ocorre após duas promoções de releases
diferentes. Repetir a mesma promoção não cria uma versão anterior.

```bash
"$MET_ROOT/bin/rollback.sh"
source "$MET_ROOT/bin/ativar.sh"
"$MET_ROOT/bin/verificar.sh"
```

**Esperado:** `rollback concluido`. Se voltou a outra release íntegra,
`deployment: other-release-active` e `active_release_sha256` mostram a versão
reativada. O aceite continua vinculado à candidata em `release_sha256`.

O rollback troca **o código ativo**. Os CSVs/PNGs de topo e o arquivo de aceite
continuam como estavam. A restauração de produtos é uma operação separada,
a partir do backup; o verificador continuará comparando-os à candidata instalada.

## Se houver erro

| Mensagem | Ação |
|---|---|
| `evidencia ausente` | Execute e confira o uso indicado, depois registre seu arquivo. |
| `hash da evidencia diverge` | A cópia registrada mudou. Refaça o registro antes de assinar. |
| `release_sha256 ... nao corresponde` | O aceite e a instalação pertencem a releases diferentes; use o ambiente correspondente. |
| `aceite ja aprovado` | A versão já foi assinada; uma nova candidata deve usar outro ambiente e outro aceite. |
| `aceite pendente`, código 2 | Falta concluir os passos 3–7 antes da promoção. |
| `sem release anterior` | Ainda não há duas releases diferentes para realizar rollback. |

Referência de pastas e manutenção: [ambiente de aceitação](14-ambiente-de-producao-e-aceitacao.md).
