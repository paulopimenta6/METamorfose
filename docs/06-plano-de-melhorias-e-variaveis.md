# Plano de melhorias e auditoria de variáveis — servidor_MET


> **Estado após as Fases 3 e 4:** robustez operacional implementada e Fase 4
> validada localmente. Consulte [11-fase-3-resultados.md](11-fase-3-resultados.md)
> e [12-fase-4-resultados.md](12-fase-4-resultados.md) para comportamento atual,
> testes, overrides e limites; descrições abaixo preservam o histórico.

**Status:** Fases 1 e 2 executadas no worktree `METamorfose` (branch `execucao`); Fase 3 implementada (documento 11); Fase 4 implementada e validada localmente; aceite externo e producao pendentes (documento 12).
**Data:** 23/10/2026; execuções das Fases 1 e 2 registradas em 27/10/2026.
**Escopo:** conclusões sobre nomenclatura e semântica das variáveis, revisão da orientação norte-sul e plano priorizado de correções do `servidor_MET`.

> **Restrições obrigatórias**
>
> - A aquisição GRIB permanece congelada: `goGribV2.sh`, ciclos `00/06/12/18`, previsões `f000/f006/f012/f018`, resoluções `0p25`/`1p00`, URLs e escopo não mudam.
> - Nenhuma variável ou produto será renomeado, removido ou adicionado.
> - Nomes de colunas, schemas e contratos existentes serão preservados, salvo decisão explícita em contrário.
> - Este documento é um plano. As Fases 1 e 2 foram executadas conforme a ordem e os critérios abaixo; os registros estão em [09-fase-1-resultados.md](09-fase-1-resultados.md) e [10-fase-2-resultados.md](10-fase-2-resultados.md). As fases 3–4 dependem de aprovação.

---

## 1. Resumo executivo

A auditoria das variáveis encontrou:

1. **Nenhum erro de digitação** nas chaves canônicas do catálogo (`ps`, `prnm`, `temp`, `temps`, `nuvem`, `chuvaNaoConvec`, `chuvaConvec`, `umidadeRel`, `u`, `v`, `uSupe`, `vSupe`).
2. **Um erro semântico real:** `chuvaNaoConvec` aponta para `Total Precipitation`, que é precipitação total, não apenas a parcela não convectiva.
3. **Nomes históricos ou imprecisos, mas não errados:** `temps`, `nuvem`, `uSupe`, `vSupe`, `wind`, `winds`.
4. **Erros de nome fora do catálogo:** o help cita `chuva` e a região `MN`, que não existem; alguns cabeçalhos de vento usam `nivel<hPa>` para valores em metros; chaves JSON do METAR têm espaço no final.

Na parte de cálculo, foram confirmados:

- **Inversão norte-sul** em mapas e matrizes: `lat` é invertida, mas `data` não.
- **Componente V recebendo U** em dois pontos do fluxo automático de vento superficial.
- **`hMET`/`halt` de `winds`** calculados com a fórmula de pressão, embora o nível esteja em metros.
- **Direção do vento** em `[-180, 180]`, sem normalização para `[0, 360)`.
- **Seleção de ciclo** com intervalo inclusivo e `chdir` relativo, usando o ciclo anterior na primeira hora de cada ciclo.

O plano está dividido em quatro fases: preparação, correção de cálculo, produtos/operações e robustez/rollout. As correções de cálculo vêm primeiro porque os produtos atuais não devem ser usados como referência geográfica ou de vento antes delas.

---

## 2. Restrições e não objetivos

### 2.1 O que não será alterado

- `goGribV2.sh` e qualquer parâmetro de aquisição GRIB.
- Ciclos, previsões e resoluções baixadas.
- Nomes das variáveis e dos produtos.
- Existência, quantidade ou semântica declarada dos produtos.
- Layouts de CSV/JSON e nomes de colunas, salvo correção de valor ou decisão explícita de schema v2.

### 2.2 O que este plano pode alterar

- Valores calculados (vento, altura, ângulo, orientação de grade).
- Qual ciclo local é lido, sem mudar o que é baixado.
- Lógica de uso de variáveis que não têm campo no nível pedido.
- Documentação, help e validação.
- Robustez operacional (logs, atomicidade, locks, fechamento de recursos).

---

## 3. Conclusões sobre as variáveis

### 3.1 Catálogo canônico

Fonte: `classes_MET/processamento_dados_MET.py:19-30` (AUT) e `:176-187` (MAN).

| Chave | Campo GFS (`name`) | `typeOfLevel` | Níveis usados | Saída | Diagnóstico | Ação |
|---|---|---|---|---|---|---|
| `ps` | `Surface pressure` | `surface` | Superfície | hPa | Correto | Manter |
| `prnm` | `Pressure reduced to MSL` | `meanSea` | Superfície | hPa | Correto; sigla histórica coerente | Manter |
| `temp` | `Temperature` | `isobaricInhPa` | 150–1000 hPa | °C | Correto | Manter |
| `temps` | `Temperature` | `surface` | Superfície | °C | Campo é temperatura de pele; nome ambíguo | Manter e documentar |
| `nuvem` | `Total Cloud Cover` | `isobaricInhPa` | 150–1000 hPa | % | Nome abreviado; campo é cobertura total | Manter e documentar |
| `chuvaNaoConvec` | `Total Precipitation` | `surface` | Superfície | kg m⁻² ≈ mm | **Nome não corresponde ao dado**: é precipitação total | Manter, documentar e não alterar o seletor |
| `chuvaConvec` | `Convective precipitation (water)` | `surface` | Superfície | kg m⁻² ≈ mm | Correto | Manter |
| `umidadeRel` | `Relative humidity` | `isobaricInhPa` | 150–1000 hPa | % | Nome correto; não há campo superficial no mapeamento | Manter; corrigir uso com `-ns` |
| `u` | `U component of wind` | `isobaricInhPa` | 150–1000 hPa | m s⁻¹ | Correto | Manter |
| `v` | `V component of wind` | `isobaricInhPa` | 150–1000 hPa | m s⁻¹ | Correto | Manter |
| `uSupe` | `U component of wind` | `heightAboveGround` | 20, 30, 40, 50, 80 m | m s⁻¹ | Nome histórico; “Supe” não significa superfície literal | Manter e documentar |
| `vSupe` | `V component of wind` | `heightAboveGround` | 20, 30, 40, 50, 80 m | m s⁻¹ | Nome histórico; idem | Manter e documentar |

