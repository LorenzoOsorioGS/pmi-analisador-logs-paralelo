"""Mede de onde vem a perda de eficiência do paralelo (números usados no relatório).

- custo de subir o Pool, tamanho do pickle de um resultado e custo do juntar (parte serial)
- tempo de UM arquivo conforme quantos workers trabalham ao mesmo tempo (efeito do hardware)
- quanto o strptime pesa: mesma rotina pegando a hora por fatia da string

Uso: python scripts/medir_overheads.py   (precisa de dados/ gerado)
"""
import pickle
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from analisador_logs import nucleo  # noqa: E402

PASTA = "dados"


def cronometrado(caminho):
    t = time.perf_counter()
    nucleo.analisar_arquivo(caminho)
    return time.perf_counter() - t


def analisar_fatiando(caminho):
    """Igual a nucleo.analisar_arquivo, mas pega a hora com data[12:14] em vez de strptime."""
    r = nucleo.resultado_vazio()
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            m = nucleo.PADRAO.match(linha)
            if m is None:
                r["invalidas"] += 1
                continue
            ip, data, metodo, url, status, tamanho = m.groups()
            r["hora"][int(data[12:14])] += 1
            r["status"][status] += 1
            r["url"][f"{metodo} {url}"] += 1
            r["ip"][ip] += 1
            r["bytes"] += int(tamanho)
            r["bloqueados"] += ip in nucleo._bloqueados
    return r


if __name__ == "__main__":
    arquivos = nucleo.listar_arquivos(PASTA)
    nucleo.preparar(PASTA, False)

    for n in (2, 12):
        tempos = []
        for _ in range(3):
            t = time.perf_counter()
            with Pool(n, initializer=nucleo.preparar, initargs=(PASTA, False)) as p:
                p.map(abs, range(n))
            tempos.append(time.perf_counter() - t)
        print(f"Subir Pool({n}) + tarefa trivial: {statistics.median(tempos):.3f} s")

    r = nucleo.analisar_arquivo(arquivos[0])
    print(f"Pickle de 1 resultado: {len(pickle.dumps(r)) / 1024:.0f} KB")
    t = time.perf_counter()
    nucleo.juntar([r] * len(arquivos))
    print(f"juntar {len(arquivos)} parciais: {time.perf_counter() - t:.3f} s\n")

    for n in (1, 2, 4, 6, 12):
        with Pool(n, initializer=nucleo.preparar, initargs=(PASTA, False)) as p:
            p.map(cronometrado, arquivos[:n], chunksize=1)  # aquecimento
            tempos = p.map(cronometrado, arquivos[:n * 2], chunksize=1)
        print(f"{n:>2} workers ao mesmo tempo: {statistics.median(tempos):.3f} s por arquivo")

    t = time.perf_counter()
    original = nucleo.juntar(nucleo.analisar_arquivo(a) for a in arquivos)
    t_original = time.perf_counter() - t
    t = time.perf_counter()
    fatiado = nucleo.juntar(analisar_fatiando(a) for a in arquivos)
    t_fatiado = time.perf_counter() - t
    print(f"\nSequencial com strptime: {t_original:.2f} s | fatiando a hora: {t_fatiado:.2f} s "
          f"| resultados iguais: {fatiado == original}")
