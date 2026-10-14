# Relatório – Paralelização com `multiprocessing` no projeto PMI

**Disciplina:** Desenvolvimento em Linguagens de Programação Disruptivas II (ADS)
**Projeto:** Analisador de logs de acesso — Python 3.13, linha de comando, só biblioteca padrão
**Ambiente:** Windows 11 (10.0.26200) · Intel Core i5-12400F (6 núcleos físicos / 12 lógicos) · 15,8 GB RAM
**Histórico no git:** tag `v1-sequencial` (antes) → tag `v2-paralelo` (depois)

---

## 1. O projeto e a rotina paralelizada

O sistema lê os logs de acesso de um servidor web — **um arquivo por dia, 60 dias** — e gera um
relatório com a distribuição de status HTTP, as URLs mais acessadas, as requisições por IP e por
hora, o tráfego total e os acessos vindos de IPs bloqueados. A massa de teste tem
**60 arquivos × 60.000 linhas = 3,6 milhões de linhas (283 MB)**, gerada com seed fixa por
`scripts/gerar_dados.py`.

**Rotina paralelizada:** `analisar_arquivo(caminho)` em `src/analisador_logs/nucleo.py`. Para cada
linha ela aplica uma expressão regular, converte a data com `datetime.strptime` e atualiza os
contadores. Como cada arquivo é independente dos outros, **o item de trabalho do Pool é um arquivo**.

### Evidência do cProfile (versão sequencial)

`python -m cProfile -o resultados/sequencial.prof -m analisador_logs.sequencial`
(saída completa em `resultados/cprofile_sequencial.txt`)

| Função | Chamadas | Tempo acumulado | % do total |
|---|---:|---:|---:|
| `analisar_arquivo` (a rotina) | 60 | 66,27 s | **99,9%** |
| `datetime.strptime` (converter a data) | 3.596.471 | 55,10 s | **83,0%** |
| ↳ dentro dele, `locale.getlocale` (checa o idioma a cada chamada) | 3.596.473 | 7,99 s | 12,0% |
| `re.Pattern.match` (regex nossa + regex interna do strptime) | 7.196.532 | 4,37 s | 6,6% |
| decodificação UTF-8 do arquivo | 36.300 | 0,08 s | 0,1% |
| **Total com o profiler ligado** | | **66,34 s** | |

> O profiler deixa o programa ~2x mais lento (66 s × 31 s sem ele), mas as proporções valem.

**Classificação: CPU-bound.** Para confirmar, medimos só a leitura das 3,6 milhões de linhas, sem
processar nada: **0,55 s**, ou seja **1,8%** dos 31,1 s do sequencial. Os outros ~98% são a CPU
executando Python puro (regex, strptime, contadores). Isso define a estratégia:

- **threads não ajudam** — o GIL deixa só uma thread executar bytecode Python por vez;
- **processos ajudam** — cada um tem seu próprio interpretador e seu próprio GIL.

---

## 2. a) Dificuldades encontradas

1. **A saída dos workers sumia.** Na primeira execução do paralelo (com a saída redirecionada),
   apareceram só **20 das 60** linhas `Tarefa N finalizada com PID: ...` — e antes da linha
   "Início". Causa: com o stdout redirecionado, o `print` fica num buffer dentro do worker; ao sair
   do `with Pool`, o Pool chama `terminate()` e mata os processos antes de o buffer ser descarregado.
   Solução: `print(..., flush=True)`. Depois disso: **60 linhas e 12 PIDs distintos**.
2. **Calibrar o volume.** O primeiro teste (4 arquivos × 50 mil linhas) levava 1,7 s — pouco demais:
   o custo de criar os processos esconderia o ganho. Medimos ~8,6 µs por linha e calibramos para
   60 × 60 mil (~30 s). E 60 é divisível por 1, 2, 4, 6 e 12: com qualquer quantidade de workers
   testada, todos recebem a mesma quantidade de arquivos (ninguém fica ocioso no fim).
