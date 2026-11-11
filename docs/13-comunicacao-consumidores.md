# Mudanças para os consumidores de produtos MET

Destinatários: responsáveis por BlueSky, preditor e planilhas/sites.

- Headers, unidades e nomes canônicos de variáveis foram preservados.
- A coluna latitude já era crescente. Agora o valor está alinhado à coordenada;
  não inverter novamente as linhas no consumidor.
- Vento V usa a componente V real. angMET passa a estar em [0,360).
- hMET/halt de winds são metros convertidos para pés: 20 m = 65,6168 ft.
- Ciclos nas fronteiras 06/12/18 e nomes de níveis refletem o dado efetivo.
- chuvaNaoConvec continua sendo precipitação total e mantém o rótulo histórico.
- temps continua sendo temperatura de pele, não temperatura do ar a 2 m.
- O preditor recebe temperatura em Kelvin; matrizes escalares usam Celsius.
- JSON bruto METAR conserva as chaves com espaço final. As novas gravações são
  atômicas; os 12 JSONs históricos inválidos não foram reescritos.

Aceite necessário: abrir os arquivos candidatos nos consumidores reais, confirmar
unidades, sentido do vento, orientação e paths; executar seus cenários usuais;
registrar evidências e vincular o aceite ao SHA-256 da release.json exata.
Os testes de contrato locais não equivalem à execução dos aplicativos externos.
