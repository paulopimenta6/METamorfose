# 05 — Diagnóstico de bugs e recomendações

> **Aviso de uso**: os produtos GFS gerados pelo código **original** (`main`) não devem ser usados como referência geográfica sem antes corrigir **D-01**. Os produtos de vento superficial não devem ser usados sem corrigir **D-02** e **D-03**. Os JSONs METAR históricos marcados como inválidos em **D-07** não devem ser consumidos por parsers estritos; novas execuções já gravam atomicamente.
>
> **Fase 1:** na branch `execucao`, **D-01, D-02, D-03, D-04 e D-12** foram corrigidos e validados com a amostra real. O resultado, os testes T-01–T-05 e o reprocessamento estão em [09-fase-1-resultados.md](09-fase-1-resultados.md).
>
> **Fase 2:** na mesma branch, foram corrigidos **D-05, D-06, D-07, D-08, D-09, D-10, D-13, D-14, D-15, D-17, D-24, D-25, D-27 e D-28** (C-06, C-07 e itens de produtos/CLI/METAR). Os testes T-06–T-12 estão verdes e a validação independente tem 177 verificações. O resultado está em [10-fase-2-resultados.md](10-fase-2-resultados.md). Continuam em aberto apenas os itens da Fase 3 e D-11 (congelado).

## 1. Sumário executivo

A auditoria encontrou **20 achados principais** e **8 achados secundários**:

| Severidade | Quantidade | IDs |
|---|---:|---|
| Crítica | 3 | D-01, D-02, D-03 |
| Alta | 5 | D-04, D-05, D-06, D-07, D-08 |
| Média | 6 | D-09, D-10, D-12, D-13, D-14, D-20 |
| Baixa | 6 | D-11, D-15, D-16, D-17, D-18, D-19 |

### Top 5 riscos

| ID | Risco | Efeito prático | Estado |
|---|---|---|---|
| D-01 | Todas as grades GFS são invertidas no eixo norte-sul | Valores do norte são gravados no sul e vice-versa em PNG e CSV | Corrigido na Fase 1 |
| D-02 | Mapas de vento superficial e matriz do preditor usam U no lugar de V | Vetores e componente V errados; a matriz BlueSky usa o V correto | Corrigido na Fase 1 |
| D-03 | Altura do vento superficial é calculada com a fórmula de pressão | Ventos de 20–80 m viram 55.696–76.487 ft no BlueSky | Corrigido na Fase 1 |
| D-04 | Ciclo GFS errado na primeira hora de 06/12/18 | Produto rotulado `06` pode conter dados de `00`; idem `12`/`06` e `18`/`12` | Corrigido na Fase 1 |
| D-07 | JSONs METAR concatenados sem separador | 12 arquivos do checkout são JSON inválido | Corrigido em novas execuções (Fase 2); acervo antigo permanece |

### Ordem mínima de correção

1. **D-01** antes de qualquer reprocessamento, porque contamina todos os produtos. *(corrigido na Fase 1)*
2. **D-02 e D-03** antes de gerar ou consumir vento superficial. *(corrigidos na Fase 1)*
3. **D-04** antes de comparar produtos entre ciclos ou reprocessar datas. *(corrigido na Fase 1)*
4. **D-07 e D-08** antes de ampliar a série METAR. *(corrigidos na Fase 2)*
5. **D-05 e D-06** para completar os produtos automáticos. *(corrigidos na Fase 2)*
6. **D-09, D-10, D-13, D-14, D-15, D-17, D-24, D-25, D-27 e D-28** também foram tratados na Fase 2; **D-12** foi corrigido junto da Fase 1.

## 2. Método e escopo

### 2.1 O que foi feito

- Leitura integral dos scripts shell e dos módulos Python.
- Verificação de sintaxe shell com `bash -n` em todos os scripts — todos passaram.
- Verificação das dependências Python no ambiente auditado.
- Inventário dos JSONs METAR: contagem, períodos, pares bruto/traduzido e validação JSON.
- Download de uma amostra real do GFS 0.25° do NOMADS (`gfs.t00z.pgrb2.0p25.f000`, 484 MB) e inspeção com `pygrib` 2.1.8.
- Simulação lógica da seleção de ciclo e da aritmética de datas.
- Nenhum arquivo de código-fonte foi alterado.

### 2.2 O que não foi feito

- Não foi executada a geração completa de mapas/matrizes no host de produção.
- Não foi montado `/media/MET/servidor_MET`; o checkout atual não tem os diretórios de dados.
- Não houve consulta ao vivo à NOAA nem execução dos scripts METAR.
- Não houve comparação numérica com uma fonte meteorológica independente; a validação de D-01 foi estrutural e pontual.
- Não houve teste de concorrência, carga ou recuperação de desastre.

### 2.3 Formato das evidências

As referências usam `arquivo:linha`. Quando a evidência é empírica, o comando e a saída relevante são mostrados em bloco de código.

## 3. Tabela consolidada

| ID | Severidade | Achado | Evidência principal | Impacto |
|---|---|---|---|---|
| D-01 | Crítica | Grade GFS invertida no eixo N-S | `gera_mapas_MET.py:113,118`; `gera_matriz_MET.py:81,86`; demais geradores | Todos os produtos GFS com latitude errada |
| D-02 | Crítica | U usado como V no vento superficial | `gera_mapas_vento_MET.py:215`; `gera_matriz_vento_MET.py:317` | Mapas e matriz do preditor errados |
| D-03 | Crítica | Altura do vento superficial calculada como pressão | `gera_matriz_vento_MET.py:170`; `gera_matriz_vento_MAN_MET.py:143,251` | BlueSky com altitude absurda |
| D-04 | Alta | Ciclo anterior usado na primeira hora | `leitura_dados_grib_MET.py:85-87` | Rótulo e dado divergentes |
| D-05 | Alta | Vento superficial e bloco duplicado no-op | `automatizacao_controle_MET.sh:17-18,62-65` | `winds` não é gerado no AUT |
| D-06 | Alta | Umidade superficial ausente | `processamento_dados_MET.py:26,142-159,193-203` | Sem produto; MAN falha |
| D-07 | Alta | Append de JSON sem separador | `METARpy.py:40-41`; `METARpy_traduzido.py:80-81` | 12 JSONs inválidos |
| D-08 | Alta | Timestamp METAR com ano/mês correntes | `METARpy.py:48-50`; `METARpy_traduzido.py:88-90` | Erro na virada do mês |
| D-09 | Média | Intervalo MAN exige mínimo > máximo | `executa_reqs_param.py:78-101` | `min < max` quebra |
| D-10 | Média | Limpeza calcula data errada e não remove tudo | `remove_GRIBS_antigos.sh:9-15,40-42` | Retenção falha |
| D-11 | Baixa | Teste de diretório GFS com caminho absoluto | `goGribV2.sh:37` | Condição enganosa |
| D-12 | Média | Direção do vento não normalizada | `gera_matriz_vento_MET.py:40-43`; `gera_matriz_vento_MAN_MET.py:51-54` | Ângulos negativos |
| D-13 | Média | `chuvaNaoConvec` mapeia precipitação total | `processamento_dados_MET.py:24,181` | Semântica enganosa |
| D-14 | Média | CLI MAN posicional e frágil | `reqs_MAN_MET.sh:166,195,243,288` | Chamadas silenciosamente ignoradas |
| D-15 | Baixa | Matriz MAN escalar gerada duas vezes | `gera_matriz_MAN_MET.py:123-124` | I/O duplicado |
| D-16 | Baixa | Scripts terminam com `exit 1` em sucesso | `automatizacao_controle_MET.sh:75`; `remove_GRIBS_antigos.sh:118` | Código de saída inútil |
| D-17 | Baixa | Checagem `str(nuvem) is not None` sempre verdadeira | `METARpy_traduzido.py:46-49` | Visibilidade classificada errado |
| D-18 | Baixa | Caminho de saída e região sem sanitização | `gera_mapas_MAN_MET.py:193`; `gera_matriz_MAN_MET.py:57` | Arquivos em local inesperado |
| D-19 | Baixa | Artefatos obsoletos e ausência de empacotamento | `controla_env.pyc`, `.swp`, `__pycache__` | Manutenção e reprodutibilidade |
| D-20 | Média | Sem logging, atomicidade, lock ou idempotência | Vários scripts | Falhas silenciosas e dados parciais |

