"""Núcleo do analisador: a rotina que processa UM item (um arquivo de log).

Este é o módulo que cada worker do Pool importa. Por isso tudo aqui fica no
nível do módulo: o pickle só consegue mandar para outro processo funções "de topo".
"""
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

# Uma linha do log (formato "common log" do Apache/Nginx):
# 10.1.2.3 - - [01/Sep/2026:13:45:12 -0300] "GET /produtos HTTP/1.1" 200 5120
PADRAO = re.compile(r'(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) [^"]*" (\d{3}) (\d+)')
FORMATO_DATA = "%d/%b/%Y:%H:%M:%S %z"

# Recursos carregados UMA vez por processo (no paralelo: initializer= do Pool)
_bloqueados = frozenset()
_mostrar_pid = True


def preparar(pasta, mostrar_pid=True):
    """Carrega a lista de IPs bloqueados para a memória deste processo."""
    global _bloqueados, _mostrar_pid
    _bloqueados = frozenset(Path(pasta, "ips_bloqueados.txt").read_text().split())
    _mostrar_pid = mostrar_pid


def resultado_vazio():
    return {"status": Counter(), "url": Counter(), "ip": Counter(), "hora": Counter(),
            "bytes": 0, "bloqueados": 0, "invalidas": 0}


def analisar_arquivo(caminho):
    """ROTINA PESADA: lê um arquivo de log e contabiliza linha por linha."""
    r = resultado_vazio()
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            m = PADRAO.match(linha)
            if m is None:  # linha corrompida: conta e segue
                r["invalidas"] += 1
                continue
            ip, data, metodo, url, status, tamanho = m.groups()
            r["hora"][datetime.strptime(data, FORMATO_DATA).hour] += 1
            r["status"][status] += 1
            r["url"][f"{metodo} {url}"] += 1
            r["ip"][ip] += 1
            r["bytes"] += int(tamanho)
            r["bloqueados"] += ip in _bloqueados
    return r


def tarefa(item):
    """Igual ao tarefa(n) da aula: processa um item e mostra qual PID fez o trabalho."""
    n, caminho = item
    resultado = analisar_arquivo(caminho)
    if _mostrar_pid:
        print(f"Tarefa {n} finalizada com PID: {os.getpid()}")
    return resultado


def juntar(parciais):
    """Etapa de 'reduce': soma os parciais (Counter + Counter, int + int)."""
    total = resultado_vazio()
    for p in parciais:
        for chave in total:
            total[chave] += p[chave]
    return total


def listar_arquivos(pasta):
    arquivos = sorted(str(p) for p in Path(pasta).glob("acessos_*.log"))
    if not arquivos:
        raise SystemExit(f"Nenhum log em '{pasta}'. Rode antes: python scripts/gerar_dados.py")
    return arquivos


def salvar(resultado, caminho):
    """Grava o relatório em JSON (sempre chamado pelo processo principal)."""
    Path(caminho).parent.mkdir(exist_ok=True)
    Path(caminho).write_text(json.dumps(resultado, indent=1, sort_keys=True), encoding="utf-8")


def imprimir_resumo(r):
    total = sum(r["status"].values())
    print(f"Requisições: {total:,} | tráfego: {r['bytes'] / 1e9:.2f} GB | "
          f"de IPs bloqueados: {r['bloqueados']:,} | linhas inválidas: {r['invalidas']:,}")
    print("Status:", ", ".join(f"{s}={q / total:.1%}" for s, q in sorted(r["status"].items())))
    print("Top 3 URLs:", r["url"].most_common(3))
