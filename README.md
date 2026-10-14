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
```

Histórico: tag `v1-sequencial` (antes) e tag `v2-paralelo` (depois).

## Como rodar (PowerShell, na raiz do projeto)

```powershell
python scripts/gerar_dados.py                 # 60 arquivos x 60.000 linhas em dados/
$env:PYTHONPATH = "src"
python -m analisador_logs.sequencial          # relatório em resultados/relatorio_sequencial.json
python -m analisador_logs.paralelo            # usa os.cpu_count() processos
python -m analisador_logs.paralelo dados 4    # escolhendo a quantidade de processos
```