## 4. Achados críticos

### D-01 — Orientação vertical das grades GFS está invertida

**Severidade**: Crítica  
**Status**: Corrigido na Fase 1. `data` e `lat` são invertidos juntos em mapas e matrizes; a primeira linha do CSV é a menor latitude. A validação independente compara os 13 CSVs com `pygrib`.
**Afeta**: mapas e matrizes AUT e MAN, escalares e vento.

#### Evidência

O padrão aparece em todos os geradores: o código extrai `data, lat, lon`, converte `lat` para uma coluna, inverte `lat` com `lat[::-1]`, mas **não inverte `data`**:

```python
# classes_MET/gera_mapas_MET.py:113-118
data, lat, lon = objMET.data(lat1=lats1, lat2=lats2, lon1=lons1, lon2=lons2)
...
lat = lat[:, 0]
lat = lat[::-1]
```

O mesmo padrão está em:

| Arquivo | Linhas |
|---|---|
| `classes_MET/gera_mapas_MET.py` | flag 1/2: 113, 118; flag 3: 126-139, 143-150 |
| `classes_MET/gera_matriz_MET.py` | flag 1/2: 81, 86; flag 3: 95-104, 106-114 |
| `classes_MET/gera_mapas_MAN_MET.py` | flag 1/2: 89, 94; flag 3: 102-115, 120-127 |
| `classes_MET/gera_matriz_MAN_MET.py` | flag 1/2: 62, 67; flag 3: 76-85, 88-95 |
| `classes_MET/gera_mapas_vento_MET.py` | flag 1/2: 81-88; flag 3: 91-104, 106-119 |
| `classes_MET/gera_matriz_vento_MET.py` | flag 1/2: 117-125; flag 3: 134-147, 149-167 |
| `classes_MET/gera_mapas_vento_MAN_MET.py` | mesmo padrão nos três métodos (LC, barb, LCbarb); flag 1/2 em 60-68, 180-187, 290-300 |
| `classes_MET/gera_matriz_vento_MAN_MET.py` | mesmo padrão nos três métodos (vento, bluesky, predi); flag 1/2 em 90-94, 198-202, 291-295 |

A verificação com GFS 0.25° real mostra que `pygrib` devolve a grade de **norte para sul**:

```text
msg: Temperature surface 0
jScansPositively: 0
lat[0,0]= 90.0   lat[-1,0]= -90.0
lon[0,0]= 0.0    lon[0,-1]= 359.75
data[0,0] (north)= 263.9655 K  em lat 90.0
data[-1,0] (south)= 242.4655 K em lat -90.0
```

Ou seja: a primeira linha de `data` corresponde a 90°N. Ao inverter apenas `lat`, a primeira linha do mapa/CSV passa a ser rotulada como 90°S, mas continua contendo o valor de 90°N.

#### Impacto

- Todos os PNGs e CSVs GFS têm os valores associados à latitude errada.
- O erro é silencioso: não há exceção, e o mapa continua visualmente plausível.
- Séries temporais e comparações com estações ficam deslocadas.
- O problema afeta também o fluxo manual e os produtos de vento.
- A matriz do preditor e a matriz BlueSky herdam a inversão.

#### Correção sugerida

Centralizar a normalização em uma função única e usá-la em todos os geradores:

```python
def normaliza_grade(data, lat, lon):
    """Garante lat crescente e data alinhada à lat."""
    lat_1d = lat[:, 0] if lat.ndim == 2 else lat
    if lat_1d[0] > lat_1d[-1]:
        data = data[::-1, :]
        lat = lat[::-1]
    assert data.shape[0] == lat.shape[0]
    assert data.shape[1] == lon.shape[1]
    return data, lat, lon
```

Para o flag 3, normalizar `data_ini`/`data_fim` (e `data_U`/`data_V`) **antes** de concatenar. Para vento, aplicar a mesma normalização a U e V com a mesma máscara.

Não basta “deixar o Basemap resolver”: os CSVs também estão errados e são consumidos diretamente.

#### Teste de aceitação

- Ler o mesmo GFS com `pygrib` e comparar o valor de um ponto conhecido (ex.: latitude -10) com a linha correspondente do CSV.
- Verificar que a primeira linha do CSV tem a menor latitude da caixa e que o valor bate com `data[-1, :]` do GRIB.
- Verificar que o mapa não está espelhado verticalmente em relação a um campo conhecido (ex.: temperatura).

---

### D-02 — Componente V do vento superficial recebe U

**Severidade**: Crítica  
**Status**: Corrigido na Fase 1. O mapa superficial AUT e o preditor usam `vSupe`; a matriz BlueSky já usava o V correto. A resultante e o `angMET` foram validados.
**Afeta**: mapas de vento superficial AUT e matriz do preditor AUT; a matriz BlueSky AUT e o fluxo MAN usam V corretamente.

#### Evidência

No mapa automático, as duas componentes são lidas de `uSupe`:

```python
# classes_MET/gera_mapas_vento_MET.py:213-216
for nivelQuaseSupe in varNivelProxSupe:
    u_comp = processamento_dados_met_AUT("uSupe", nivelQuaseSupe).define_lista_var_com_altitude()
    v_comp = processamento_dados_met_AUT("uSupe", nivelQuaseSupe).define_lista_var_com_altitude()
    gera_mapas_vento(u_comp, v_comp, lonslats, varRegiaoNome, nivelQuaseSupe)
```

Na matriz do preditor, o segundo argumento também é `u_comp_supe`:

```python
# classes_MET/gera_matriz_vento_MET.py:312-317
for varNivel_sup in varNivelVentoSup:
    u_comp_supe = processamento_dados_met_AUT("uSupe", varNivel_sup).define_lista_var_com_altitude()
    v_comp_supe = processamento_dados_met_AUT("vSupe", varNivel_sup).define_lista_var_com_altitude()

    geraMatriz_Vento_Resu(u_comp_supe, v_comp_supe, lon_lat, varReg, varNivel_sup)
    geraMatriz_Vento_UVT_predi(u_comp_supe, u_comp_supe, t_comp_supe, lon_lat, varReg, varNivel_sup)
```

Observação importante:

- `geraMatriz_Vento_Resu` (BlueSky, linha 316) recebe `v_comp_supe` **correto**.
- `geraMatriz_Vento_UVT_predi` (preditor, linha 317) recebe `u_comp_supe` duas vezes.
- O fluxo MAN está correto: `gera_mapas_vento_MAN_MET.py:417-418` e `gera_matriz_vento_MAN_MET.py:392-393` usam `uSupe` e `vSupe`.

#### Impacto

- Mapas de vento superficial mostram direção e velocidade erradas.
- Na matriz do preditor, a coluna `vento V` contém U.
- Para um escoamento puramente zonal (`U=10`, `V=0`), o produto atual mostra `V=10` e uma resultante `sqrt(10²+10²)=14,14` em vez de 10.
- A matriz BlueSky não é afetada por este bug específico, mas herda D-03.

#### Correção sugerida

```python
v_comp = processamento_dados_met_AUT("vSupe", nivelQuaseSupe).define_lista_var_com_altitude()
```

e:

```python
geraMatriz_Vento_UVT_predi(u_comp_supe, v_comp_supe, t_comp_supe, lon_lat, varReg, varNivel_sup)
```

Adicionar um teste com `U=10, V=0` e verificar que a coluna V é zero e que a resultante é 10 (ou 19,43 kt no BlueSky).

