# Fase 4 — reprocessamento, validação e rollout

## Estado e critério de saída

A infraestrutura e a validação local desta fase foram implementadas. A promoção
em produção e o aceite pelos consumidores externos permanecem pendentes: o
caminho /media/MET/servidor_MET não existe neste ambiente e os códigos externos
BlueSky/preditor não foram disponibilizados. O relatório não substitui esse
aceite e o critério integral da Fase 4 ainda não está satisfeito.

## Janela e método

Campanha de três datas com METAR de referência: 15, 16 e 17/12/2022, ciclo 00 UTC,
previsões reais f000, f006, f012 e f018. São 12 arquivos distintos, com hash,
URL do arquivo público NOAA e ranges originais registrados no manifesto. Não
há cópia de f000 sob nomes de previsão futura. A aquisição operacional continua
congelada: fetch_phase4_samples.py é exclusivo da validação de arquivos históricos.

Regiões SP/RJ/AM; temperatura e vento em 200/500/850/1000 hPa; nuvens em
200/500/700 hPa; umidade em 850 hPa; pressão superficial/MSL; temperatura de pele;
chuva total e convectiva em previsões; vento em 20/30/40/50/80 m. Não é uma
certificação de todas as situações meteorológicas nem uma série de 30 dias.

As rotinas de produção geram os produtos em árvores separadas por amostra.
Cada CSV é comparado em todas as linhas com extração independente do GRIB
original: coordenadas, orientação, unidades, U/V/T, direção, velocidade e altura.
Também são verificados headers, CRLF, valores finitos, nomes, tamanhos e hashes.
Os mapas representativos usam as mesmas rotinas de desenho e preservam PNG/nome.

O cache de recorte evita decodificações globais repetidas durante o ensaio;
a validação numérica relê o GRIB original, sem usar o cache como oráculo.
As matrizes deixaram de construir objetos Basemap globais que nunca eram usados.
Essa otimização não muda dados, nomes ou schemas e está coberta pela suíte.

A comparação METAR usa vento GFS a 10 m e temperatura GFS **a 2 m**, não temperatura de pele nem
850 hPa. É diagnóstico separado dos produtos existentes. Usa ponto de grade
mais próximo e observação mais próxima dentro de ±3 horas, incluindo a virada
do dia; empates escolhem a observação anterior. Coordenadas vêm do inventário
vendorizado nsd_cccc.txt, que pode estar desatualizado. MAE/bias de temperatura e MAE de velocidade do vento são diagnóstico,
não limiar de certificação meteorológica nem validação do preditor externo.

## Reprodução

```bash
python reprocessamento/fetch_phase4_samples.py --output reprocessamento/phase4-data
python reprocessamento/phase4.py --manifest reprocessamento/phase4-data/manifest.json \
  --output reprocessamento/phase4-runs/nova-campanha --maps
python -m pytest -q -m 'not network'
python reprocessamento/release_phase4.py build \
  --validation reprocessamento/phase4-runs/nova-campanha \
  --output reprocessamento/releases/candidata
python reprocessamento/release_phase4.py verify reprocessamento/releases/candidata
```

O comando de reprocessamento exige diretório novo, não sobrescreve baseline,
produtos antigos ou releases anteriores. Download falho ou cobertura incompleta
não produz validação aprovável. Amostras são verificadas por SHA-256 e metadados
reais; para chuva acumulada, endStep identifica a previsão e startStep/forecastTime
mantêm o rótulo histórico +6. Os dois campos não são confundidos.

## Promoção e rollback

Release candidata contém código/configuração, produtos com a árvore operacional,
relatório e inventário completo de hashes. Um produto alterado, arquivo extra ou
symlink faz verify falhar. Duas previsões que colidissem em nome com valores
diferentes impediriam a construção da release. Código e produtos antigos não
são substituídos dentro de suas releases; current é trocado atomicamente.

```bash
# Ensaio em destino separado, nunca sobre a série operacional:
python reprocessamento/release_phase4.py promote reprocessamento/releases/candidata \
  --target /tmp/ensaio-MET --rehearsal
# Produção: fornecer destino real e aceite vinculado ao hash de release.json:
python reprocessamento/release_phase4.py promote reprocessamento/releases/candidata \
  --target /DESTINO/VALIDADO --acceptance /CAMINHO/aceite-consumidores.json
# Restaurar release anterior (necessário já haver duas versões):
python reprocessamento/release_phase4.py rollback --target /DESTINO/VALIDADO
```

O aceite deve declarar release_sha256, approved=true e consumers contendo
BlueSky, preditor e planilhas. Deve ser preenchido após os testes reais dos
consumidores. Não é criado automaticamente nem simulado como aceite de produção.
Current e previous apontam para releases verificadas, protegidos por lock.
O ponteiro previous permite recuperação mesmo se o log for interrompido após
uma promoção. Repetir a promoção atual é no-op e preserva o rollback anterior.

Antes da promoção real: manter backup de código, configuração e série antiga;
confirmar janela de manutenção/agendador; apontar consumidores ao novo destino
de produtos; fornecer MET_PATH_CONF para a configuração operacional validada.
A configuração original é preservada no pacote; não se inventa um host/destino.
A ferramenta inclui o utilitário de rollback no próprio pacote de código.

## Comunicação aos consumidores

As mudanças de valor das fases anteriores estão reunidas em
[13-comunicacao-consumidores.md](13-comunicacao-consumidores.md).
Esse documento é o material de comunicação; nenhuma mensagem externa foi enviada.

## Evidências finais

Resultado: **205 testes locais aprovados**, 3 testes de remotos Git excluídos.
Foram gerados e verificados **1.098 CSVs e 3 PNGs** a partir de 12 amostras reais,
sem falhas numéricas ou de contrato. Há 108 pares de temperatura e 108 de vento
com METAR. MAE de temperatura: **2,179 °C**, bias **+0,416 °C**; MAE de velocidade
do vento: **2,758 kt**. Interpretar essas métricas com a tolerância temporal e
as limitações de coordenadas descritas acima; não são certificado operacional.

Evidências persistentes:
- `reprocessamento/reports/fase-4/validation.json`: campanha, fontes e resultados.
- `reprocessamento/reports/fase-4/rehearsal.json`: promoção/rollback e backup.
- `reprocessamento/reports/fase-4/tests.json`: suíte final e hashes atuais.
- `reprocessamento/phase4-data/`: binários/manifesto de origem (fora do Git).
- `reprocessamento/phase4-runs/20221215-17/`: produtos e logs (fora do Git).
- `reprocessamento/releases/phase4-candidate/`: pacote candidato verificado.
- `reprocessamento/phase4-rehearsal/`: destino local do ensaio, com duas versões
  preservadas e a primeira restaurada ao final. São snapshots do mesmo conjunto
  validado; não há série de produção disponível para restaurar neste ambiente.

O backup local registra núcleo GFS/configuração do ensaio; o backup completo
original da Fase 0 e os pacotes de release preservam o restante do código.
O backup da produção real, seu agendador e a configuração dos consumidores ainda
precisam ser confirmados no destino efetivo. Verificar acesso/permissões com a
conta operacional real antes de apontar consumidores ao diretório da release.

O ensaio local de promoção/rollback não representa publicação em produção.
Nenhuma mensagem externa, push ou merge foi realizado.