### 3.2 Veredito da nomenclatura

- **Erro ortográfico:** não há.
- **Erro semântico real:** um, em `chuvaNaoConvec`.
- **Nomes ambíguos ou históricos:** `temps`, `nuvem`, `uSupe`, `vSupe`, `wind`, `winds`.
- **Erros de documentação/contrato:** `chuva` e `MN` no help; `nivel<hPa>` para `winds`; chaves METAR com espaço final.
- **Decisão:** todos os nomes de variáveis e produtos permanecem. Os caveats vão para a documentação e para os testes de contrato.

### 3.3 `chuvaNaoConvec` — o único erro semântico

O GFS `Total Precipitation` é a soma da precipitação convectiva com a não convectiva (estratiforme). O nome `chuvaNaoConvec` sugere apenas a parcela não convectiva.

Consequências:

- Quem consome `chuvaNaoConvec` esperando chuva estratiforme recebe um valor que inclui a convectiva.
- Se o consumidor tentar obter a não convectiva fazendo `chuvaNaoConvec - chuvaConvec`, o resultado pode ficar negativo ou incorreto, porque `chuvaNaoConvec` já é o total.
- Relatórios e séries podem superestimar a chuva não convectiva.

**Decisão:** manter o nome e o seletor atuais. Não renomear para `chuvaTotal`, não trocar o campo e não criar uma variável nova. A documentação deve declarar explicitamente que o valor é **precipitação total**. Se houver necessidade de chuva realmente não convectiva, isso será uma decisão separada, fora deste plano.

### 3.4 `temps` — temperatura de pele, não 2 m

`Temperature` em `surface` é a temperatura da superfície (skin), não a temperatura do ar a 2 m (`2 metre temperature`, em `heightAboveGround`, nível 2).

O nome `temps` é coerente com “temperatura de superfície”, mas ambíguo para quem espera temperatura do ar.

**Decisão:** manter o nome e o seletor. Documentar que o produto usa temperatura de pele. Não trocar para `2 metre temperature` sem autorização, pois isso mudaria os valores e o contrato.

### 3.5 `umidadeRel` — nome correto, uso inválido em superfície

O mapeamento só tem `Relative humidity` em `isobaricInhPa` (150–1000 hPa). Não existe campo superficial mapeado para `umidadeRel`.

O controlador original chamava `umidadeRel -ns`. No AUT, a lista de superfície ficava vazia e nenhum produto era gerado. No MAN, o atributo de superfície não era criado e o acesso podia levantar `AttributeError`.

**Decisão:** manter o nome `umidadeRel`. **Correção aplicada na Fase 2:** o controlador usa `-n 850` e o código falha com mensagem clara para `-ns`; `umidadeRel -n 850` continua válido.

### 3.6 `nuvem`, `uSupe` e `vSupe`

- `nuvem` é abreviação de `Total Cloud Cover`; não é erro, mas o nome não explicita “total”.
- `uSupe`/`vSupe` usam níveis de 20/30/40/50/80 m em `heightAboveGround`; “Supe” é histórico e não significa superfície literal.

**Decisão:** manter os nomes, documentar os níveis e não alterar os seletores.

### 3.7 `wind` e `winds`

Esses nomes não estão no dicionário de variáveis; são produtos tratados pelas classes de vento:

- `wind`: níveis de pressão (hPa).
- `winds`: níveis quase-superficiais (20/30/40/50/80 m).

O plural é incomum, mas é intencional e já está consolidado no CLI e nos nomes dos arquivos. **Não renomear.**

### 3.8 Nomes fora do catálogo

| Local | Problema | Decisão |
|---|---|---|
| `bash/reqs_MAN_MET.sh:27` | Help lista `chuva`, que não existe | Corrigir a documentação para `chuvaConvec`/`chuvaNaoConvec`; não criar a variável `chuva` |
| `bash/automatiza_vento_MET.sh:13` | Help lista a região `MN`, que não existe | Corrigir para uma região válida; as regiões são `SP`, `RJ`, `AM`, `DF`, `PR`, `RS`, `MG`, `PA`, `PE`, `CE`, `SA` (`regioes_predefinidas_MET.py:89-99`) |
| `classes_MET/gera_matriz_vento_MAN_MET.py:145` | Cabeçalho `nivel<hPa>` também é usado para `winds`, cujo valor é em metros | Manter o cabeçalho nesta fase; corrigir o valor de `halt` e documentar. Mudança de header seria schema v2 |
| `classes_MET/gera_matriz_vento_MAN_MET.py:253` e `gera_matriz_vento_MET.py:172` | `hMET`/`hMET<feet>` é usado para `winds` | Manter o nome; corrigir o valor |
| `METARpy/METARpy.py:33-35` | Chaves JSON com espaço no final: `"id_localidade "`, `"data "`, `"mensagem_metar "` | Não é variável GRIB. Preservar por compatibilidade ou versionar o schema; não alterar silenciosamente |

---

## 4. Revisão da orientação norte-sul