#### Teste de aceitação

- Gerar um caso sintético com U constante e V nulo.
- Verificar `vento V == 0` na matriz do preditor.
- Verificar que mapas de barbs/streamplot apontam para a direção correta.

---

### D-03 — Altura do vento superficial é calculada como pressão

**Severidade**: Crítica  
**Status**: Corrigido na Fase 1. `hMET`/`halt` de `winds` usa `metros × 3,28084`; 20 m → 65,6168 ft e 80 m → 262,4672 ft. A fórmula de pressão continua apenas para `wind`.
**Afeta**: matriz BlueSky AUT e MAN; matriz simples MAN.

#### Evidência

`converte_altitude` implementa a fórmula barométrica e espera pressão em hPa:

```python
# classes_MET/gera_matriz_vento_MET.py:45-49
def converte_altitude(pres):
    p0 = 1013.25
    h_alt = (1 - (pres/p0)**0.190284) * 145366.45
    return h_alt
```

Para `winds`, porém, `nivel` é uma altura em metros (20, 30, 40, 50, 80). O código passa esse valor diretamente:

```python
# classes_MET/gera_matriz_vento_MET.py:170
hMET = converte_altitude(nivel)
```

O mesmo ocorre em `classes_MET/gera_matriz_vento_MAN_MET.py:143` e `:251`.

Resultado numérico:

| Altura real | `hMET` atual (ft) | `hMET` correto (ft) |
|---:|---:|---:|
| 20 m | 76.487,0 | 65,6 |
| 30 m | 70.962,3 | 98,4 |
| 40 m | 66.775,8 | 131,2 |
| 50 m | 63.366,9 | 164,0 |
| 80 m | 55.695,5 | 262,5 |

#### Impacto

- O BlueSky recebe vento de 20–80 m como se estivesse a 55.696–76.487 ft.
- A matriz simples MAN rotula `nivel<hPa>` e grava metros; o `halt` fica absurdo.
- A matriz do preditor não tem `hMET`, então não é afetada por este cálculo específico.
- Para `wind` em pressão, a conversão está correta.

#### Correção sugerida

```python
def calcula_hmet(nivel, eh_vento_superficie):
    if eh_vento_superficie:
        return float(nivel) * 3.28084
    return converte_altitude(nivel)
```

Corrigir também o header da matriz MAN, que hoje é fixo:

```text
# winds
nivel<m>,halt<feet>,...
# wind
nivel<hPa>,halt<feet>,...
```

E documentar que `halt` de `wind` é uma altitude aproximada derivada da pressão, não a altura geométrica real.

#### Teste de aceitação

- 20 m → 65,6 ft; 80 m → 262,5 ft (tolerância de 0,1 ft).
- Nenhum `hMET` de `winds` acima de 1.000 ft.
- Para `wind` em 500 hPa, o valor continua sendo a conversão barométrica esperada.

## 5. Achados de severidade alta

### D-04 — Ciclo GFS anterior é usado na primeira hora de cada ciclo

**Severidade**: Alta  
**Status**: Corrigido na Fase 1. A seleção usa intervalo semiaberto e caminho absoluto; 06:00 usa o ciclo 06, 12:00 usa 12 e 18:00 usa 18.

#### Evidência

```python
# classes_MET/leitura_dados_grib_MET.py:85-88
if int(self.prev_ana[i]) <= int(self.hora) <= int(self.prev_ana[j]):
    if os.path.exists(self.prev_ana[i]):
        os.chdir(self.prev_ana[i])
```

Há dois problemas combinados:

1. A comparação é inclusiva nos dois extremos (`<=`).
2. `os.chdir` é relativo. Depois de entrar em `00`, a verificação `os.path.exists("06")` é feita **dentro de `00`**, não na raiz da data.

O rótulo de saída é calculado separadamente e usa a comparação correta (`06 <= hora < 12`), como em `gera_mapas_MET.py:69-76` e `gera_matriz_MET.py:35-42`.

| Hora local | Ciclo usado | Rótulo do produto | Situação |
|---|---|---|---|
| 00:00–00:59 | 00 | 00 | Correto |
| 01:00–05:59 | 00 | 00 | Correto |
| 06:00–06:59 | 00 | 06 | **Divergente** |
| 07:00–11:59 | 06 | 06 | Correto |
| 12:00–12:59 | 06 | 12 | **Divergente** |
| 13:00–17:59 | 12 | 12 | Correto |
| 18:00–18:59 | 12 | 18 | **Divergente** |
| 19:00–23:59 | 18 | 18 | Correto |

#### Impacto

- Produto rotulado `06` pode conter dados de `00`.
- Comparações entre execuções e validações por rótulo ficam inválidas.
- A primeira hora de cada ciclo é justamente a janela em que usuários costumam consultar o produto novo.
- O bug é intermitente e difícil de perceber sem inspecionar o GRIB.

#### Correção sugerida

Não usar `os.chdir` relativo para navegar entre ciclos. Montar caminhos absolutos:

```python
base = os.path.join(dir_gribs, ano + mes + dia)
hora_int = int(hora)
ciclo = max(c for c in (0, 6, 12, 18) if c <= hora_int)
ciclo_dir = os.path.join(base, f"{ciclo:02d}")
```

Trocar a comparação por intervalos semiabertos (`inicio <= hora < fim`) e usar `os.path.isdir` com caminho absoluto. Se o ciclo ainda não existir, usar explicitamente o anterior **com o rótulo anterior**, ou falhar com mensagem clara; nunca rotular o ciclo anterior como se fosse o novo.

#### Teste de aceitação

Parametrizar a função de seleção para 00:00, 05:59, 06:00, 06:59, 07:00, 11:59, 12:00, 12:59, 13:00, 17:59, 18:00, 18:59, 19:00 e 23:59, verificando o ciclo esperado.

---

### D-05 — Vento superficial e bloco duplicado do controlador são no-op

**Severidade**: Alta  
**Status**: Corrigido na Fase 2 (C-07). O controlador chama `winds -ns` para SP/RJ, o bloco duplicado de 1000/200 foi removido e os wrappers validam `-v`/`-n`/`-ns`.

#### Evidência

O controlador chama:

```bash
# bash/automatizacao_controle_MET.sh:17-18
./automatiza_vento_MET.sh "-v" "winds" "-r" "SP"
./automatiza_vento_MET.sh "-v" "winds" "-r" "RJ"

# bash/automatizacao_controle_MET.sh:20-24
./automatiza_vento_MET.sh "-v" "wind" "-n" "1000" "-r" "SP"
./automatiza_vento_MET.sh "-v" "wind" "-n" "1000" "-r" "RJ"
./automatiza_vento_MET.sh "-v" "wind" "-n" "200" "-r" "SP"
./automatiza_vento_MET.sh "-v" "wind" "-n" "200" "-r" "RJ"

# bash/automatizacao_controle_MET.sh:62-65
./automatiza_vento_MET.sh "-n" "1000" "-r" "SP"
./automatiza_vento_MET.sh "-n" "200" "-r" "SP"
./automatiza_vento_MET.sh "-n" "1000" "-r" "RJ"
./automatiza_vento_MET.sh "-n" "200" "-r" "RJ"
```

O wrapper só executa se `-v` estiver na posição 1 e `-n`/`-ns` na posição 3 (`bash/automatiza_vento_MET.sh:28-54`).

| Linhas | Chamada | Efeito |
|---|---|---|
| 17-18 | `winds -r` | **Nenhum** — falta `-ns` |
| 20-24 | `wind -n 1000/200 -r` | **Gera** mapas/matrizes em pressão |
| 62-65 | `-n 1000/200 -r` | **Nenhum** — falta `-v` |

#### Impacto