3. **A primeira medição é "fria".** Numa rodada única o sequencial pequeno levou 0,17 s; a mediana de
   3 rodadas, 0,03 s. A primeira chamada de `strptime` importa o módulo `_strptime` e monta as regex
   de datas. Solução: 3 repetições de cada modo e uso da mediana.
4. **Particularidades do Windows.** O Windows cria processos por *spawn*: cada worker é um Python
   novo que **reimporta** o módulo principal. Isso obriga o `if __name__ == "__main__":` (sem ele o
   programa trava — ver seção 5) e exige que o pacote em `src/` esteja no caminho de importação
   (`PYTHONPATH=src`; o benchmark faz `sys.path.insert`, que o spawn repassa aos filhos). Também
   tivemos `SyntaxError` em scripts de teste gravados sem `encoding="utf-8"` (o padrão do Windows é
   cp1252); por isso todo `open()` do projeto declara a codificação.
5. **O gargalo não era o que parecia.** Esperávamos que a regex fosse a parte mais cara; o cProfile
   mostrou que **83% é o `strptime`** — e 12% do tempo total é ele conferindo o *locale* a cada uma
   das 3,6 milhões de chamadas. Isso levou ao teste da seção 5.4.

---

## 3. b) Tempo de execução antes e depois

### Execução avulsa (hora de início/fim do próprio programa)

| Versão | Início | Fim | Duração | PIDs usados |
|---|---|---|---:|---:|
| Antes — `python -m analisador_logs.sequencial` | 19:54:15.271920 | 19:54:46.390205 | **31,12 s** | 1 (6380) |
| Depois — `python -m analisador_logs.paralelo` (12 processos) | 19:57:17.969560 | 19:57:23.459467 | **5,49 s** | 12 |

Os dois geraram exatamente o mesmo `relatorio_*.json` (3.596.471 requisições, 90,32 GB de tráfego,
71.887 acessos de IPs bloqueados, 3.529 linhas inválidas).

### Benchmark (`benchmark_paralelismo.py` · 3 repetições · mediana)

**Volume normal: 60 arquivos, 282,8 MB**

| Modo | Workers | Início | Fim | Tempo (s) | Speedup | Eficiência |
|---|---:|---|---|---:|---:|---:|
| Sequencial | 1 | 20:01:25.628548 | 20:01:55.715245 | 30,09 | 1,00x | 100% |
| Threads | 4 | 20:02:58.707935 | 20:03:30.135565 | 31,43 | **0,96x** | 24% |
| Pool | 1 | 20:04:29.789215 | 20:04:59.580127 | 29,79 | 1,01x | 101% |
| Pool | 2 | 20:05:32.259581 | 20:05:48.450436 | 16,19 | 1,86x | 93% |
| Pool | 4 | 20:05:48.452061 | 20:05:57.676988 | 9,22 | 3,26x | 82% |
| Pool | 6 | 20:06:16.089774 | 20:06:23.054613 | 6,96 | 4,32x | 72% |
| Pool | 12 | 20:06:37.019439 | 20:06:42.470599 | **5,45** | **5,52x** | 46% |

**Volume pequeno: 12 arquivos × 200 linhas, 0,2 MB**

| Modo | Workers | Início | Fim | Tempo (s) | Speedup | Eficiência |
|---|---:|---|---|---:|---:|---:|
| Sequencial | 1 | 20:06:53.427113 | 20:06:53.452117 | 0,03 | 1,00x | 100% |
| Threads | 4 | 20:06:53.476637 | 20:06:53.513221 | 0,04 | 0,68x | 17% |
| Pool | 2 | 20:06:53.692075 | 20:06:53.795769 | 0,10 | **0,24x** | 12% |
| Pool | 12 | 20:06:54.186770 | 20:06:54.333375 | 0,15 | **0,17x** | 1% |