### 4.1 Resultado

**Confirmado: há inversão norte-sul.** O problema atinge mapas e matrizes, não apenas a imagem.

O `pygrib` entrega a grade de norte para sul:

```text
lat[0,0]  =  90.0
lat[-1,0] = -90.0
data[0,0]  (norte) = 263.9655 K
data[-1,0] (sul)   = 242.4655 K
```

O código faz:

```python
data, lat, lon = objMET.data(...)
lon = lon[0, :]
lat = lat[:, 0]
lat = lat[::-1]          # inverte a latitude
# data não é invertida
```

Resultado: a primeira linha de `data` continua sendo 90°N, mas passa a ser associada à latitude -90° (sul). O mapa mostra os rótulos de latitude corretos, mas os valores de cada latitude estão espelhados. O erro é silencioso.

Demonstração sintética:

```text
lat = -90  valor = 90
lat = -45  valor = 45
lat =   0  valor = 0
lat =  45  valor = -45
lat =  90  valor = -90
```

A evidência empírica completa está em `docs/05-diagnostico.md:86-162`.

### 4.2 Onde ocorre

**Mapas:**

- `classes_MET/gera_mapas_MET.py:113-118` — mapas escalares AUT;
- `classes_MET/gera_mapas_MAN_MET.py:89-94` — mapas escalares MAN;
- `classes_MET/gera_mapas_vento_MET.py:81-88` — mapas de vento AUT;
- `classes_MET/gera_mapas_vento_MAN_MET.py` — mapas de vento MAN (métodos LC, barb e LCbarb).

**Matrizes:**

- `classes_MET/gera_matriz_MET.py:81-86`;
- `classes_MET/gera_matriz_MAN_MET.py:62-67`;
- `classes_MET/gera_matriz_vento_MET.py:117-125`;
- `classes_MET/gera_matriz_vento_MAN_MET.py:90-94` e equivalentes nos três métodos.

### 4.3 Correção proposta

Centralizar a normalização em uma função única:

```python
def normaliza_grade(data, lat, lon):
    """Garante latitude crescente e dados alinhados à latitude."""
    lat_1d = lat[:, 0] if lat.ndim == 2 else lat
    if lat_1d[0] > lat_1d[-1]:
        data = data[::-1, :]
        lat = lat[::-1]
    assert data.shape[0] == lat.shape[0]
    assert data.shape[1] == lon.shape[1]
    return data, lat, lon
```

Regras:

1. Aplicar em todos os geradores de mapas e matrizes.
2. No `flag 3` (cruzamento do dateline), normalizar `data_ini` e `data_fim` **antes** de concatenar.
3. Para vento, aplicar a mesma normalização a `data_U` e `data_V`, com a mesma máscara.
4. Não basta remover `lat[::-1]`: os CSVs também estão errados e são consumidos diretamente.
5. A coluna `lat` já é crescente no baseline; a correção deve alinhar `data` à `lat`, preservando a ordem das linhas. Só comunicar mudança de ordem se ela realmente ocorrer.

### 4.4 Teste de aceitação

- Ler o mesmo GFS com `pygrib` e comparar um ponto conhecido (ex.: latitude -10) com a linha correspondente do CSV.
- Verificar que a primeira linha do CSV tem a menor latitude da caixa e que o valor bate com `data[-1, :]` do GRIB.
- Verificar que o mapa não está espelhado verticalmente em relação a um campo Assimétrico (ex.: temperatura com gradiente norte-sul).
- Verificar que mapas e matrizes do mesmo produto usam a mesma ordem de latitude.

---

## 5. Correções de cálculo (Bloco A)

Estas correções não mudam nomes de variáveis nem produtos. Elas mudam apenas valores, orientação, seleção de ciclo e uso de níveis.

### C-01 — Componente V recebendo U (D-02)

**Onde:**

- `classes_MET/gera_mapas_vento_MET.py:213-216` — mapa de vento superficial AUT;
- `classes_MET/gera_matriz_vento_MET.py:312-317` — matriz do preditor AUT.

**Código atual:**

```python
# gera_mapas_vento_MET.py
for nivelQuaseSupe in varNivelProxSupe:
    u_comp = processamento_dados_met_AUT("uSupe", nivelQuaseSupe).define_lista_var_com_altitude()
    v_comp = processamento_dados_met_AUT("uSupe", nivelQuaseSupe).define_lista_var_com_altitude()
    gera_mapas_vento(u_comp, v_comp, lonslats, varRegiaoNome, nivelQuaseSupe)
```

```python
# gera_matriz_vento_MET.py
geraMatriz_Vento_Resu(u_comp_supe, v_comp_supe, lon_lat, varReg, varNivel_sup)
geraMatriz_Vento_UVT_predi(u_comp_supe, u_comp_supe, t_comp_supe, lon_lat, varReg, varNivel_sup)
```

**Correção:**

```python
v_comp = processamento_dados_met_AUT("vSupe", nivelQuaseSupe).define_lista_var_com_altitude()
```

```python
geraMatriz_Vento_UVT_predi(u_comp_supe, v_comp_supe, t_comp_supe, lon_lat, varReg, varNivel_sup)
```

**Observações:**

- A matriz BlueSky AUT (`geraMatriz_Vento_Resu`) já recebe `v_comp_supe` correto.
- O fluxo MAN já usa `uSupe` e `vSupe` corretamente.
- O cabeçalho `vento U`/`vento V` está correto; o problema é o valor, não o nome.

**Teste:**

- `U=10, V=0` → `vento V=0`, resultante `10`.
- `U=0, V=10` → `vento U=0`, `vento V=10`.
- `U=10, V=10` → resultante `14,14`.
- Comparar com os campos U e V lidos diretamente do GRIB em um ponto conhecido.

