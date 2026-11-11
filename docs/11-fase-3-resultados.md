# Fase 3 — robustez operacional e correções da auditoria

Implementação sobre `e8f17d8`, no worktree METamorfose, branch execucao.
Este documento é a referência do estado atual; os documentos 01–10 conservam
as descrições e resultados históricos das fases anteriores.

## Alterações

- D-16: controlador usa caminhos relativos ao script, interrompe na primeira
  falha e retorna 0 em sucesso. Wrappers propagam erros; concorrência retorna 75.
- D-18: configuração independente do cwd, override MET_PATH_CONF, normalização
  de caminhos e validação de nomes de região antes da escrita. O MAN mantém
  a escolha explícita de diretório existente; caminhos relativos são resolvidos.
- D-19: removidos bytecodes/editor swaps próprios versionados; requirements.txt
  e requirements-dev.txt registram ambiente e vendor PythonMETAR.
- D-20: CSV/PNG escritos em temporário único no mesmo filesystem e promovidos
  com os.replace após flush/fsync; JSON usa temporário único. Reexecuções
  sobrescrevem o mesmo produto, sem anexar ou criar duplicatas. Permissões de
  arquivo existente são preservadas; novos produtos usam 0644.
- Locks por destino serializam escritores; wrappers têm locks de execução e
  compartilham products.lock com a limpeza (exclusivo na limpeza). Locks ficam
  fora dos produtos, em MET_LOCK_DIR ou /tmp/metamorfose-UID. Não remover locks
  durante execução. A publicação é atômica por arquivo, não por lote inteiro.
- D-21: coordenadas finitas e dentro da faixa; caixas de ponto usam ±5 graus,
  limitadas aos polos/antimeridiano, sem produzir caixas invertidas. O sistema
  não implementa recorte que dê a volta no antimeridiano.
- D-22: rótulo de chuva usa argumento da função, sem depender de global.
- D-23: caminhos construídos com pathlib; leitores MAN e configuração não
  alteram o diretório corrente. MET_PATH_CONF pode selecionar configuração local.
- D-26: seletores fecham GRIBs em finally; figuras criadas pela operação são
  fechadas mesmo em falha de desenho ou escrita.
- Auditoria: GRIBs ausentes/incompletos retornam erro; coordenadas decimais
  funcionam no AUT; índice de previsão separado do índice espacial no ramo
  Greenwich; nomes usam nível realmente selecionado; seleção de nível é
  independente da ordem das mensagens, com desempate para o maior nível.
- U/V/T exigem mesma data/hora, previsão e resolução, grades iguais e níveis
  compatíveis antes de gerar o produto. Falta de temperatura não desloca listas.
- Logs no stderr incluem operação, status, destino e tamanho do produto.

## Validação

Resultado final: **182 passed, 3 deselected** (testes de remotos Git), incluindo
**23 regressões da Fase 3**. Sintaxe Python, bash -n e git diff --check aprovados.
Nenhuma falha, skip ou xfail na suíte local selecionada.

Reprocessamento com a amostra real: **13 CSVs idênticos byte a byte** aos produtos
corrigidos da Fase 1, pelos três scripts CLI de matrizes; **7 PNGs idênticos byte
a byte**, pelas rotinas de desenho de produção, sem figuras abertas ao final.
Nomes, headers e unidades preservados. A validação de mapas encontrou e corrigiu
a interferência do rc global do Matplotlib; cada operação agora usa rc_context.

Artefatos da execução local:
- Matrizes: `/tmp/met-phase3-integration-7q1kixnc/result.json` e logs por script.
- Mapas: `/tmp/met-phase3-maps-i9q9ndat/result.json` e sete PNGs.
- Resumo persistido: `reprocessamento/reports/fase-3/validation.json`.

A tentativa inicial de executar os seis scripts completos em /tmp atingiu o
limite de 360 s no mapa winds: a fixture f000 sob quatro nomes repetia o desenho
do mesmo mapa quatro vezes. A validação final usa uma mensagem por produto de
mapa e mantém a execução CLI das matrizes. Não se declara validado um lote
operacional completo nem previsões futuras.
A suíte `tests/test_phase3_acceptance.py` cobre regressões da auditoria e
T-13 a T-15: escrita interrompida, concorrência real entre processos,
reexecução, permissões, fechamento de figuras/GRIBs, configuração, regiões,
Greenwich, coordenadas decimais, alinhamento de componentes e controlador.

## Operação e compatibilidade

Instalar dependências a partir da raiz: `python -m pip install -r requirements.txt`.
Para desenvolvimento, usar requirements-dev.txt. O vendor PythonMETAR é local.
Executar testes sem rede: `python -m pytest -q -m 'not network'`.
MET_LOCK_DIR deve ser compartilhado por todas as instâncias locais que escrevem
os mesmos destinos. Em hosts diferentes, usar armazenamento/coordenação comum;
esta versão não fornece lock distribuído. Não executar o downloader congelado
simultaneamente à leitura de arquivos que ele ainda esteja baixando.

Nomes, headers, schemas e unidades são preservados. Níveis arredondados passam
a usar o nível efetivo no nome. O downloader goGribV2.sh e baseline estão intactos.
Não houve instalação global, push, merge, promoção ou alteração em /media/MET.

## Limites e próxima fase

O escopo desta fase cobre logging/lock/escrita atômica/idempotência, mas não
inclui manifesto ou `run_id` por execução: os logs de produto vão para o stderr
e o único manifesto versionado é o do baseline da Fase 0.

A Fase 4 foi implementada e validada localmente depois desta fase; previsões
reais f006/f012/f018, mais regiões e níveis, release/rollback e comparação com
METAR estão em [12-fase-4-resultados.md](12-fase-4-resultados.md). O aceite dos
consumidores BlueSky/preditor e a promoção em produção continuam pendentes. Os
12 JSONs históricos inválidos não foram reescritos. Coleta de METAR ao vivo e
agendador de produção não foram certificados.
