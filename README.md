# PMI – Analisador de logs de acesso

Ferramenta de linha de comando que lê os logs de acesso de um servidor web (um
arquivo por dia) e gera um relatório com status HTTP, URLs, IPs, tráfego por hora
e acessos de IPs bloqueados. Só usa a biblioteca padrão (Python 3.11+).

## Estrutura

```
src/analisador_logs/nucleo.py      rotina que processa UM arquivo de log
src/analisador_logs/sequencial.py  versão sequencial (antes)
src/analisador_logs/paralelo.py    versão paralela com multiprocessing.Pool (depois)
scripts/gerar_dados.py             gera a massa de teste (seed fixa)
scripts/experimentos_desafios.py   reproduz os deadlocks / problemas de concorrência do relatório
scripts/medir_overheads.py         mede custo do Pool, pickle, reduce e efeito do hardware
benchmark_paralelismo.py           sequencial x threads x Pool (3 repetições, mediana)
RELATORIO_PARALELISMO.md           relatório da atividade + roteiro da apresentação
resultados/                        tabelas do benchmark e saída do cProfile
```

Histórico: tag `v1-sequencial` (antes) e tag `v2-paralelo` (depois).

## Como rodar (PowerShell, na raiz do projeto)

Demonstração em um comando só (sequencial x paralelo x threads, igual ao exemplo da aula):

```powershell
python main.py
```

Comandos separados:

```powershell
python scripts/gerar_dados.py                 # 60 arquivos x 60.000 linhas em dados/
$env:PYTHONPATH = "src"
python -m analisador_logs.sequencial          # relatório em resultados/relatorio_sequencial.json
python -m analisador_logs.paralelo            # usa os.cpu_count() processos
python -m analisador_logs.paralelo dados 4    # escolhendo a quantidade de processos

python benchmark_paralelismo.py               # ~7 min; grava resultados/benchmark.md
python scripts/experimentos_desafios.py       # ~25 s (dois casos travam de propósito)
python scripts/medir_overheads.py             # ~50 s

# análise de gargalo (cProfile) da versão sequencial
python -m cProfile -s tottime -m analisador_logs.sequencial | Select-Object -First 30
```