### C-02 — Altura do vento superficial (D-03)

**Onde:**

- `classes_MET/gera_matriz_vento_MET.py:170`;
- `classes_MET/gera_matriz_vento_MAN_MET.py:143`;
- `classes_MET/gera_matriz_vento_MAN_MET.py:251`.

**Problema:** `converte_altitude()` implementa a fórmula barométrica e espera pressão em hPa:

```python
def converte_altitude(pres):
    p0 = 1013.25
    h_alt = (1 - (pres / p0) ** 0.190284) * 145366.45
    return h_alt
```

Para `winds`, `nivel` é 20/30/40/50/80 **metros**. Passar esse valor como pressão produz 55.696–76.487 ft.

**Correção:**

```python
def calcula_hmet(nivel, eh_vento_superficie):
    if eh_vento_superficie:
        return float(nivel) * 3.28084
    return converte_altitude(nivel)
```

Aplicar `eh_vento_superficie=True` no fluxo `winds` e `False` no fluxo `wind`. Não inferir pelo valor de `nivel`; passar a informação explicitamente para evitar ambiguidade futura.

**Valores esperados:**

| Altura | `hMET` correto |
|---:|---:|
| 20 m | 65,6 ft |
| 30 m | 98,4 ft |
| 40 m | 131,2 ft |
| 50 m | 164,0 ft |
| 80 m | 262,5 ft |

**Headers:** `hMET`, `halt` e `nivel<hPa>` permanecem. Só o valor é corrigido. Se o header `nivel<hPa>` for considerado parte do contrato, ele fica como está e o caveat “para `winds`, o valor é em metros” vai para a documentação. Mudança de header seria schema v2.

**Teste:**

- 20 m → 65,6 ft; 80 m → 262,5 ft (tolerância 0,1 ft).
- Nenhum `hMET` de `winds` acima de 1.000 ft.
- `wind` em 500 hPa continua com a conversão barométrica esperada.

### C-03 — Orientação norte-sul (D-01)

Correção descrita na seção 4. Afeta mapas e matrizes. No baseline, a coluna `lat` já é crescente; o que está errado é o desalinhamento dos dados. A correção deve preservar a ordem das linhas e alinhar `data` à `lat`.

**Teste:** ver seção 4.4.

### C-04 — Normalização da direção do vento (D-12)

**Onde:**

- `classes_MET/gera_matriz_vento_MET.py:40-43`;
- `classes_MET/gera_matriz_vento_MAN_MET.py:51-54`.

**Código atual:**

```python
def criaAngMET(data_u, data_v):
    angResult = ((180 / np.pi) * (np.arctan2((-data_u), (-data_v))))
    return angResult
```

`arctan2` retorna `[-180, 180]`. Exemplo: `U=10, V=0` → `-90°`, equivalente a `270°`.

**Correção:**

```python
angResult = (np.degrees(np.arctan2(-data_u, -data_v)) + 360.0) % 360.0
```

**Teste:**

| U | V | Direção esperada |
|---:|---:|---:|
| 10 | 0 | 270° |
| -10 | 0 | 90° |
| 0 | 10 | 180° |
| 0 | -10 | 0° |

Todos os valores em `[0, 360)`.

### C-05 — Seleção do ciclo GFS (D-04)

**Onde:** `classes_MET/leitura_dados_grib_MET.py:77-88`.

**Problema:**

- A comparação é inclusiva nos dois extremos: `<= hora <=`.
- O `os.chdir` é relativo. Depois de entrar em `00`, a verificação `os.path.exists("06")` é feita dentro de `00`, não na raiz da data.

Na primeira hora de cada ciclo, o produto pode usar o ciclo anterior:

| Hora local | Ciclo usado | Rótulo | Situação |
|---|---|---|---|
| 00:00–00:59 | 00 | 00 | Correto |
| 01:00–05:59 | 00 | 00 | Correto |
| 06:00–06:59 | 00 | 06 | **Divergente** |
| 07:00–11:59 | 06 | 06 | Correto |
| 12:00–12:59 | 06 | 12 | **Divergente** |
| 13:00–17:59 | 12 | 12 | Correto |
| 18:00–18:59 | 12 | 18 | **Divergente** |
| 19:00–23:59 | 18 | 18 | Correto |

**Correção:**

- Montar caminhos absolutos.
- Usar intervalo semiaberto: `[ciclo, proximo_ciclo)`.
- Não usar `os.chdir` relativo para navegar entre ciclos.

```python
hora_int = int(hora)
ciclo = max(c for c in (0, 6, 12, 18) if c <= hora_int)
proximo = ciclo + 6 if ciclo < 18 else 24
if not (ciclo <= hora_int < proximo):
    raise ValueError("hora fora dos ciclos GFS")
```

**Importante:** isso não altera o `goGribV2.sh`, as URLs, os ciclos baixados ou a resolução. Muda apenas qual diretório local já existente é lido.

**Teste:** 05:59 → 00; 06:00 → 06; 11:59 → 06; 12:00 → 12; 17:59 → 12; 18:00 → 18; 23:59 → 18; 00:00 → 00.

### C-06 — `umidadeRel -ns` (D-06)

**Onde:** `bash/automatizacao_controle_MET.sh:52` e `:57`.

**Problema:** o mapeamento de `umidadeRel` só tem `Relative humidity` em `isobaricInhPa`. Com `-ns`, o AUT não encontra campo superficial e não gera produto; o MAN pode levantar `AttributeError`.

**Correção aplicada:** as duas chamadas `-ns` foram substituídas por `-n 850` no controlador. O nome `umidadeRel` permanece. O AUT e o MAN validam o tipo de nível antes de ler o GRIB; `-ns` falha com mensagem que indica `-n 850`, sem criar produto vazio nem `AttributeError`.

