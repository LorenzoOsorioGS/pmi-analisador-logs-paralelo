"""Versão DEPOIS (paralela): os arquivos de log são distribuídos entre os processos de um Pool.

Uso (na raiz do projeto, PowerShell):
    $env:PYTHONPATH = "src"
    python -m analisador_logs.paralelo [pasta] [processos]
"""
import os
import sys
from datetime import datetime
from multiprocessing import Pool
from time import perf_counter

from analisador_logs import nucleo


def executar(pasta, processos=None, mostrar_pid=True):
    arquivos = nucleo.listar_arquivos(pasta)
    # processes=None -> os.cpu_count(). O initializer roda 1x em CADA worker:
    # a lista de IPs bloqueados é carregada uma vez por processo, e não reenviada a cada tarefa.
    with Pool(processes=processos, initializer=nucleo.preparar, initargs=(pasta, mostrar_pid)) as pool:
        # imap_unordered: cada resultado volta assim que o arquivo termina; a ordem não importa
        # porque somar Counters é comutativo. chunksize=1 porque cada item é pesado (~0,5 s):
        # um arquivo por vez equilibra a carga entre os workers e o custo de IPC é desprezível.
        parciais = pool.imap_unordered(nucleo.tarefa, enumerate(arquivos), chunksize=1)
        # O "reduce" (e qualquer escrita em arquivo) fica no processo principal.
        # Precisa consumir AQUI dentro do with: na saída o Pool é encerrado (terminate()).
        return nucleo.juntar(parciais)


if __name__ == "__main__":  # obrigatório no Windows: cada worker reimporta este módulo
    pasta = sys.argv[1] if len(sys.argv) > 1 else "dados"
    processos = int(sys.argv[2]) if len(sys.argv) > 2 else os.cpu_count()

    inicio = datetime.now()
    t0 = perf_counter()
    print(f"Início: {inicio:%H:%M:%S.%f} ({processos} processos, PID principal {os.getpid()})", flush=True)

    resultado = executar(pasta, processos)

    duracao = perf_counter() - t0
    fim = datetime.now()
    print(f"Fim:    {fim:%H:%M:%S.%f}")
    print(f"Paralelo: {duracao:.2f} s\n")

    nucleo.imprimir_resumo(resultado)
    nucleo.salvar(resultado, "resultados/relatorio_paralelo.json")