*Speedup = tempo_seq / tempo_modo · Eficiência = speedup / workers.* Em todos os modos o benchmark
confere com `assert` que o resultado é **idêntico** ao do sequencial.

### Interpretação

- **Antes → depois: 30,09 s → 5,45 s (5,5x)** com 12 processos; com 6 (um por núcleo físico), 4,3x.
- **Threads não ganharam nada (0,96x)**: as 4 threads disputam o mesmo GIL e só uma executa Python
  por vez. A troca constante de thread ainda deixa um pouco mais lento que o sequencial.
- **Pool(1) ≈ sequencial**: criar o Pool custa ~0,1 s, irrelevante perto de 30 s.
- **O speedup cresce, mas a eficiência cai**: 93% (2) → 72% (6) → 46% (12). A causa está na seção 5.3.
- **Com volume pequeno o paralelo é 4 a 6x MAIS LENTO** — ver seção 5.4.

---

## 4. c) Código sequencial × código paralelo

A rotina pesada (`analisar_arquivo`) **não mudou uma linha**. O que muda é *quem* a chama e *onde*
ela roda. Trechos de `sequencial.py` e `paralelo.py` (comentários resumidos para caber lado a lado):

<table>
<tr><th>ANTES — sequencial.py</th><th>DEPOIS — paralelo.py</th></tr>
<tr><td>
<pre>
def executar(pasta, mostrar_pid=True):
    arquivos = nucleo.listar_arquivos(pasta)

    # carrega os IPs bloqueados 1x
    nucleo.preparar(pasta, mostrar_pid)

    # Como o [tarefa(i) for i in range(4)]
    # da aula: um arquivo por vez, tudo
    # dentro de UM processo (um PID só)
    parciais = [nucleo.tarefa(item)
                for item in enumerate(arquivos)]



    # soma os resultados parciais
    return nucleo.juntar(parciais)
</pre>
</td><td>
<pre>
def executar(pasta, processos=None, mostrar_pid=True):
    arquivos = nucleo.listar_arquivos(pasta)
    # None = os.cpu_count(); o initializer roda
    # 1x em CADA worker (carrega os IPs dele)
    with Pool(processes=processos,
              initializer=nucleo.preparar,
              initargs=(pasta, mostrar_pid)) as pool:
        # Como o p.map(tarefa, range(4)) da aula:
        # os arquivos são distribuídos entre os
        # processos (cada um com seu PID)
        parciais = pool.imap_unordered(
            nucleo.tarefa, enumerate(arquivos),
            chunksize=1)
        # reduce no processo principal,
        # AINDA DENTRO do with
        return nucleo.juntar(parciais)
</pre>
</td></tr>
</table>

| Decisão no paralelo | Por quê |
|---|---|
| `Pool(processes=None)` → `os.cpu_count()` | configurável pela linha de comando: `python -m analisador_logs.paralelo dados 6` |
| `initializer=nucleo.preparar` | a lista de 17.292 IPs bloqueados é lida **uma vez por worker**, e não reenviada a cada tarefa |
| `imap_unordered` em vez de `map` | cada resultado volta assim que o arquivo termina; a ordem não importa porque somar contadores é comutativo |
| `chunksize=1` | cada item é pesado (~0,5 s): mandar um arquivo por vez equilibra a carga; o custo de IPC por item é desprezível |
| worker recebe só o **caminho** do arquivo | o worker lê o próprio arquivo; os 283 MB nunca passam por pickle |
| `juntar()` e `salvar()` no processo principal | nenhum worker escreve em arquivo → sem condição de corrida |
| `juntar()` **dentro** do `with` | ao sair do `with` o Pool é encerrado; consumir o iterador depois trava (seção 5.1) |
| `if __name__ == "__main__":` | obrigatório no Windows: cada worker reimporta o módulo |

A função de cada item segue o mesmo formato do `tarefa(n)` da aula (`nucleo.py`):