**Teste:**

- `umidadeRel -ns` retorna erro claro e não gera produto.
- `umidadeRel -n 850` gera CSV/PNG com valores entre 0 e 100; o controlador usa esse nível.

**Resultado (Fase 2):** concluído. `tests/test_phase2_acceptance.py` verifica a mensagem, a ausência de saída e o produto em 850 hPa.

### C-07 — Ativação de `winds` (D-05)

O controlador tinha chamadas de `winds` sem `-ns` e um bloco duplicado de `wind` em 1000/200 hPa (`bash/automatizacao_controle_MET.sh:17-18,62-65`). Essas chamadas eram no-op.

**Decisão:** ativar `winds` somente depois de C-01, C-02 e C-03 estarem corrigidos e testados, como ocorreu na Fase 1.

**Correção aplicada:** o controlador chama `winds -ns` para SP e RJ, mantém um único bloco de `wind` em 1000/200 hPa e os wrappers rejeitam chamadas sem `-v` ou sem `-n`/`-ns`. Os produtos de `winds` usam U/V reais, `hMET` em metros × 3,28084 e `angMET` em `[0, 360)`.

**Teste:**

- Os mapas de 20/30/40/50/80 m e as matrizes BlueSky/preditor são gerados;
- `hMET` de 20 m ≈ 65,6 ft e de 80 m ≈ 262,5 ft;
- não há chamada no-op nem bloco duplicado no controlador.

**Resultado (Fase 2):** concluído; a validação independente compara os produtos `winds` com `pygrib` em T-07.

---

## 6. Plano de melhorias por fases

### Fase 0 — Preparação e baseline

**Objetivo:** criar uma base segura para comparar antes/depois.

- Fazer backup do código, configuração (`environment/path.conf`) e produtos existentes.
- Como não há repositório Git no diretório, criar um snapshot com data/hora.
- Escolher uma data/ciclo/região/nível de referência e salvar os produtos atuais em diretório separado.
- Criar um harness de teste com:
  - arrays sintéticos para orientação e vento;
  - uma amostra real de GFS 0.25° para validar `pygrib`;
  - comparação de um ponto conhecido.
- Inventariar consumidores de CSV/JSON: ordem das linhas, headers, unidades e chaves.
- Congelar `goGribV2.sh`; nenhuma alteração.

**Critério de saída:** baseline, backup e harness prontos; consumidores identificados.

### Fase 1 — Correção de cálculo (prioridade máxima)

**Objetivo:** corrigir os erros que tornam os produtos geograficamente ou fisicamente errados.

Ordem:

1. **C-05** — seleção do ciclo.
2. **C-03** — orientação norte-sul.
3. **C-01** — U/V.
4. **C-02** — `hMET`/`halt`.
5. **C-04** — `angMET`.

**Critério de saída:** T-01 a T-05 passam; mapas e matrizes conferem com leitura independente do GRIB; nenhum nome de variável/produto mudou; reprocessamento de amostra em diretório separado.

**Resultado (27/10/2026):** concluída na branch `execucao`. T-01 a T-05 estão
verdes em `tests/test_phase1_acceptance.py`; os 20 produtos da amostra foram
reprocessados em `reprocessamento/reports/20261022-00/` e os 13 CSVs conferem
linha a linha com leitura independente via `pygrib`; nomes, headers e unidades
foram preservados. Detalhes em
[09-fase-1-resultados.md](09-fase-1-resultados.md).

### Fase 2 — Produtos, CLI e METAR

**Objetivo:** corrigir produtos ausentes/errados em condições comuns e melhorar a usabilidade.

Itens:

- **C-06** — `umidadeRel -ns`.
- **C-07** — ativar `winds` somente após a Fase 1.
- **D-05** — remover bloco duplicado e chamadas no-op do controlador.
- **D-07/D-08** — METAR: JSON válido (sem concatenação) e timestamp UTC com rollover.
- **D-09** — intervalo MAN aceitar as duas ordens.
- **D-10** — limpeza com `date -d "-2 days" +"%Y%m%d"` e remoção de `0p25`, `1p00` e legados.
- **D-14/D-28** — CLI manual: argumento duplicado, validação, help gerado a partir do catálogo.
- **D-15** — remover geração duplicada da matriz MAN.
- **D-17** — corrigir a checagem `str(nuvem) is not None`.
- **D-24** — documentar a janela de acumulação da chuva; manter o nome.
- **D-25** — corrigir variáveis indefinidas no `automatizaMetar.sh`.
- **D-27** — documentar `temps` como temperatura de pele; não trocar o seletor.

**Critério de saída:** T-06 a T-12 passam; METAR válido; CLI com erros claros; produtos automáticos completos.

**Resultado (27/10/2026):** concluída na branch `execucao`, sobre o commit
`9288c1f`. T-06 a T-12 estão verdes em `tests/test_phase2_acceptance.py`
(36 testes); a suíte completa tem 162 testes; a validação independente em
`reprocessamento/validar_fase2.py` executou 177 verificações com 0 falhas. Os
produtos da Fase 1 foram preservados, `goGribV2.sh` continua congelado e os
nomes de variáveis, produtos, headers e schemas não mudaram. Detalhes em
[10-fase-2-resultados.md](10-fase-2-resultados.md).

### Fase 3 — Robustez e operação

**Objetivo:** reduzir falhas silenciosas e facilitar manutenção.

Itens:

