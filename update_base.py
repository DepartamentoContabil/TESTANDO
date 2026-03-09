#!/usr/bin/env python3
"""
update_base.py
==============
Baixa o CSV publicado do Google Sheets, converte em JSON e injeta
no index.html substituindo o array BASE embutido.

Uso local:
    python update_base.py

Via GitHub Actions: chamado automaticamente pelo workflow.
"""

import csv
import json
import re
import sys
import urllib.request
from io import StringIO

# ── Configuração ───────────────────────────────────────────────────────────────
CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vS4SRwt-4cFsO1Tw7LSWvsKkB_8yHn1pxe0WECb1GniFGKFKHSItlxQ9fAl2T73tA_6pJuFElOx_OFv"
    "/pub?output=csv"
)
HTML_FILE = "index.html"

# Colunas-chave que identificam a linha de cabeçalho
KEY_COLS = {"EMPRESAS", "CNPJ", "RESPONSÁVEL", "STATUS DE FECHAMENTO"}

# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize(s: str) -> str:
    """Remove espaços múltiplos e faz trim."""
    return re.sub(r'\s+', ' ', s or '').strip()


def download_csv(url: str) -> str:
    print(f"📥 Baixando CSV de:\n   {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    # Google Sheets envia UTF-8 com BOM às vezes
    return raw.decode("utf-8-sig")


def parse_csv(text: str) -> list[dict]:
    """Lê o CSV, encontra a linha de cabeçalho, normaliza chaves e retorna JSON."""
    reader = csv.reader(StringIO(text))
    rows = list(reader)

    # Encontra linha de cabeçalho (primeiras 10 linhas)
    header_idx = -1
    for i, row in enumerate(rows[:10]):
        normed = {normalize(c).upper() for c in row}
        if len(KEY_COLS & normed) >= 3:
            header_idx = i
            break

    if header_idx == -1:
        first = " | ".join(rows[0][:8]) if rows else "(vazio)"
        raise ValueError(
            f"Cabeçalho não encontrado nas primeiras 10 linhas.\n"
            f"Primeira linha: {first}\n"
            "Verifique se está publicando a aba BASE como CSV."
        )

    # Normaliza cabeçalhos (colapsa espaços duplos)
    headers = [normalize(h) if normalize(h) else f"_col{i}"
               for i, h in enumerate(rows[header_idx])]

    print(f"   Cabeçalho na linha {header_idx + 1}: {' | '.join(h for h in headers if not h.startswith('_col'))}")

    records = []
    for row in rows[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue  # pula linhas vazias
        obj = {}
        for j, h in enumerate(headers):
            obj[h] = row[j].strip() if j < len(row) else ""
        empresa = obj.get("EMPRESAS", "").strip()
        if empresa:
            records.append(obj)

    return records


def inject_base(html_path: str, records: list[dict]) -> None:
    """Substitui o array BASE no index.html pelos novos registros."""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_json = json.dumps(records, ensure_ascii=False, separators=(",", ":"))

    # Regex: substitui   const BASE  = [...];
    # Aceita variações de espaços entre BASE e =
    pattern = r'(const\s+BASE\s*=\s*)\[.*?\](;)'
    replacement = rf'\g<1>{new_json}\g<2>'

    new_content, n = re.subn(pattern, replacement, content, count=1, flags=re.DOTALL)

    if n == 0:
        raise ValueError(
            "Marcador 'const BASE = [...]' não encontrado no index.html.\n"
            "Verifique se a variável ainda se chama BASE."
        )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"   ✅ BASE atualizada no {html_path} ({len(records)} empresas)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    try:
        csv_text = download_csv(CSV_URL)
        records  = parse_csv(csv_text)
        print(f"   📊 {len(records)} empresas encontradas")
        inject_base(HTML_FILE, records)
        print("\n🎉 index.html atualizado com sucesso!")
    except Exception as e:
        print(f"\n❌ Erro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