```python
def tarefa(item):
    """Igual ao tarefa(n) da aula: processa um item e mostra qual PID fez o trabalho."""
    n, caminho = item
    resultado = analisar_arquivo(caminho)
    if _mostrar_pid:
        print(f"Tarefa {n} finalizada com PID: {os.getpid()}", flush=True)
    return resultado
```

E a medição de hora de início/fim (igual nas duas versões):

```python
inicio = datetime.now()              # hora de início (relógio)
t0 = perf_counter()                  # cronômetro de alta precisão
print(f"Início: {inicio:%H:%M:%S.%f}")

resultado = executar(pasta)

duracao = perf_counter() - t0
fim = datetime.now()                 # hora de fim
print(f"Fim:    {fim:%H:%M:%S.%f}")
```

Saída (trechos) — no sequencial todo trabalho é feito pelo mesmo PID; no paralelo, por 12 PIDs
diferentes e fora de ordem:

```
SEQUENCIAL                                 PARALELO (12 processos)
Início: 19:54:15.271920                    Início: 19:57:17.969560 (12 processos, PID principal 10160)
Tarefa 0 finalizada com PID: 6380          Tarefa 2 finalizada com PID: 8716
Tarefa 1 finalizada com PID: 6380          Tarefa 3 finalizada com PID: 5424
Tarefa 2 finalizada com PID: 6380          Tarefa 0 finalizada com PID: 18200
...                                        ...
Fim:    19:54:46.390205                    Fim:    19:57:23.459467
Sequencial: 31.12 s                        Paralelo: 5.49 s
```

---

## 5. d) Desafios

Os casos abaixo foram **executados de verdade** (`python scripts/experimentos_desafios.py`, cada um
num subprocesso com limite de 10 s) e as medições de custo vêm de `scripts/medir_overheads.py`.

### 5.1 Deadlocks

| Situação testada | O que aconteceu | Como o projeto evita |
|---|---|---|
| Pool criado **sem** `if __name__ == "__main__":` | **Travou.** 508 `RuntimeError` em 10 s: cada worker reimporta o arquivo, tenta criar outro Pool e morre; o Pool recria o worker, que morre de novo, sem fim | guard em `paralelo.py` e `benchmark_paralelismo.py` |
| Retornar o `imap_unordered` e consumir **fora** do `with` | **Travou (deadlock).** O `with` já chamou `terminate()`; o iterador fica esperando resultados de workers que não existem mais | `juntar()` consome o iterador dentro do `with` (com comentário no código) |
| Worker abrindo **outro Pool** (pool aninhado) | `AssertionError: daemonic processes are not allowed to have children` | paralelismo em um nível só: um arquivo por tarefa |
| `Queue` e `Lock` | não usados | os workers só **retornam** valores; quem transporta é o próprio Pool. Sem lock, não existe espera circular. (A armadilha clássica — um processo que colocou muitos dados numa `Queue` não termina até alguém ler a fila; dar `join()` antes de ler trava os dois — não pode acontecer aqui.) |

### 5.2 Concorrência

- **Estado compartilhado não existe entre processos.** Teste: um `Counter` global alterado pelos
  workers continuou **vazio** (`Counter()`) no processo principal — cada worker alterou a própria
  cópia. Por isso o desenho é *map-reduce*: cada tarefa devolve seu resultado parcial e o principal
  soma tudo em `juntar()`.
- **Condição de corrida na escrita.** Se cada worker gravasse no mesmo JSON, as escritas poderiam se
  misturar ou sobrescrever umas às outras. Aqui só o processo principal grava (`nucleo.salvar`).
  Os `print` dos workers chegam fora de ordem (`Tarefa 2, 3, 0, ...`), o que é esperado.
- **Threads compartilham memória — e por isso precisam de mais cuidado.** Se as threads somassem
  num dicionário comum (`r["bytes"] += ...`), haveria condição de corrida; no nosso `ThreadPool`
  cada tarefa cria o próprio `r`. Além disso, o próprio `strptime` usa uma trava interna: o
  cProfile mostra **3.596.471** usos de `_thread.lock`, um por chamada. Com threads, essa trava e o
  GIL são disputados; com processos, cada um tem os seus.