- O produto de vento superficial (`winds`) nunca é gerado pelo controlador.
- As linhas 62-65 são chamadas duplicadas inúteis.
- O usuário pode concluir erroneamente que “o vento automático não funciona”, quando os níveis de pressão funcionam.
- D-02 e D-03 ficam latentes até alguém chamar `winds` manualmente ou corrigir o controlador.

#### Correção sugerida

```bash
./automatiza_vento_MET.sh -v winds -ns -r SP
./automatiza_vento_MET.sh -v winds -ns -r RJ
```

e remover as linhas 62-65, que duplicam 20-24. Se a intenção era gerar outro conjunto, corrigi-las com `-v`:

```bash
./automatiza_vento_MET.sh -v wind -n 1000 -r SP
./automatiza_vento_MET.sh -v wind -n 200 -r SP
./automatiza_vento_MET.sh -v wind -n 1000 -r RJ
./automatiza_vento_MET.sh -v wind -n 200 -r RJ
```

Adicionar `set -euo pipefail` e validar no wrapper que `-v` e `-n`/`-ns` estão presentes, com mensagem de erro explícita.

#### Teste de aceitação

Executar o controlador em ambiente de teste e verificar que existem arquivos `CampoVento` em `mapasGrib/...` e matrizes em `matrizGrib/bluesky`/`predi` para `winds`.

---

### D-06 — Umidade relativa superficial não gera saída e quebra no MAN

**Severidade**: Alta  
**Status**: Corrigido na Fase 2 (C-06). O controlador usa `umidadeRel -n 850`; o AUT/MAN validam o tipo de nível e `-ns` retorna erro claro com sugestão de `-n 850`, sem `AttributeError`. O mapa preserva o nível `N850` no nome do produto; o gerador não força mais `Nsuperficie` para `umidadeRel`.

#### Evidência

O mapeamento é fixo para `isobaricInhPa`:

```python
# classes_MET/processamento_dados_MET.py:26
"umidadeRel": ["Relative humidity", "isobaricInhPa"],
```

No AUT, `define_lista_var_com_nivel_superficie` só considera `surface`/`meanSea` (`:142-159`). Para `umidadeRel` com `-ns`, a lista fica vazia e nenhum arquivo é gerado.

No MAN, `define_var_com_nivel_ou_superficie` (`:193-203`) só define `self.var_met_com_nivel` se o tipo for `surface`/`meanSea`. Para `umidadeRel` com `-ns`, o atributo não é criado e o acesso em `:209` levanta `AttributeError`.

O controlador chama `umidadeRel -ns` em `automatizacao_controle_MET.sh:52` e `:57`.

#### Impacto

- Não há produto de umidade relativa superficial.
- A chamada do controlador “passa” sem gerar arquivo, o que mascara a falha.
- No MAN, o usuário recebe um traceback em vez de mensagem de erro.

#### Correção sugerida

Separar a chave de superfície:

```python
"umidadeRelSuperficie": ["2 metre relative humidity", "heightAboveGround"],
```

e tratar `heightAboveGround` no seletor de superfície (ou usar um mapa por tipo de nível). Alternativamente, calcular a umidade a partir de temperatura e ponto de orvalho, documentando a fórmula.

No MAN, lançar erro claro:

```python
raise ValueError("umidadeRel não possui campo em superfície; use -n <hPa> ou uma variável de superfície")
```

#### Teste de aceitação

- `umidadeRel -ns` gera CSV/PNG com valores entre 0 e 100.
- `umidadeRel -n 850` continua funcionando.
- MAN com `-ns` retorna mensagem clara, não traceback.

---

### D-07 — JSONs METAR são concatenados sem separador

**Severidade**: Alta  
**Status**: Corrigido na Fase 2. A escrita usa `"w"` em arquivo `.tmp`, `flush`/`fsync` e `os.replace`; reexecuções sobrescrevem a mesma estação + timestamp. Os 12 arquivos históricos inválidos permanecem no acervo e precisam de reparo/descarte conforme o consumidor.

#### Evidência

```python
# METARpy/METARpy.py:40-41
arquivo = open(sigla + data + ".json", "a")
arquivo.write(y)
```

```python
# METARpy/METARpy_traduzido.py:80-81
arquivo = open(sigla + data + "_traduzido.json", "a")
arquivo.write(x)
```

Se o mesmo arquivo for aberto duas vezes, dois objetos JSON completos são concatenados sem nova linha, vírgula ou array. O resultado não é JSON válido.

O inventário encontrou **12 arquivos inválidos**, incluindo:

```text
METARpy/20220201/SBBE202202010300.json
METARpy/20220201/SBBE202202010300_traduzido.json
METARpy/20221125/SBBE202211250300.json
METARpy/20221125/SBBE202211250300_traduzido.json
METARpy/20210815/SBCF202108150300.json
METARpy/20210815/SBCF202108150300_traduzido.json
METARpy/20210719/SBPA202107190300.json
METARpy/20210719/SBPA202107190300_traduzido.json
METARpy/20221010/SBRF202210100300.json
METARpy/20221010/SBRF202210100300_traduzido.json
METARpy/20211219/SBBE202112190300.json
METARpy/20211219/SBBE202112190300_traduzido.json
```

#### Impacto

- Consumidores que usam `json.load` falham.
- O arquivo cresce indefinidamente e mistura observações.
- A falha é silenciosa no momento da escrita.

#### Correção sugerida

- Usar `"w"` para sobrescrever a observação daquele timestamp, ou JSON Lines (`uma linha = um objeto`) para histórico.
- Escrever em arquivo temporário e renomear atomicamente (`os.replace`).
- Deduplicar por estação + timestamp antes de gravar.
- Validar com `json.load` após a escrita e falhar se inválido.
- Separar claramente bruto e traduzido; não reutilizar o mesmo nome.

#### Teste de aceitação

- Rodar duas vezes no mesmo minuto e verificar que o arquivo continua válido.
- Validar todos os JSONs com `json.load`.
- Verificar que não há dois objetos na mesma linha.

---

### D-08 — Timestamp METAR usa ano/mês correntes

**Severidade**: Alta  
**Status**: Corrigido na Fase 2. `resolve_data_metar` usa uma referência UTC única (`METAR_REFERENCIA_UTC`, ou `date -u`) e resolve o rollover de mês/ano; o diretório usa a mesma referência.

#### Evidência

```python
# METARpy/METARpy.py:48-50
dataMETAR = codMetar.imprime_data()
dataPy = datetime.now().strftime("%Y%m")
data = dataPy + dataMETAR[0] + dataMETAR[1] + dataMETAR[2]
```

O mesmo em `METARpy_traduzido.py:88-90`.

O METAR informa dia, hora e minuto (UTC), mas **não informa ano/mês**. O código combina esses campos com o ano/mês do relógio local.

#### Impacto

- Na virada do mês, uma observação do dia 31 pode ser gravada com o mês seguinte.
- Na virada do ano, o ano pode ficar errado.
- O diretório (`automatizaMetar.sh`) usa data local; o timestamp usa outra referência. Há mistura de fuso.
- Observações do mesmo evento podem aparecer em arquivos diferentes.

#### Correção sugerida

Construir o timestamp com um instante de referência em UTC e resolver o rollover:

```python
from datetime import datetime, timezone

def resolve_metar(agora, dia, hora, minuto):
    for meses_atras in (0, 1):
        ano, mes = agora.year, agora.month - meses_atras
        if mes < 1:
            ano, mes = ano - 1, mes + 12
        try:
            ref = datetime(ano, mes, dia, hora, minuto, tzinfo=timezone.utc)
        except ValueError:
            continue  # dia não existe nesse mês
        if ref <= agora:
            return ref
    raise ValueError("timestamp METAR fora da janela esperada")

agora = datetime.now(timezone.utc)
dia, hora, minuto = int(dataMETAR[0]), int(dataMETAR[1]), int(dataMETAR[2])
ref = resolve_metar(agora, dia, hora, minuto)
```

