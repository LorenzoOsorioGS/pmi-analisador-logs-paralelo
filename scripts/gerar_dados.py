"""Gera a massa de teste: N arquivos de log (um por dia) + a lista de IPs bloqueados.

Seed fixa -> sempre os mesmos dados, então os tempos são comparáveis entre execuções.
Uso: python scripts/gerar_dados.py [--pasta dados] [--arquivos 60] [--linhas 60000]
"""
import argparse
import random
from datetime import date, timedelta
from pathlib import Path

URLS = ["/", "/login", "/produtos", "/produtos/123", "/carrinho",
        "/checkout", "/api/pedidos", "/admin", "/contato", "/static/app.js"]
METODOS = ["GET"] * 8 + ["POST"] * 2
STATUS = [200] * 85 + [301] * 3 + [404] * 7 + [500] * 5
MESES = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def main():
    p = argparse.ArgumentParser(description="Gera logs de acesso falsos para o benchmark.")
    p.add_argument("--pasta", default="dados")
    p.add_argument("--arquivos", type=int, default=60, help="quantidade de arquivos (dias)")
    p.add_argument("--linhas", type=int, default=60_000, help="linhas por arquivo")
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()

    random.seed(a.seed)
    pasta = Path(a.pasta)
    pasta.mkdir(exist_ok=True)
    for antigo in pasta.glob("acessos_*.log"):  # não misturar com uma geração anterior
        antigo.unlink()

    ips = [f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
           for _ in range(5000)]
    bloqueados = random.sample(ips, 100) + [f"172.16.{random.randint(0, 255)}.{random.randint(1, 254)}"
                                            for _ in range(20_000)]
    (pasta / "ips_bloqueados.txt").write_text("\n".join(bloqueados))

    for n in range(a.arquivos):
        dia = date(2026, 9, 1) + timedelta(days=n)
        data = f"{dia.day:02d}/{MESES[dia.month - 1]}/{dia.year}"
        segundos = sorted(random.randrange(86_400) for _ in range(a.linhas))  # log em ordem cronológica
        with open(pasta / f"acessos_{dia}.log", "w", encoding="utf-8") as f:
            for s in segundos:
                if random.random() < 0.001:
                    f.write("linha corrompida pela rotação do log\n")
                    continue
                f.write(f'{random.choice(ips)} - - [{data}:{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d} -0300] '
                        f'"{random.choice(METODOS)} {random.choice(URLS)} HTTP/1.1" '
                        f'{random.choice(STATUS)} {random.randint(200, 50_000)}\n')

    print(f"{a.arquivos} arquivos x {a.linhas:,} linhas gerados em '{pasta}/'")


if __name__ == "__main__":
    main()