- **O custo do isolamento de memória:** cada worker é um interpretador inteiro, com sua cópia dos
  17.292 IPs bloqueados (carregados 1x por worker pelo `initializer`), e cada resultado volta por
  pickle — **87 KB por arquivo** (~5 MB por execução). Somar os 60 parciais leva **0,038 s**.

### 5.3 Escalabilidade

| Workers | Tempo (s) | Speedup | Eficiência | Tempo de **1 arquivo** com N workers juntos | Previsto = (60/N) × tempo do arquivo |
|---:|---:|---:|---:|---:|---:|
| 1 | 29,79 | 1,01x | 101% | 0,497 s | 29,82 s |
| 2 | 16,19 | 1,86x | 93% | 0,549 s | 16,47 s |
| 4 | 9,22 | 3,26x | 82% | 0,602 s | 9,03 s |
| 6 | 6,96 | 4,32x | 72% | 0,657 s | 6,57 s |
| 12 | 5,45 | 5,52x | 46% | 1,031 s | 5,16 s |

**A parte serial do programa é minúscula.** Subir o Pool custa 0,087 s (2 workers) a 0,119 s
(12 workers), e o `juntar` custa 0,038 s. Isso dá ~0,16 s de 30,09 s: uma **fração serial de
f ≈ 0,5%**.

**Lei de Amdahl:** S(N) = 1 / (f + (1 − f)/N). Com f = 0,5%, o limite teórico seria ~190x, e com
6 núcleos Amdahl prevê **5,85x**. Medimos **4,32x**. A diferença está na 5ª coluna: **cada arquivo
fica mais lento quando há mais núcleos trabalhando** — 0,497 s sozinho, 0,657 s com 6 (+32%).
Corrigindo Amdahl por esse fator (5,85 × 0,497/0,657) chega-se a **4,43x**, a 3% do medido. A última
coluna mostra o mesmo efeito: só o tempo por arquivo já explica o tempo total com erro de até 6%.

- **Por que cada núcleo fica mais lento?** Não medimos a frequência da CPU, mas as causas mais
  prováveis são o *turbo* (o processador baixa o clock quando mais núcleos estão ativos) e a disputa
  pelo cache L3 e pela memória, que são compartilhados.
- **Saturação nos núcleos físicos:** de 6 para 12 workers o ganho foi só de 4,32x para 5,52x
  (+28%). Os 12 "núcleos" lógicos são 6 físicos com *hyperthreading*: dois workers dividem as
  mesmas unidades de execução, e o tempo de cada arquivo quase dobra (0,657 s → 1,031 s).
- **Métrica de Karp-Flatt** (fração serial "efetiva", que inclui esses efeitos do hardware):
  7,5% (2), 7,6% (4), 7,8% (6) e 10,7% (12). O valor estável até 6 mostra que o limite é físico e
  não um trecho serial que cresce.
- **Granularidade:** a unidade de trabalho é o arquivo. Com 60 arquivos, mais de 60 workers não
  adiantam, e com N que não divide 60 (ex.: 8 → 7,5 rodadas) sobram workers ociosos no fim. Para
  escalar mais, seria preciso dividir os arquivos em blocos.

### 5.4 Pouco ganho sequencial × paralelo

- **Volume pequeno:** o sequencial levou 0,03 s, enquanto Pool(2) levou 0,10 s e Pool(12) levou
  0,15 s, ou seja, **4 a 6x mais lento**. Só criar os processos (0,09–0,12 s) já custa mais que o
  trabalho inteiro, e com mais workers há mais processos para criar.
- **Threads × GIL:** 0,96x no volume normal e 0,68x no pequeno. Em tarefa CPU-bound, as threads só
  acrescentam disputa.
