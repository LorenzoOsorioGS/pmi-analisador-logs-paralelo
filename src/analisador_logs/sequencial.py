"""Versão ANTES (sequencial): analisa os arquivos de log um depois do outro.

Uso (na raiz do projeto, PowerShell):
    $env:PYTHONPATH = "src"
    python -m analisador_logs.sequencial [pasta]
"""
import sys
from datetime import datetime
from time import perf_counter

from analisador_logs import nucleo


def executar(pasta, mostrar_pid=True):
    arquivos = nucleo.listar_arquivos(pasta)
    nucleo.preparar(pasta, mostrar_pid)  # carrega os IPs bloqueados uma única vez
    # Igual ao [tarefa(i) for i in range(4)] da aula: um item por vez, num só processo
    parciais = [nucleo.tarefa(item) for item in enumerate(arquivos)]
    return nucleo.juntar(parciais)


if __name__ == "__main__":
    pasta = sys.argv[1] if len(sys.argv) > 1 else "dados"

    inicio = datetime.now()
    t0 = perf_counter()
    print(f"Início: {inicio:%H:%M:%S.%f}")

    resultado = executar(pasta)

    duracao = perf_counter() - t0
    fim = datetime.now()
    print(f"Fim:    {fim:%H:%M:%S.%f}")
    print(f"Sequencial: {duracao:.2f} s\n")

    nucleo.imprimir_resumo(resultado)
    nucleo.salvar(resultado, "resultados/relatorio_sequencial.json")
