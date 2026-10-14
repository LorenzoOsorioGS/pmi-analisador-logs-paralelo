"""Reproduz os desafios citados no relatório (deadlocks e concorrência).

Cada caso roda num subprocesso separado com timeout, porque alguns TRAVAM de propósito.
Uso: python scripts/experimentos_desafios.py
"""
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

TIMEOUT = 10

CASOS = {
    "1) Pool sem o guard __main__ (Windows/spawn)": """
        from multiprocessing import Pool
        def f(x): return x * x
        with Pool(2) as p:                      # SEM if __name__ == "__main__"
            print(p.map(f, range(4)))
    """,
    "2) iterador do imap consumido fora do with": """
        from multiprocessing import Pool
        def f(x): return x * x
        def executar():
            with Pool(2) as p:
                return p.imap_unordered(f, range(4))  # devolve sem consumir
        if __name__ == "__main__":
            print(list(executar()))             # o with já chamou terminate()
    """,
    "3) Pool aninhado (worker abrindo outro Pool)": """
        from multiprocessing import Pool
        def f(x): return x * x
        def g(x):
            with Pool(2) as p:
                return sum(p.map(f, range(x)))
        if __name__ == "__main__":
            with Pool(2) as p:
                print(p.map(g, [3, 4]))
    """,
    "4) 'variável global compartilhada' entre processos": """
        from multiprocessing import Pool
        from collections import Counter
        TOTAL = Counter()
        def f(x):
            TOTAL["linhas"] += 1000             # altera a cópia DO WORKER
            return x
        if __name__ == "__main__":
            with Pool(4) as p:
                p.map(f, range(8))
            print("TOTAL no processo principal:", TOTAL)
    """,
}


def texto(x):
    return x.decode(errors="replace") if isinstance(x, bytes) else (x or "")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as pasta:
        for i, (titulo, codigo) in enumerate(CASOS.items()):
            arq = Path(pasta, f"caso{i}.py")
            arq.write_text(textwrap.dedent(codigo), encoding="utf-8")
            try:
                r = subprocess.run([sys.executable, arq], capture_output=True, text=True, timeout=TIMEOUT)
                saida = (r.stdout + r.stderr).strip().splitlines()
                print(f"{titulo}\n   terminou (código {r.returncode}): {saida[-1] if saida else ''}")
            except subprocess.TimeoutExpired as e:
                erros = (texto(e.stdout) + texto(e.stderr)).count("RuntimeError")
                print(f"{titulo}\n   TRAVOU: morto após {TIMEOUT} s ({erros} RuntimeError na saída)")