- **D-16** — retornar 0 em sucesso; não usar `exit 1` no fim.
- **D-18** — sanitizar caminho de saída e nome de região; usar `pathlib`.
- **D-19** — remover artefatos obsoletos (`controla_env.pyc`, `.swp`, `__pycache__`) e organizar empacotamento.
- **D-20** — logging, escrita atômica (`.tmp` + `os.replace`), lock e idempotência.
- **D-21** — corrigir validação de latitude/longitude em `ponto_regiao_MET.py`.
- **D-22** — usar `variavelMET` em vez do global `varMET` no ramo de chuva.
- **D-23** — substituir `os.mkdir`/`os.chdir` global por `pathlib` e `mkdir(parents=True, exist_ok=True)`.
- **D-26** — fechar figuras (`plt.close`) e arquivos GRIB (`with pygrib.open(...)`).

**Critério de saída:** T-13 a T-15 passam; runbook atualizado; nenhuma falha silenciosa conhecida.

**Resultado (27/10/2026):** concluída na branch `execucao`. T-13 a T-15 estão
verdes em `tests/test_phase3_acceptance.py` (23 regressões); a suíte da época
tinha **182 testes locais aprovados** e 3 de rede excluídos. A amostra real
preservou 13 CSVs e 7 PNGs byte a byte. O controlador retorna 0 somente em
sucesso e 75 em concorrência; a escrita é atômica por arquivo, com locks e logs
no stderr, mas sem manifesto/`run_id` por execução. O runbook foi atualizado.
Detalhes em [11-fase-3-resultados.md](11-fase-3-resultados.md).

### Fase 4 — Reprocessamento, validação e rollout

**Objetivo:** colocar as correções em produção com segurança.

- Reprocessar uma janela histórica representativa (ex.: 30 dias ou datas com estações de referência) em diretório separado.
- Comparar com leitura independente do GRIB e com observações/METAR.
- Validar consumidores BlueSky, preditor e planilhas.
- Comunicar mudanças de contrato:
  - dados alinhados à latitude crescente (a coluna `lat` já era crescente);
  - `hMET`/`halt` de `winds` mudou;
  - `vento V` foi corrigido;
  - `angMET` agora está em `[0, 360)`;
  - seleção de ciclo mudou nas fronteiras.
- Atualizar `docs/03-dados-e-saidas.md` e o help.
- Manter rollback: código e produtos antigos preservados; novos produtos em diretório separado até aprovação.

**Critério de saída:** validação aprovada; produtos novos promovidos; rollback documentado.

**Resultado local (28/10/2026):** campanha real de 15–17/12/2022 com f000, f006,
f012 e f018, 1.098 CSVs e 3 PNGs verificados, release candidata e ensaio de
promoção/rollback concluídos. A suíte local tem **205 testes aprovados**. O
aceite dos consumidores BlueSky/preditor/planilhas e a promoção em produção
continuam pendentes. Detalhes em
[12-fase-4-resultados.md](12-fase-4-resultados.md).

---

## 7. Inventário de achados e decisão

| ID | Severidade | Achado | Decisão | Fase |
|---|---|---|---|---|
| D-01 | Crítica | Orientação N-S invertida | Corrigir | 1 |
| D-02 | Crítica | V recebe U no vento superficial | Corrigir | 1 |
| D-03 | Crítica | `hMET` de `winds` calculado como pressão | Corrigir | 1 |
| D-04 | Alta | Ciclo anterior na primeira hora | Corrigir | 1 |
| D-05 | Alta | `winds` e bloco duplicado no-op | Corrigir controlador; ativar após Fase 1 (feito na Fase 2) | 2 |
| D-06 | Alta | `umidadeRel -ns` sem produto | Corrigir uso | 2 |
| D-07 | Alta | JSON METAR concatenado | Corrigir | 2 |
| D-08 | Alta | Timestamp METAR com ano/mês correntes | Corrigir | 2 |
| D-09 | Média | Intervalo MAN exige mínimo maior que máximo | Corrigir | 2 |
| D-10 | Média | Limpeza com data errada e só `0p25` | Corrigir | 2 |
| D-11 | Baixa | Teste de diretório no `goGribV2.sh` | Fora de escopo (congelado) | — |
| D-12 | Média | Direção do vento fora de 0–360 | Corrigir | 1 |
| D-13 | Média | `chuvaNaoConvec` mapeia precipitação total | Documentar; não renomear | 2 |
| D-14 | Média | CLI manual posicional/duplicada | Corrigir | 2 |
| D-15 | Baixa | Matriz MAN escalar gerada duas vezes | Corrigir | 2 |
| D-16 | Baixa | `exit 1` em sucesso | Corrigir | 3 |
| D-17 | Baixa | Checagem de visibilidade sempre verdadeira | Corrigir | 2 |
| D-18 | Baixa | Caminho/região sem sanitização | Corrigir | 3 |
| D-19 | Baixa | Artefatos obsoletos | Limpar/empacotar | 3 |
| D-20 | Média | Sem logging/atomicidade/lock | Corrigir | 3 |
| D-21 | Baixa | `ponto_regiao` usa latitude em condições de longitude | Corrigir | 3 |
| D-22 | Baixa | `varMET` global no ramo de chuva | Corrigir | 3 |
| D-23 | Baixa | `controla_env` com `os.mkdir`/`os.chdir` | Corrigir | 3 |
| D-24 | Baixa | Chuva `f000` rotulada como `06` | Documentar; manter nome | 2 |
| D-25 | Baixa | Variáveis indefinidas no `automatizaMetar.sh` | Corrigir | 2 |
| D-26 | Baixa | Figuras/GRIB não fechados | Corrigir | 3 |
| D-27 | Baixa | `temps` é pele, não 2 m | Documentar; não alterar seletor | 2 |
| D-28 | Baixa | Shell sem `set -euo pipefail`; help inconsistente | Corrigir | 2/3 |

---

## 8. Testes de aceitação