O exemplo acima cobre a virada de mês sem `replace(day=31)` em um mês de 30 dias. Se a defasagem puder passar de um mês, ampliar a janela e registrar a decisão.

Idealmente, usar o timestamp completo fornecido pela biblioteca, se disponível, e gravar ISO 8601 em UTC.

#### Teste de aceitação

- Simular 2022-03-01 00:05 UTC com METAR do dia 28/02 e verificar que o arquivo é `20220228...`.
- Simular 2023-01-01 com METAR do dia 31/12 e verificar `20221231...`.
- Verificar que o diretório e o timestamp usam a mesma referência.

## 6. Achados de severidade média

### D-09 — Intervalo MAN exige mínimo maior que máximo

**Severidade**: Média  
**Status**: Corrigido na Fase 2. `cria_intervalo_niveis` ordena os índices, aceita `200→500` e `500→200`, devolve sempre níveis crescentes e rejeita extremos fora de 150–1000 hPa com código 2.

#### Evidência

```python
# classes_MET/executa_reqs_param.py:78-101
if nivelmin > nivelmax:
    ...
    if nivelmin in niveis:
        idx_nivel_min = niveis.index(nivelmin)
    if nivelmax in niveis:
        idx_nivel_max = niveis.index(nivelmax)

for i in range(idx_nivel_max, idx_nivel_min + 1):
    niveis_return.append(niveis[i])
```

Se `nivelmin < nivelmax` (ordem natural), o bloco `if` não é executado, `idx_nivel_min`/`idx_nivel_max` não existem e a linha 97 levanta `UnboundLocalError`.

#### Impacto

- A documentação e o help sugerem `min` e `max` na ordem natural, mas o código só funciona invertido.
- Usuários recebem traceback em vez de uma lista de níveis.
- O fluxo manual de intervalo fica frágil.

#### Correção sugerida

```python
if nivelmin not in niveis or nivelmax not in niveis:
    raise ValueError("nível fora da lista suportada")
i0, i1 = sorted((niveis.index(nivelmin), niveis.index(nivelmax)))
return niveis[i0:i1 + 1]
```

Aceitar as duas ordens e documentar que o resultado é sempre crescente.

#### Teste de aceitação

- `500→200` e `200→500` produzem a mesma lista.
- Níveis iguais produzem um único elemento.
- Nível fora da lista retorna erro claro.

---

### D-10 — Limpeza calcula a data errada e não remove todas as resoluções

**Severidade**: Média  
**Status**: Corrigido na Fase 2. A data alvo é `date -d "-2 days" +"%Y%m%d"`; o script remove `0p25`, `1p00`, legados e os diretórios de produtos do dia, com validação de formato e de calendário (`20260231` e `20260229` retornam 2) e retorno 0. Overrides `MET_BASE_DIR`/`MET_HOJE`/`MET_DATA_ALVO` permitem teste seguro.

#### Evidência

```bash
# remove_GRIBS_antigos.sh:9-15
data_ano=`date +"%Y"`
data_mes=`date +"%m"`
data_dia_anterior=`date -d "-2 days" +"%d"`
data_final_anterior=${data_ano}${data_mes}${data_dia_anterior}
```

O dia vem de “-2 days”, mas o ano/mês vêm de **hoje**. Nos dois primeiros dias do mês, a data formada aponta para o mês corrente (futuro) ou para um dia inexistente.

Exemplo em 01/11/2026:

```text
ano=2026, mes=11, dia_anterior=30
data_final_anterior=20261130  (30/11/2026, futuro)
```

A limpeza não remove os dados de 30/10.

Além disso, o script remove apenas `gfs.tCCz.pgrb2.0p25.f0FF` (`:40-42`); os arquivos `1p00` e legados permanecem.

#### Impacto

- Retenção maior que a planejada; disco pode encher.
- Nenhum dado é removido nos primeiros dias do mês.
- Resoluções alternativas acumulam indefinidamente.
- O `exit 1` no final (`:118`) atrapalha automação.

#### Correção sugerida

```bash
data_final_anterior=$(date -d "-2 days" +"%Y%m%d")
```

Remover também `1p00` e o padrão legado, com `find` e `-maxdepth`. Usar `set -euo pipefail` e retornar 0 em sucesso.

#### Teste de aceitação

- Simular 01/03, 02/03 e 15/03 e verificar que a data alvo é sempre `hoje - 2 dias`.
- Verificar que `0p25`, `1p00` e legados do dia alvo são removidos.
- Verificar que dados de outros dias não são tocados.

---

### D-12 — Direção do vento não é normalizada para 0–360

**Severidade**: Média  
**Status**: Corrigido na Fase 1. `angMET` é normalizado para `[0, 360)` em mapas e matrizes, incluindo os quadrantes negativos.

#### Evidência

```python
# classes_MET/gera_matriz_vento_MET.py:40-43
def criaAngMET(data_u, data_v):
    angResult = ((180/np.pi) * (np.arctan2((-data_u), (-data_v))))
    return angResult
```

O mesmo em `gera_matriz_vento_MAN_MET.py:51-54`. `arctan2` retorna `[-180, 180]`.

Exemplo: `U=10`, `V=0` → `-90°`. O valor equivalente em 0–360 é `270°`.

#### Impacto

- A matriz BlueSky e a matriz simples do MAN podem receber ângulos negativos; a matriz do preditor não inclui direção.
- Dependendo do consumidor, `-90` pode ser interpretado como 90 ou como valor inválido.
- Séries de direção ficam descontínuas na passagem de 180→-180.

#### Correção sugerida

```python
angResult = (np.degrees(np.arctan2(-data_u, -data_v)) + 360.0) % 360.0
```

Documentar a convenção (direção de onde o vento vem) e testar os quatro quadrantes.

#### Teste de aceitação

- `U=10, V=0` → 270°.
- `U=-10, V=0` → 90°.
- `U=0, V=10` → 180°.
- `U=0, V=-10` → 0°.
- Todos os valores em `[0, 360)`.

---

### D-13 — `chuvaNaoConvec` mapeia precipitação total

**Severidade**: Média  
**Status**: Documentado na Fase 2 sem renomear. `chuvaNaoConvec` continua sendo precipitação total (convectiva + estratiforme); o nome, o seletor e os produtos foram preservados. A semântica está em `docs/03` e `docs/08`.

#### Evidência

```python
# classes_MET/processamento_dados_MET.py:24
"chuvaNaoConvec": ["Total Precipitation", "surface"],
```

O mesmo em `:181` no dicionário MAN.

#### Impacto

- O nome sugere “precipitação não convectiva”, mas o campo é a precipitação total.
- Quem consome `chuvaNaoConvec` esperando chuva estratiforme recebe um valor que inclui a convectiva.
- Relatórios e séries podem superestimar a chuva não convectiva.
- A unidade é kg m⁻² (numericamente equivalente a mm), mas o intervalo de acumulação não está documentado no produto.

#### Correção sugerida

- Renomear para `chuvaTotal` (com alias temporário para `chuvaNaoConvec`).
- Se houver campo real de precipitação não convectiva no GFS, mapear corretamente.
- Documentar a unidade (kg m⁻² ≈ mm) e o intervalo de acumulação.

#### Teste de aceitação

- Comparar `chuvaTotal` com a soma de `chuvaConvec` + `chuvaNaoConvec` real, se disponível.
- Verificar que o help e os nomes dos arquivos usam o termo correto.

---

### D-14 — CLI manual é posicional, duplica argumento e falha silenciosamente

**Severidade**: Média  
**Status**: Corrigido na Fase 2. O shell virou um wrapper fino e o Python usa `argparse`: flags em qualquer ordem, sem `${4}` duplicado, validação de variável/coordenadas/data/nível/saída e código 2 para chamadas inválidas.

#### Evidência

O wrapper chama o Python com `${4}` duas vezes:

