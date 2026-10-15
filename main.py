"""Demonstração em um comando só, igual ao exemplo da aula: sequencial x paralelo x threads.

Uso: python main.py
"""
import subprocess
import sys
from datetime import datetime
from multiprocessing.pool import ThreadPool
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).parent / "src"))  # dispensa o PYTHONPATH
from analisador_logs import nucleo, paralelo, sequencial  # noqa: E402

PASTA = "dados_demo"
TAREFAS = 6  # 6 arquivos de log = 6 tarefas; 1 worker por núcleo físico do i5-12400F


def com_threads(pasta):
    """Mesmo trabalho com threads: todas no mesmo processo (mesmo PID) e presas ao GIL."""
    arquivos = nucleo.listar_arquivos(pasta)
    with ThreadPool(TAREFAS, initializer=nucleo.preparar, initargs=(pasta,)) as pool:
        return nucleo.juntar(pool.imap_unordered(nucleo.tarefa, enumerate(arquivos)))


def medir(nome, funcao):
    inicio = datetime.now()
    print(f"\nIniciando {nome}... Início: {inicio:%H:%M:%S.%f}", flush=True)
    t0 = perf_counter()
    resultado = funcao()
    tempo = perf_counter() - t0
    print(f"{nome}: Fim: {datetime.now():%H:%M:%S.%f} | Tempo: {tempo:.2f} s", flush=True)
    return resultado, tempo


if __name__ == "__main__":
    if len(list(Path(PASTA).glob("acessos_*.log"))) != TAREFAS:  # (re)gera os logs de teste
        subprocess.run([sys.executable, "scripts/gerar_dados.py", "--pasta", PASTA,
                        "--arquivos", str(TAREFAS), "--linhas", "200000"], check=True)

    r_seq, tempo_seq = medir("Sequencial", lambda: sequencial.executar(PASTA))
    r_par, tempo_par = medir(f"Paralelo ({TAREFAS} processos)", lambda: paralelo.executar(PASTA, TAREFAS))
    r_thr, tempo_thread = medir(f"Threads ({TAREFAS})", lambda: com_threads(PASTA))
    assert r_seq == r_par == r_thr, "As versões deram resultados diferentes!"

    print(f"\nO modo paralelo foi {tempo_seq / tempo_par:.1f}x mais rápido que o sequencial.")
    print(f"O modo thread foi {tempo_seq / tempo_thread:.1f}x mais rápido que o sequencial.")
    print(f"O modo paralelo foi {tempo_thread / tempo_par:.1f}x mais rápido que o thread.\n")
    nucleo.imprimir_resumo(r_par)