- **Pickle/IPC:** aqui o custo é baixo porque o worker recebe só o caminho do arquivo (dezenas de
  bytes) e devolve 87 KB. Se as linhas fossem enviadas aos workers, os 283 MB inteiros passariam por
  pickle.
- **Otimizar antes de paralelizar.** Guiados pelo cProfile, trocamos o `strptime` por pegar a hora
  fatiando a string (`int(data[12:14])`). O **sequencial caiu de 30,16 s para 5,89 s**, com
  resultado idêntico. É praticamente o mesmo ganho dos 12 processos (5,45 s), sem criar nenhum
  processo. As duas técnicas se somam (não medimos a combinação). A lição é medir primeiro,
  corrigir o gargalo e só então paralelizar.

---

## 6. Conclusão

A rotina `analisar_arquivo` concentra 99,9% do tempo e é CPU-bound (1,8% de I/O). Trocar o laço
sequencial por um `multiprocessing.Pool` reduziu a análise de **30,09 s para 5,45 s (5,5x)** com
resultado idêntico, enquanto as threads não ganharam nada por causa do GIL. O ganho satura nos 6
núcleos físicos por limite do hardware, não por código serial (0,5%). Em volumes pequenos o
paralelo chega a ser 6x mais lento. Por fim, o cProfile mostrou que otimizar o `strptime` dá um
ganho parecido sem nenhum processo: paralelizar e otimizar se complementam.

---

## 7. Roteiro da apresentação (~5 min, 7 slides)

| # | Slide | Pontos (3 bullets) | Tempo |
|---|---|---|---|
| 1 | **PMI: analisador de logs em paralelo** | • lê 60 dias de log (3,6 milhões de linhas, 283 MB) e gera relatório de acessos • objetivo: paralelizar a rotina mais pesada com `multiprocessing.Pool` • Python 3.13, só biblioteca padrão, i5-12400F (6 núcleos / 12 threads) | 30 s |
| 2 | **Onde estava o gargalo (cProfile)** | • `analisar_arquivo` = 99,9% do tempo; `strptime` sozinho = 83% • leitura de disco = 1,8% → CPU-bound • arquivos independentes → um arquivo por tarefa | 40 s |
| 3 | **Antes × depois no código** | • antes: `[tarefa(item) for item in enumerate(arquivos)]` • depois: `with Pool(...) as pool: pool.imap_unordered(tarefa, ..., chunksize=1)` • `initializer` carrega os IPs 1x por worker; soma e gravação só no principal | 50 s |
| 4 | **Resultados** | • sequencial 30,09 s → Pool(12) 5,45 s = **5,5x**, resultado idêntico • threads: 31,43 s (0,96x) → o GIL na prática • sequencial usa 1 PID; paralelo, 12 PIDs | 50 s |
| 5 | **Deadlocks e concorrência** | • sem o guard `__main__` e com `imap` fora do `with`: travou (demonstrado) • global "compartilhado": o principal ficou com `Counter()` vazio (memória isolada) • solução: workers só retornam; sem Queue/Lock; o principal soma e grava | 50 s |
| 6 | **Escalabilidade e pouco ganho** | • eficiência 93% (2) → 72% (6) → 46% (12): cada arquivo vai de 0,50 s para 0,66 s e 1,03 s • parte serial de só 0,5% → o limite é o hardware (núcleos físicos / HT) • volume pequeno: paralelo 4–6x mais lento (subir o Pool ~0,1 s > trabalho de 0,03 s) | 50 s |
| 7 | **Conclusão e lição** | • Pool deu 5,5x em tarefa CPU-bound; threads não servem aqui • trocar o `strptime` por fatiar a string: 30,2 s → 5,9 s sem processo nenhum • medir (cProfile) → otimizar → paralelizar | 30 s |

**Demo ao vivo (opcional, ~40 s):** `python -m analisador_logs.sequencial` e depois
`python -m analisador_logs.paralelo`, mostrando a hora de início/fim e os PIDs na tela.