```bash
# bash/reqs_MAN_MET.sh:166, 195, 243, 288
python3 ${dir_executa_reqs} ${1} ${2} ${3} ${4} ${4} ${5} ...
```

As flags precisam estar em posições fixas. Se a ordem mudar, o wrapper pode não chamar o Python e **sair com sucesso** (por exemplo, sem nível, ou com `-ns` fora da posição 11).

O help também é inconsistente:

- cita `-v chuva`, que não existe no dicionário;
- diz que nível vazio é superfície, mas o wrapper exige `-ns`;
- exemplos usam `-datetime` de 12 dígitos sem explicar o formato.

#### Impacto

- Chamadas erradas não geram saída e não retornam erro.
- O argumento duplicado desloca posições; o parser atual encontra flags por nome, mas a lógica é frágil.
- Usuários perdem tempo depurando “nada aconteceu”.

#### Correção sugerida

- Substituir o shell posicional por `argparse` no Python (ou `getopt` no shell).
- Remover o `${4}` duplicado.
- Validar data, polígono, nível, variável e diretório de saída.
- Retornar código de erro não zero em qualquer falha.
- Atualizar o help para as variáveis reais.

#### Teste de aceitação

- Uma matriz de chamadas válidas e inválidas deve produzir sucesso ou erro claro, nunca silêncio.
- `-v chuva` deve retornar “variável desconhecida; use chuvaConvec/chuvaNaoConvec”.
- `-out` sem barra deve ser rejeitado ou normalizado.

---

### D-20 — Falta de logging, atomicidade, lock e idempotência

**Severidade**: Média  
**Status**: Confirmado por inspeção.

#### Evidência

- A maioria dos scripts usa `print` e deixa exceções subirem.
- O controlador sempre termina com `exit 1` (`automatizacao_controle_MET.sh:75`).
- A limpeza também termina com `exit 1` (`remove_GRIBS_antigos.sh:118`).
- Não há `flock`, lockfile, transação, arquivo de manifesto ou retry.
- Escritas de CSV/JSON são feitas diretamente no arquivo final.
- Não há logs estruturados, métricas ou correlação por execução.

#### Impacto

- Falhas parciais são difíceis de detectar.
- Uma execução interrompida pode deixar CSV/JSON truncado.
- Duas execuções simultâneas podem sobrescrever arquivos.
- Não há como saber qual ciclo/resolução foi usado sem abrir o GRIB.
- O código de saída não é confiável.

#### Correção sugerida

- Criar um `run_id` (timestamp + ciclo) e um manifesto JSON por execução.
- Registrar em log: data, ciclo, resolução por arquivo, variável, nível, região, número de mensagens, caminho de saída e duração.
- Escrever em `.tmp` e renomear atomicamente.
- Usar `flock -n` no controlador.
- Retornar códigos de saída reais (0 sucesso, ≠0 falha).
- Adicionar validação pós-escrita (linhas do CSV, JSON válido, PNG não vazio).

#### Teste de aceitação

- Interromper uma execução e verificar que não há arquivo final truncado.
- Rodar duas instâncias e verificar que a segunda não corrompe a primeira.
- Verificar que o log permite reconstruir o ciclo e a resolução usados.

## 7. Achados de severidade baixa

### D-11 — Teste de existência do diretório GFS usa caminho absoluto

**Evidência**: `goGribV2.sh:37` faz `if test -d /${data_completa}`. O script já está em `gribs/` e deveria testar `./${data_completa}` ou `${dir}/${data_completa}`.

**Impacto**: Na prática, o teste quase sempre é falso; o script tenta `mkdir` de um diretório que pode já existir. Sem `set -e`, o erro de `mkdir` é ignorado e o `cd` seguinte funciona. Se existir um diretório com o mesmo nome na raiz, o `cd` pode ir para o lugar errado.

**Correção**: `if test -d "${dir}/${data_completa}"` ou `if test -d "./${data_completa}"`.

---

### D-15 — Matriz MAN escalar é gerada duas vezes

**Status**: Corrigido na Fase 2. A chamada duplicada foi removida; o schema e o nome do arquivo não mudaram.

**Evidência**: `gera_matriz_MAN_MET.py:123-124` chamava `self.gera_matriz(...)` duas vezes consecutivas.

**Impacto**: I/O duplicado, tempo de execução maior e possibilidade de confusão em logs. O resultado final é o mesmo porque o segundo `open(..., 'w')` sobrescreve.

**Correção**: Remover uma das chamadas.

---

### D-16 — Scripts terminam com `exit 1` mesmo em sucesso

**Evidência**:

- `automatizacao_controle_MET.sh:75`
- `remove_GRIBS_antigos.sh:118`

**Impacto**: Cron/systemd interpretam a execução como falha; alertas falsos; impossibilidade de usar o código de saída para decidir retry.

**Correção**: `exit 0` no fim ou, melhor, propagar o primeiro erro real e retornar 0 apenas em sucesso completo.

---

### D-17 — Checagem `str(nuvem) is not None` é sempre verdadeira

**Status**: Corrigido na Fase 2. A classificação usa `nuvem is not None`/`nuvem is None`; `9999` sem nuvem vira `"10000"` e com nuvem vira `"superior a 10000"`.

**Evidência**:

```python
# METARpy/METARpy_traduzido.py:46-49
if str(autoOunao) == "False" and str(nuvem) is not None and str(visibilidade) == "9999":
    return "superior a 10000"
elif str(autoOunao) == "False" and str(nuvem) is None and str(visibilidade) == "9999":
    return "10000"
```

`str(x)` nunca é `None`; é uma string (`"None"` no pior caso). O segundo ramo é inalcançável.

**Impacto**: Visibilidade `9999` com estação automática e sem nuvem é classificada como “superior a 10000” em vez de “10000”. É uma diferença semântica pequena, mas o código não faz o que aparenta.

**Correção**: Usar `nuvem is not None` e `nuvem is None`, ou comparar com o sentinela real (`"informacao ausente"`).

---

### D-18 — Caminho de saída e nome de região sem sanitização

**Evidência**:

- `gera_mapas_MAN_MET.py:193` e `gera_matriz_MAN_MET.py:57` concatenam `saida + nome`.
- `saida` vem de `-out` sem validação; se não terminar em `/`, o arquivo é criado com prefixo errado.
- `regiao` no MAN é `LonMin:<...> LonMax:<...> ...`, com espaços e dois-pontos.
- O diretório não é criado pelo código.

**Impacto**: Arquivos em locais inesperados; nomes difíceis de usar em shell; falha se o diretório não existir.

**Correção**: Usar `pathlib.Path`, exigir que `-out` seja um diretório existente, normalizar com `os.path.join` e sanitizar a região para o nome do arquivo (ou usar um ID curto).

---

### D-19 — Artefatos obsoletos e ausência de empacotamento

**Evidência**:

- `classes_MET/controla_env.pyc` (bytecode antigo, Python 2.7).
- `classes_MET/.gera_mapas_vento_MAN_MET.py.swp` e `classes_MET/.processamento_dados_MET.py.swp`.
- Vários `__pycache__` de Python 3.5/3.7/3.8.
- `METARpy` ocupa aproximadamente 71 MB, com dois vendors.
- Não há `requirements.txt`, `pyproject.toml`, testes, lint, CI ou Git.

**Impacto**: Dificulta reproduzir o ambiente, aumenta o repositório e cria risco de importar bytecode/arquivo errado.

**Correção**: Remover artefatos, adicionar `requirements.txt` com versões, separar vendor, inicializar Git e adicionar testes.

## 8. Achados secundários

