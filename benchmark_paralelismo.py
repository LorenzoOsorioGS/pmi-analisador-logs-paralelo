"""Benchmark: sequencial x threads x Pool, sempre com a mesma massa de dados.

Uso: python benchmark_paralelismo.py
Gera dados/ e dados_pequeno/ se não existirem e grava as tabelas em resultados/benchmark.md.
"""
import os
import platform
import subprocess
import sys
from datetime import datetime
from multiprocessing.pool import ThreadPool
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).parent / "src"))  # importa o pacote sem precisar instalar
from analisador_logs import nucleo, paralelo, sequencial  # noqa: E402

REPETICOES = 3
CABECALHO = ["| Modo | Workers | Início | Fim | Tempo (s) | Speedup | Eficiência |",
             "|---|---|---|---|---|---|---|"]


def com_threads(pasta, threads):
    """Mesmo fluxo do paralelo trocando processos por threads: todas presas ao mesmo GIL."""
    arquivos = nucleo.listar_arquivos(pasta)
    with ThreadPool(threads, initializer=nucleo.preparar, initargs=(pasta, False)) as pool:
        return nucleo.juntar(pool.imap_unordered(nucleo.tarefa, enumerate(arquivos)))


def ambiente():
    info = {"SO": platform.platform(), "Python": platform.python_version(), "CPU": platform.processor(),
            "Núcleos físicos": "n/d", "Núcleos lógicos": os.cpu_count(), "RAM": "n/d"}
    if sys.platform == "win32":  # ponytail: detalhes só no Windows (SO da apresentação)
        cmd = ("$c = Get-CimInstance Win32_Processor; $m = Get-CimInstance Win32_ComputerSystem; "
               '"$($c.Name)|$($c.NumberOfCores)|$($m.TotalPhysicalMemory)"')
        cpu, fisicos, ram = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                           capture_output=True, text=True).stdout.strip().split("|")
        info.update({"CPU": cpu.strip(), "Núcleos físicos": int(fisicos), "RAM": f"{int(ram) / 2**30:.1f} GB"})
    return info


def medir(funcao, *args):
    """Roda REPETICOES vezes e devolve a rodada mediana: (tempo, início, fim, resultado)."""
    rodadas = []
    for _ in range(REPETICOES):
        inicio = datetime.now()
        t0 = perf_counter()
        resultado = funcao(*args)
        tempo = perf_counter() - t0
        rodadas.append((tempo, inicio, datetime.now(), resultado))
    rodadas.sort(key=lambda r: r[0])
    return rodadas[len(rodadas) // 2]


def cenario(pasta, workers_pool):
    """Mede cada modo; o sequencial (1º) é a referência de tempo e de resultado."""
    modos = [("Sequencial", 1, sequencial.executar, (False,)),
             ("Threads", 4, com_threads, (4,))]
    modos += [("Pool", n, paralelo.executar, (n, False)) for n in workers_pool]

    linhas, referencia, t_seq = [], None, None
    for nome, workers, funcao, args in modos:
        tempo, inicio, fim, resultado = medir(funcao, pasta, *args)
        if referencia is None:
            referencia, t_seq = resultado, tempo
        assert resultado == referencia, f"{nome} ({workers}) deu resultado diferente do sequencial!"
        speedup = t_seq / tempo
        linha = (f"| {nome} | {workers} | {inicio:%H:%M:%S.%f} | {fim:%H:%M:%S.%f} | "
                 f"{tempo:.2f} | {speedup:.2f}x | {speedup / workers:.0%} |")
        print(linha, flush=True)
        linhas.append(linha)
    return linhas


if __name__ == "__main__":  # obrigatório no Windows: os workers reimportam este arquivo
    for pasta, extra in (("dados", []), ("dados_pequeno", ["--arquivos", "12", "--linhas", "200"])):
        if not Path(pasta).exists():
            subprocess.run([sys.executable, "scripts/gerar_dados.py", "--pasta", pasta, *extra], check=True)

    amb = ambiente()
    cpus = os.cpu_count()
    fisicos = amb["Núcleos físicos"]
    workers = sorted({1, 2, 4, cpus} | ({fisicos} if isinstance(fisicos, int) else set()))

    md = ["# Benchmark", "", *(f"- **{k}:** {v}" for k, v in amb.items()),
          f"- **Repetições:** {REPETICOES} por modo (tabela mostra a mediana)", ""]
    print("\n".join(md))
    for titulo, pasta, w in (("Volume normal", "dados", workers), ("Volume pequeno", "dados_pequeno", [2, cpus])):
        arquivos = nucleo.listar_arquivos(pasta)
        mb = sum(os.path.getsize(a) for a in arquivos) / 2**20
        titulo = f"## {titulo}: {len(arquivos)} arquivos, {mb:.1f} MB"
        print(titulo, "", *CABECALHO, sep="\n")
        md += [titulo, "", *CABECALHO, *cenario(pasta, w), ""]

    Path("resultados").mkdir(exist_ok=True)
    Path("resultados/benchmark.md").write_text("\n".join(md), encoding="utf-8")
    print("\nTabelas gravadas em resultados/benchmark.md")