| ID | Teste | Critério | Estado |
|---|---|---|---|
| T-01 | Orientação N-S | Ponto conhecido do GRIB confere com o CSV; mapa não espelhado; primeira linha = menor latitude | Verde (Fase 1) |
| T-02 | U/V | U/V puros e diagonais; coluna `vento V` correta; resultante correta | Verde (Fase 1) |
| T-03 | `hMET`/`halt` | 20 m → 65,6 ft; 80 m → 262,5 ft; 500 hPa inalterado | Verde (Fase 1) |
| T-04 | `angMET` | Quatro quadrantes em `[0, 360)` | Verde (Fase 1) |
| T-05 | Ciclo | Fronteiras 05:59/06:00, 11:59/12:00, 17:59/18:00, 23:59/00:00 | Verde (Fase 1) |
| T-06 | `umidadeRel` | `-ns` falha claramente; `-n 850` funciona; mapa preserva `N850` | Verde (Fase 2) |
| T-07 | `winds` | Produto gerado após ativação; mapas e matrizes presentes; sem no-op | Verde (Fase 2) |
| T-08 | METAR | JSON válido; sem concatenação; timestamp UTC com rollover | Verde (Fase 2) |
| T-09 | Intervalo MAN | `200→500` e `500→200` produzem a mesma lista; nível inválido falha claramente | Verde (Fase 2) |
| T-10 | Limpeza | 01/03, 02/03 e 15/03 removem o dia correto; `0p25`, `1p00` e legados; datas de calendário inválidas falham | Verde (Fase 2) |
| T-11 | CLI | `-v chuva` e região `MN` retornam erro claro; níveis fora de 150–1000 falham; argumento duplicado não desloca posições | Verde (Fase 2) |
| T-12 | Visibilidade METAR | Classificação correta quando `nuvem` está ausente ou presente | Verde (Fase 2) |
| T-13 | Sanitização | Caminho de saída e região não permitem traversal; arquivos no lugar esperado | Verde (Fase 3; documento 11) |
| T-14 | Atomicidade | Falha no meio da escrita não deixa CSV/JSON parcial; lock evita execução concorrente | Verde (Fase 3; documento 11) |
| T-15 | Recursos | Figuras e GRIBs fechados; memória estável em lote | Verde (Fase 3; documento 11) |

**Verificação transversal de contrato:** antes/depois, comparar headers e nomes de variáveis/produtos. Nenhum nome deve mudar. A coluna `lat` já é crescente; a correção deve preservar a ordem das linhas e alinhar os dados à latitude.

---

## 9. Rollout, reprocessamento e rollback

### 9.1 Antes da implementação

- Backup completo do código e da configuração.
- Snapshot dos produtos atuais para comparação.
- Lista de consumidores e seus contratos.
- Janela de manutenção definida.

### 9.2 Durante

- Implementar em branch/worktree separado, se possível.
- Reprocessar em diretório separado (`reprocessamento/`), sem sobrescrever a série antiga.
- Rodar os testes da fase (T-01–T-05 na Fase 1; T-06–T-12 na Fase 2; T-13–T-15 na Fase 3).
- Comparar pontos conhecidos com `pygrib` e com METAR/estações.

### 9.3 Depois

- Comunicar as mudanças de valor e de ordem de linha.
- Atualizar `docs/03-dados-e-saidas.md`, `docs/04-operacao.md` e o help.
- Promover os produtos novos somente após aprovação.
- Manter os produtos antigos por um período de rollback.

### 9.4 Rollback

- Restaurar o backup do código e a configuração.
- Voltar a apontar os consumidores para os produtos antigos.
- Reverter o commit da fase no branch `execucao`; o baseline da Fase 0 e os produtos de `reprocessamento/` são imutáveis e servem de referência.
- A limpeza já está corrigida (D-10), mas continua sendo `rm -rf`: testar com `MET_BASE_DIR`/`MET_HOJE` antes de executar em produção.
- Não reverter `goGribV2.sh`; ele permanece congelado em todas as fases.

---

## 10. Riscos e decisões abertas

| Tema | Risco | Decisão atual |
|---|---|---|
| `chuvaNaoConvec` | Consumidores interpretarem como chuva não convectiva | Nome e seletor mantidos; documentado como precipitação total, inclusive o rótulo `+6` (Fase 2) |
| `temps` | Consumidores esperarem temperatura do ar a 2 m | Nome e seletor mantidos; documentado como temperatura de pele (Fase 2) |
| `winds` | Produto gerado com U/V ou `hMET` errados | Ativado na Fase 2 somente após as correções da Fase 1; validado contra `pygrib` |
| Header `nivel<hPa>` | Valor em metros para `winds` | Mantido e documentado; schema v2 continua sendo decisão separada |
| Ordem dos CSVs | Consumidores podem assumir que a coluna `lat` é crescente, mas os dados originais estavam desalinhados | Ordem crescente preservada e dados alinhados desde a Fase 1 |
| METAR | Chaves com espaço final e arquivos históricos inválidos | Chaves preservadas; escrita atômica e UTC desde a Fase 2; acervo antigo requer reparo/descarte |
| `goGribV2.sh` | Alteração acidental da aquisição | Congelado; SHA-256 verificado na validação da Fase 2 |
| Git | Perda de histórico/rollback | Histórico existe desde a Fase 0; commits por fase e baseline imutável |
| `exit 1` do controlador | Interpretar sucesso como falha | Corrigido na Fase 3: retorna 0 só em sucesso, propaga o primeiro erro real e retorna 75 em concorrência (D-16) |

---

## 11. Referências