| ID | Severidade | Achado | Evidência | Impacto | Correção |
|---|---|---|---|---|---|
| D-21 | Baixa | `ponto_regiao` usa latitude em condições de longitude e faz wrap incompleto | `ponto_regiao_MET.py:27,33,36-37` | Caixas erradas perto de 0°/180° | Validar faixa e usar aritmética modular |
| D-22 | Baixa | `gera_mapas_MET.py` usa `varMET` global no ramo de chuva | `gera_mapas_MET.py:102` | Funciona hoje, mas quebra se a função for chamada com outro nome | Usar `variavelMET` |
| D-23 | Baixa | `controla_env` usa `os.mkdir` e `os.chdir` global | `controla_env.py:35,64-82,89-107` | Não é thread-safe; falha se o diretório pai não existir | `pathlib`, `mkdir(parents=True, exist_ok=True)` |
| D-24 | Baixa | Precipitação `f000` é rotulada como `06` | `gera_mapas_MET.py:102-109`; `gera_matriz_MET.py:67-74` | Confusão entre análise e previsão | **Fase 2:** documentado; sufixo `+6` mantido, sem renomear |
| D-25 | Baixa | `automatizaMetar.sh` usa variáveis indefinidas | `automatizaMetar.sh:7` (`data_hora`, `data_min`) | Diretório só com data; execuções do dia compartilham pasta | **Fase 2:** referência UTC única; variáveis indefinidas removidas |
| D-26 | Baixa | Figuras e GRIBs não são fechados explicitamente | `gera_mapas_MET.py:216`; `leitura_dados_grib_MET.py:113` | Consumo de memória/file descriptors em lote | `plt.close(fig)` e `with pygrib.open(...)` (Fase 3) |
| D-27 | Baixa | `temps` usa `Temperature`/`surface` (skin), não `2 metre temperature` | `processamento_dados_MET.py:22`; GFS tem `2 metre temperature` em `heightAboveGround` 2 | Temperatura de “superfície” pode não ser a do ar a 2 m | **Fase 2:** documentado como pele; seletor e nome mantidos |
| D-28 | Baixa | Shell sem `set -euo pipefail` e help inconsistente | `automatiza_MET.sh:28`; `reqs_MAN_MET.sh:14-27` | Falhas silenciosas; `-v chuva` e `MN` não existem | **Fase 2:** `set -euo pipefail`, validação, faixa 150–1000, help e erros claros; `chuva`/`MN` rejeitados |

### Notas sobre os secundários

- **D-21**: em `verifica_longitude`, as condições usam `self.latitude` (`:27` e `:33`), mas deveriam validar apenas a longitude. Para as caixas do Brasil o resultado coincide, mas a lógica está errada. O wrap de 180° também não cobre todos os casos.
- **D-23**: `imprime_dirMapas` e `imprime_dirMatrizes` fazem `chdir` para o diretório de saída. Isso muda o diretório de trabalho do processo inteiro; dois produtos no mesmo processo podem interferir.
- **D-24**: o acréscimo de 6 em `forecastTime` é um rótulo histórico do produto de chuva. A Fase 2 manteve o nome e documentou que `f000` aparece como `_06`; o valor continua sendo o campo de precipitação do GRIB naquele passo.
- **D-27**: em GFS, `Temperature` em `surface` é a temperatura de pele, enquanto `2 metre temperature` é a do ar a 2 m. A Fase 2 manteve o nome `temps` e o seletor, documentando explicitamente a semântica.

## 9. Plano de correção

### Fase 0 — Contenção (0–1 dia)

1. Comunicar que os produtos GFS atuais são suspeitos.
2. Fazer backup de `METARpy/20*` e dos produtos que serão reprocessados.
3. Não executar `remove_GRIBS_antigos.sh` até corrigir D-10.
4. Adicionar um validador JSON e rodar sobre o acervo METAR.
5. Congelar o consumo de vento superficial e de produtos GFS derivados até D-01/D-02/D-03 serem corrigidos.

### Fase 1 — Críticos (2–4 dias)

| Ordem | Achado | Ação | Dependência |
|---:|---|---|---|
| 1 | D-01 | Normalizar grade em todos os geradores | Nenhuma |
| 2 | D-02 | Corrigir V no mapa e no preditor | D-01 |
| 3 | D-03 | Corrigir `hMET` para `winds` | D-01 |

Gerar um conjunto de referência (“golden case”) com um GFS conhecido e comparar pontos antes/depois.

### Fase 2 — Produtos, CLI e METAR (concluída em 27/10/2026)

| Ordem | Achado | Ação | Estado |
|---:|---|---|---|
| 1 | D-04 | Seleção de ciclo por intervalos semiabertos e caminhos absolutos | Antecipado e concluído na Fase 1 |
| 2 | D-05 | Corrigir controlador; gerar `winds` | Concluído (C-07) |
| 3 | D-06 | Corrigir uso de `umidadeRel -ns` | Concluído: `-n 850` e erro claro (C-06) |
| 4 | D-07 | Escrita atômica e sobrescrita | Concluído |
| 5 | D-08 | Timestamp UTC com rollover | Concluído |
| 6 | D-09/D-10/D-13/D-14/D-15/D-17/D-24/D-25/D-27/D-28 | Intervalo, limpeza, semântica, CLI, METAR e robustez | Concluídos |

D-05 veio depois de D-02/D-03 (Fase 1), evitando gerar vento superficial errado em escala. O detalhamento está em [10-fase-2-resultados.md](10-fase-2-resultados.md).

### Fase 3 — Médios (3–5 dias)

| Ordem | Achado | Ação |
|---:|---|---|
| 1 | D-09 | Intervalo nos dois sentidos |
| 2 | D-10 | Limpeza por `%Y%m%d` e todas as resoluções |
| 3 | D-12 | Normalizar ângulo 0–360 |
| 4 | D-13 | Renomear precipitação total |
| 5 | D-14 | CLI com validação e sem argumento duplicado |
| 6 | D-20 | Logging, manifesto, lock e escrita atômica |

### Fase 4 — Baixos e dívida (2–3 dias)

D-11, D-15, D-16, D-17, D-18, D-19, D-21 a D-28.

### Reprocessamento

- Reprocessar somente depois de D-01/D-02/D-03.
- Definir uma janela (ex.: últimos 7 dias) e gerar em diretório separado (`reprocess_YYYYMMDD`).
- Comparar contagens e pontos de referência.
- Só então substituir os produtos antigos.
- Nunca misturar produtos antigos e novos no mesmo diretório sem um marcador de versão.

## 10. Testes de aceitação

| ID | Teste | Condição de aprovação |
|---|---|---|
| T-01 | Orientação da grade | Primeira linha do CSV = menor latitude; valor confere com `pygrib` no mesmo ponto |
| T-02 | Componente V | Caso sintético `U=10, V=0` → coluna V zero; resultante 10 |
| T-03 | Altura do vento | 20 m → 65,6 ft; 80 m → 262,5 ft |
| T-04 | Seleção de ciclo | 00:00→00, 05:59→00, 06:00→06, 06:59→06, 07:00→06, 12:00→12, 18:00→18, 23:59→18 |
| T-05 | Vento AUT | Controlador gera `CampoVento` e matrizes para `wind` e `winds` |
| T-06 | Umidade superficial | `-ns` gera arquivo com valores 0–100; MAN não lança `AttributeError` |
| T-07 | JSON METAR | 100% dos arquivos passam em `json.load`; nenhum objeto concatenado |
| T-08 | Data METAR | Virada de mês/ano produz timestamp do mês correto |
| T-09 | Intervalo MAN | `500→200` e `200→500` produzem a mesma lista |
| T-10 | Limpeza | `hoje - 2 dias` correto em 01, 02 e 15 de cada mês |
| T-11 | Ângulo do vento | Todos os valores em `[0, 360)` |
| T-12 | CLI MAN | Chamadas válidas geram arquivos; inválidas retornam erro claro |
| T-13 | Idempotência | Duas execuções iguais não corrompem nem duplicam arquivos |
| T-14 | Regressão | Conjunto de produtos de referência permanece estável após correções |

