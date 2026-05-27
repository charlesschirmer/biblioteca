#!/usr/bin/env python3
"""
gerar_catalogo.py
Gera automaticamente o arquivo livros/catalogo.json
a partir dos PDFs encontrados na pasta /livros

Uso:
  python gerar_catalogo.py                  # escaneia ./livros
  python gerar_catalogo.py --pasta docs     # escaneia ./docs

Dependência opcional para ler metadados reais do PDF:
  pip install pypdf2          (ou: pip install PyMuPDF)
"""

import os, json, re, argparse
from pathlib import Path

# ── Mapeamento de palavras-chave para categoria ──
REGRAS_CATEGORIA = [
    (["romance", "conto", "poema", "literatura", "machado", "clarice", "guimarães"], "Literatura"),
    (["python", "javascript", "java", "código", "código", "software", "clean code", "design pattern", "api", "banco de dados", "programação"], "Tecnologia"),
    (["gestão", "administração", "liderança", "estratégia", "empresa", "negócio", "empreend"], "Gestão"),
    (["artigo", "paper", "estudo", "pesquisa", "análise", "revista"], "Artigos"),
    (["manual", "procedimento", "instrução", "norma", "política", "regulamento"], "Documentos"),
    (["lei", "decreto", "jurídico", "direito", "contrato", "jurisprud"], "Direito"),
    (["medicina", "saúde", "clínico", "farmac", "anatom", "patol"], "Medicina"),
    (["engenharia", "mecânica", "elétrica", "civil", "estrut"], "Engenharia"),
    (["história", "histór", "guerra", "revolução", "período", "século"], "História"),
    (["filosofia", "ética", "epistem", "ontolog", "kant", "hegel", "nietzsche"], "Filosofia"),
    (["econom", "finance", "investimento", "mercado", "fiscal"], "Economia"),
    (["educação", "pedagog", "ensino", "aprendiz", "escola", "universid"], "Educação"),
]

CORES_POR_CATEGORIA = {
    "Literatura":  "#8B5E3C",
    "Tecnologia":  "#2E6DA4",
    "Gestão":      "#2E8B57",
    "Artigos":     "#6A5ACD",
    "Documentos":  "#708090",
    "Direito":     "#8B3A3A",
    "Medicina":    "#C04040",
    "Engenharia":  "#D4762A",
    "História":    "#A07040",
    "Filosofia":   "#5F6898",
    "Economia":    "#3A8A6E",
    "Educação":    "#4A90A4",
}


def inferir_categoria(nome_arquivo):
    nome = nome_arquivo.lower()
    for palavras, categoria in REGRAS_CATEGORIA:
        for p in palavras:
            if p in nome:
                return categoria
    return "Documentos"


def formatar_titulo(nome_arquivo):
    """Transforma nome do arquivo em título legível."""
    stem = Path(nome_arquivo).stem
    # remove underscores, hífens extras, números de versão tipo _v2
    stem = re.sub(r'[_\-]+', ' ', stem)
    stem = re.sub(r'\bv\d+(\.\d+)?\b', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'\s+', ' ', stem).strip()
    return stem.title()


def tentar_ler_metadados_pdf(caminho):
    """Tenta extrair título e autor reais do PDF. Retorna dict ou None."""
    try:
        import PyPDF2
        with open(caminho, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            info = reader.metadata
            titulo = (info.get('/Title') or '').strip()
            autor  = (info.get('/Author') or '').strip()
            return {
                'titulo': titulo if titulo else None,
                'autor':  autor  if autor  else None,
            }
    except Exception:
        pass

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(caminho)
        meta = doc.metadata
        titulo = (meta.get('title') or '').strip()
        autor  = (meta.get('author') or '').strip()
        return {
            'titulo': titulo if titulo else None,
            'autor':  autor  if autor  else None,
        }
    except Exception:
        pass

    return None


def gerar_catalogo(pasta: str, saida: str, base_path: str = "livros"):
    pasta_path = Path(pasta)
    if not pasta_path.exists():
        print(f"❌ Pasta '{pasta}' não encontrada.")
        return

    pdfs = sorted(pasta_path.glob("**/*.pdf"))
    print(f"📂 Encontrados {len(pdfs)} PDFs em '{pasta}'")

    # Tenta carregar catálogo existente para preservar edições manuais
    existente = {}
    saida_path = Path(saida)
    if saida_path.exists():
        try:
            with open(saida_path, encoding='utf-8') as f:
                for item in json.load(f):
                    existente[item.get('arquivo', '')] = item
            print(f"📋 Catálogo existente carregado ({len(existente)} itens)")
        except Exception:
            pass

    catalogo = []
    for pdf in pdfs:
        # Caminho relativo usado na URL
        rel = str(pdf.relative_to(pasta_path.parent)).replace("\\", "/")
        chave = rel

        if chave in existente:
            # Preserva item existente (o usuário pode ter editado título/autor/desc)
            catalogo.append(existente[chave])
            print(f"  ✏️  Mantido (já existe): {pdf.name}")
            continue

        # Novo arquivo — inferir tudo
        meta = tentar_ler_metadados_pdf(pdf)
        titulo = (meta and meta['titulo']) or formatar_titulo(pdf.name)
        autor  = (meta and meta['autor'])  or ""
        categoria = inferir_categoria(pdf.name)
        cor = CORES_POR_CATEGORIA.get(categoria, "#c9a84c")

        item = {
            "arquivo":   chave,
            "titulo":    titulo,
            "autor":     autor,
            "categoria": categoria,
            "descricao": "",
            "capa":      "",
            "cor":       cor
        }
        catalogo.append(item)
        print(f"  ➕ Adicionado: {pdf.name} → [{categoria}] {titulo}")

    # Salva
    saida_path.parent.mkdir(parents=True, exist_ok=True)
    with open(saida_path, 'w', encoding='utf-8') as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Catálogo salvo em '{saida}' com {len(catalogo)} documentos.")
    print("💡 Edite o JSON para adicionar descrições, capas e ajustar categorias.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera catalogo.json para a Biblioteca Virtual")
    parser.add_argument("--pasta", default="livros", help="Pasta com os PDFs (padrão: livros)")
    parser.add_argument("--saida", default="livros/catalogo.json", help="Arquivo de saída")
    args = parser.parse_args()

    gerar_catalogo(args.pasta, args.saida)