- `docs/01-arquitetura.md` — arquitetura e dependências.
- `docs/02-fluxos.md` — fluxos automático, manual e METAR.
- `docs/03-dados-e-saidas.md` — catálogo, níveis, schemas e unidades.
- `docs/04-operacao.md` — cron, comandos e runbook.
- `docs/05-diagnostico.md` — evidências completas D-01 a D-28.
- `docs/09-fase-1-resultados.md` — resultados e testes T-01–T-05.
- `docs/10-fase-2-resultados.md` — resultados e testes T-06–T-12.
- `docs/11-fase-3-resultados.md` — robustez, testes T-13–T-15 e limites.
- `docs/12-fase-4-resultados.md` — campanha real, release/rollback e pendências.
- `tests/test_phase1_acceptance.py`, `tests/test_phase2_acceptance.py` — testes de aceitação.
- `tests/test_phase3_acceptance.py`, `tests/test_phase4_acceptance.py` — regressões e contratos das Fases 3/4.
- `reprocessamento/validar_fase1.py`, `reprocessamento/validar_fase2.py` — validação independente.
- `reprocessamento/phase4.py`, `reprocessamento/release_phase4.py` — campanha e release/rollback da Fase 4.
- `classes_MET/processamento_dados_MET.py` — dicionário de variáveis e seleção de níveis.
- `classes_MET/gera_mapas_MET.py`, `gera_matriz_MET.py` — produtos escalares AUT.
- `classes_MET/gera_mapas_vento_MET.py`, `gera_matriz_vento_MET.py` — vento AUT.
- `classes_MET/gera_mapas_MAN_MET.py`, `gera_matriz_MAN_MET.py` — produtos escalares MAN.
- `classes_MET/gera_mapas_vento_MAN_MET.py`, `gera_matriz_vento_MAN_MET.py` — vento MAN.
- `classes_MET/leitura_dados_grib_MET.py` — seleção de ciclo e leitura dos GRIBs.
- `bash/automatizacao_controle_MET.sh` — orquestrador automático.
- `bash/reqs_MAN_MET.sh`, `classes_MET/executa_reqs_param.py` — fluxo manual.
- `METARpy/METARpy.py`, `METARpy/METARpy_traduzido.py` — coleta/tradução METAR.

---

## Apêndice A — Evidências de código

### A.1 Orientação N-S

```python
# classes_MET/gera_mapas_MET.py:113-118
data, lat, lon = objMET.data(lat1=lats1, lat2=lats2, lon1=lons1, lon2=lons2)
if flag == 2:
    lon = lon - 360
lon = lon[0, :]
lat = lat[:, 0]
lat = lat[::-1]
```

O mesmo padrão aparece em `gera_matriz_MET.py`, `gera_mapas_MAN_MET.py`, `gera_matriz_MAN_MET.py`, `gera_mapas_vento_MET.py`, `gera_matriz_vento_MET.py`, `gera_mapas_vento_MAN_MET.py` e `gera_matriz_vento_MAN_MET.py`.

### A.2 V recebendo U

```python
# classes_MET/gera_mapas_vento_MET.py:213-216
for nivelQuaseSupe in varNivelProxSupe:
    u_comp = processamento_dados_met_AUT("uSupe", nivelQuaseSupe).define_lista_var_com_altitude()
    v_comp = processamento_dados_met_AUT("uSupe", nivelQuaseSupe).define_lista_var_com_altitude()
    gera_mapas_vento(u_comp, v_comp, lonslats, varRegiaoNome, nivelQuaseSupe)
```

```python
# classes_MET/gera_matriz_vento_MET.py:312-317
for varNivel_sup in varNivelVentoSup:
    u_comp_supe = processamento_dados_met_AUT("uSupe", varNivel_sup).define_lista_var_com_altitude()
    v_comp_supe = processamento_dados_met_AUT("vSupe", varNivel_sup).define_lista_var_com_altitude()

    geraMatriz_Vento_Resu(u_comp_supe, v_comp_supe, lon_lat, varReg, varNivel_sup)
    geraMatriz_Vento_UVT_predi(u_comp_supe, u_comp_supe, t_comp_supe, lon_lat, varReg, varNivel_sup)
```

### A.3 `hMET` de `winds`

```python
# classes_MET/gera_matriz_vento_MET.py:45-49
def converte_altitude(pres):
    p0 = 1013.25
    h_alt = (1 - (pres / p0) ** 0.190284) * 145366.45
    return h_alt
```

```python
# classes_MET/gera_matriz_vento_MET.py:170
hMET = converte_altitude(nivel)
```

O mesmo em `gera_matriz_vento_MAN_MET.py:143` e `:251`.

### A.4 Direção do vento

```python
# classes_MET/gera_matriz_vento_MET.py:40-43
def criaAngMET(data_u, data_v):
    angResult = ((180 / np.pi) * (np.arctan2((-data_u), (-data_v))))
    return angResult
```

### A.5 Ciclo

```python
# classes_MET/leitura_dados_grib_MET.py:85-88
if int(self.prev_ana[i]) <= int(self.hora) <= int(self.prev_ana[j]):
    if os.path.exists(self.prev_ana[i]):
        os.chdir(self.prev_ana[i])
```

### A.6 `chuvaNaoConvec`

```python
# classes_MET/processamento_dados_MET.py:24
"chuvaNaoConvec": ["Total Precipitation", "surface"],
```

### A.7 Chaves METAR com espaço final

```python
# METARpy/METARpy.py:33-35
"id_localidade ": sigla,
"data ": data,
"mensagem_metar ": mens
```

## Estado da Fase 4

A implementacao e a validacao local estao em [12-fase-4-resultados.md](12-fase-4-resultados.md).
O rollout real e o aceite dos consumidores externos ainda estao pendentes.
Os nomes, headers, unidades e o downloader permanecem preservados.