**Estado após a Fase 2:** T-01 a T-05 estão em
`tests/test_phase1_acceptance.py`; T-06 a T-12 foram implementados em
`tests/test_phase2_acceptance.py` e estão verdes. O reprocessamento da Fase 1 e
os produtos de `winds` foram validados de forma independente com `pygrib`.
T-13 e T-14 continuam pendentes (Fases 3/4). Ver
[09-fase-1-resultados.md](09-fase-1-resultados.md) e
[10-fase-2-resultados.md](10-fase-2-resultados.md).

### Exemplo de verificação de orientação

```python
import csv
import pygrib

grb = pygrib.open("gfs.t00z.pgrb2.0p25.f000").select(
    name="Temperature", typeOfLevel="surface"
)[0]
data, lat, lon = grb.data()

# Ponto escolhido: latitude -10, longitude -50
j = abs(lat[:, 0] + 10).argmin()
i = abs(lon[0, :] + 50).argmin()
esperado = data[j, i]

with open("GFS_0.25_SP_Nsurface_temps_00_..._00.csv") as f:
    for row in csv.DictReader(f):
        if abs(float(row["lat"]) + 10) < 0.13 and abs(float(row["lon"]) + 50) < 0.13:
            assert abs(float(row["temps"]) - (esperado - 273.15)) < 0.2
            break
```

## 11. Critérios de conclusão e riscos residuais

### Definição de pronto

- Nenhum achado Crítico ou Alto em aberto.
- Todos os testes T-01 a T-14 passando.
- Produtos de referência regenerados e comparados.
- 7 dias de execução em paralelo sem divergência.
- Documentação e help atualizados.
- Backup e plano de rollback testados.

### Riscos residuais

- **Nomes do GFS**: o código depende de nomes exatos (`Temperature`, `Total Precipitation` etc.); uma mudança no NOMADS pode quebrar a seleção.
- **Basemap**: dependência antiga e sensível ao ambiente; pode falhar em Python/NumPy novos.
- **NOAA/METAR**: disponibilidade e formato podem variar; não há retry.
- **Fuso**: a operação assume hora local; qualquer mudança de `TZ` altera ciclo e diretório.
- **Volume**: sem quota, a retenção pode encher o disco mesmo com a data corrigida; monitore o espaço.
- **Validação numérica**: os produtos GFS foram comparados com leitura independente via `pygrib`; ainda falta validação com observações/METAR e com os consumidores externos.

### O que não foi alterado

A auditoria original não modificou código; as correções foram implementadas depois, em branch separado, com testes. `goGribV2.sh` permanece congelado.

## 12. Estado após a Fase 1

A Fase 1 foi executada na branch `execucao` e cobriu os cinco achados de
cálculo priorizados:

| Achado | Correção | Evidência |
|---|---|---|
| D-01 | Dados invertidos junto com `lat` em todos os geradores AUT/MAN, escalares e vento, inclusive no ramo `flag == 3` | Primeira linha do CSV de `temp` 850 hPa passou de 26,0934 °C (valor do norte) para 15,7734 °C (valor do sul), conferindo com `pygrib` |
| D-02 | Preditor AUT passou a receber `v_comp_supe`; mapa superficial AUT passou a ler `vSupe` | `vento U` e `vento V` deixaram de ser idênticos nos níveis 20/30/40/50/80 m; valores conferem com o GRIB |
| D-03 | Níveis de altura `20/30/40/50/80` usam `metros × 3,28084`; níveis de pressão mantêm a fórmula barométrica | `hMET` de 20 m passou de 76.487,0118 ft para 65,6168 ft; 850 hPa permaneceu em 4.779,1936 ft |
| D-04 | Intervalo semiaberto `[ciclo, próximo)`, caminhos absolutos e erro explícito quando o ciclo não existe | 00:00–05:59 → ciclo `00` do mesmo dia; 06:00 → `06`; 12:00 → `12`; 18:00 → `18` |
| D-12 | `angMET = ((180/π)·arctan2(-u,-v) + 360) mod 360` | Todos os ângulos ficaram em `[0, 360)`; o mínimo do baseline era -179,2747° |

Nenhum nome de variável, produto, arquivo, header ou unidade foi alterado. O
baseline da Fase 0 permanece intacto em `baseline/reports/20261022-00/`; o
reprocessamento está em `reprocessamento/reports/20261022-00/`. O detalhamento
completo está em [09-fase-1-resultados.md](09-fase-1-resultados.md).

## 13. Estado após a Fase 2

A Fase 2 foi executada no worktree `METamorfose`, branch `execucao`, sobre o
commit `9288c1f`. Ela cobriu os itens de produto, CLI, METAR e documentação:

| Achado | Correção aplicada | Evidência |
|---|---|---|
| D-05 | Controlador gera `winds -ns` para SP/RJ; bloco duplicado de 1000/200 removido; wrappers validam as flags | `automatizacao_controle_MET.sh`, `automatiza_vento_MET.sh`; T-07 |
| D-06 | Controlador usa `umidadeRel -n 850`; `-ns` falha com mensagem que indica `-n 850` | `processamento_dados_MET.py`, `executa_reqs_param.py`; T-06 |
| D-07 | JSON METAR gravado com `"w"` em `.tmp`, `fsync` e `os.replace`; reexecução sobrescreve | `METARpy/metar_common.py`; T-08 |
| D-08 | Timestamp resolvido contra referência UTC com rollover de mês/ano; diretório usa a mesma referência | `metar_common.py`, `automatizaMetar.sh`; T-08 |
| D-09 | Intervalo MAN aceita as duas ordens, devolve níveis crescentes e rejeita fora de 150–1000 hPa | `executa_reqs_param.py`; T-09 |
| D-10 | Limpeza usa `date -d "-2 days"`; remove `0p25`, `1p00`, legados e produtos do dia; valida data | `remove_GRIBS_antigos.sh`; T-10 |
| D-13 | `chuvaNaoConvec` documentado como precipitação total; nome/seletor preservados | `docs/03`, `docs/08` |
| D-14 | CLI MAN migrado para `argparse`; wrapper fino; flags em qualquer ordem; erros com código 2 | `executa_reqs_param.py`, `reqs_MAN_MET.sh`; T-11 |
| D-15 | Chamada duplicada de `gera_matriz` removida | `gera_matriz_MAN_MET.py` |
| D-17 | Comparações de nuvem usam `is None`/`is not None` | `metar_common.py`; T-12 |
| D-24 | Janela/rótulo `+6` da chuva documentado; nome preservado | `docs/03` |
| D-25 | Variáveis indefinidas removidas; referência UTC única no shell | `automatizaMetar.sh`; T-08 |
| D-27 | `temps` documentado como temperatura de pele; seletor preservado | `docs/03`, `docs/08` |
| D-28 | Wrappers com `set -euo pipefail`, validação, faixa 150–1000 e help; `chuva`/`MN` rejeitados | `automatiza_MET.sh`, `automatiza_vento_MET.sh`, `reqs_MAN_MET.sh`; T-11 |

Resultados verificáveis:

- `tests/test_phase2_acceptance.py`: **36 testes** T-06–T-12, todos verdes;
- suíte completa: **162 passed**;
- validação independente `reprocessamento/validar_fase2.py`: **177 verificações, 0 falhas**;
- 20 produtos da Fase 1 preservados e `goGribV2.sh` continua com o SHA-256 congelado;
- relatório em `reprocessamento/reports/fase-2/validation.json` e
  [10-fase-2-resultados.md](10-fase-2-resultados.md).

Continuam em aberto, por serem Fase 3: **D-16** (`exit 1` no controlador),
**D-18** (sanitização de caminho/região), **D-19** (artefatos e empacotamento),
**D-20** (logging/lock/idempotência), **D-21/D-22/D-23** (robustez de
`ponto_regiao`/`controla_env`) e **D-26** (fechamento de figuras/GRIB). **D-11**
permanece fora de escopo porque `goGribV2.sh` está congelado.
