#!/usr/bin/env python3
"""
gerar_catalogo.py
Gera automaticamente livros/catalogo.json e extrai a capa (1ª página)
de cada PDF como imagem JPG na pasta capas/

Dependência obrigatória para extração de capas:
  pip install pymupdf

Uso:
  python gerar_catalogo.py                  # escaneia ./livros
  python gerar_catalogo.py --pasta docs     # escaneia ./docs
  python gerar_catalogo.py --sem-capa       # pula extração de capas
  python gerar_catalogo.py --recriar-capas  # força recriar todas as capas
"""

import os, json, re, argparse
from pathlib import Path

# ── Mapeamento de palavras-chave para categoria ──
REGRAS_CATEGORIA = [
    (["romance", "conto", "poema", "literatura", "machado", "clarice", "guimarães"], "Literatura"),
    (["python", "javascript", "java", "código", "software", "clean code", "design pattern", "api", "banco de dados", "programação"], "Tecnologia"),
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
    stem = Path(nome_arquivo).stem
    stem = re.sub(r'[_\-]+', ' ', stem)
    stem = re.sub(r'\bv\d+(\.\d+)?\b', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'\s+', ' ', stem).strip()
    return stem.title()


def extrair_capa(pdf_path: Path, pasta_capas: Path, recriar=False) -> str:
    """
    Renderiza a 1ª página do PDF como JPG e salva em pasta_capas/.
    Retorna o caminho relativo da imagem (para usar no JSON) ou '' em caso de falha.
    """
    nome_capa = pasta_capas / (pdf_path.stem + ".jpg")
    caminho_relativo = str(nome_capa).replace("\\", "/")

    # Já existe e não precisa recriar
    if nome_capa.exists() and not recriar:
        print(f"    🖼️  Capa já existe: {nome_capa.name}")
        return caminho_relativo

    try:
        import fitz  # PyMuPDF
        pasta_capas.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(pdf_path))
        pagina = doc[0]  # primeira página

        # Renderiza em 150 DPI — bom equilíbrio entre qualidade e tamanho
        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = pagina.get_pixmap(matrix=mat)

        # Recorta proporção de capa de livro (2:3) centralizada
        w, h = pix.width, pix.height
        alvo_h = int(w * 1.5)  # proporção 2:3
        if alvo_h < h:
            # PDF mais alto que 2:3 — recorta verticalmente pelo topo
            pix = pagina.get_pixmap(matrix=mat, clip=fitz.Rect(0, 0, w * 72/150, alvo_h * 72/150))

        pix.save(str(nome_capa))
        doc.close()
        print(f"    🖼️  Capa extraída: {nome_capa.name} ({pix.width}×{pix.height}px)")
        return caminho_relativo

    except ImportError:
        print("    ⚠️  PyMuPDF não instalado. Rode: pip install pymupdf")
        return ""
    except Exception as e:
        print(f"    ❌ Erro ao extrair capa de {pdf_path.name}: {e}")
        return ""


def tentar_ler_metadados_pdf(caminho):
    """Tenta extrair título e autor reais do PDF usando PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(str(caminho))
        meta = doc.metadata
        doc.close()
        titulo = (meta.get('title') or '').strip()
        autor  = (meta.get('author') or '').strip()
        return {
            'titulo': titulo if titulo else None,
            'autor':  autor  if autor  else None,
        }
    except Exception:
        pass
    return None


def injetar_no_html(catalogo: list, html_path: str = "index.html"):
    """
    Injeta o catálogo diretamente no index.html entre as marcações
    // CATALOGO_INICIO e // CATALOGO_FIM — sem necessidade de servidor.
    """
    html_file = Path(html_path)
    if not html_file.exists():
        print(f"  ⚠️  {html_path} não encontrado — pulando injeção no HTML.")
        return

    conteudo = html_file.read_text(encoding='utf-8')

    json_str = json.dumps(catalogo, ensure_ascii=False, indent=2)
    novo_bloco = f"// CATALOGO_INICIO\nconst CATALOGO_DADOS = {json_str};\n// CATALOGO_FIM"

    import re
    padrao = r'// CATALOGO_INICIO.*?// CATALOGO_FIM'
    if not re.search(padrao, conteudo, re.DOTALL):
        print(f"  ⚠️  Marcações CATALOGO_INICIO/FIM não encontradas em {html_path}.")
        return

    novo_conteudo = re.sub(padrao, novo_bloco, conteudo, flags=re.DOTALL)
    html_file.write_text(novo_conteudo, encoding='utf-8')
    print(f"  💉 Catálogo injetado em {html_path} ({len(catalogo)} itens)")


def gerar_catalogo(pasta: str, saida: str, sem_capa: bool = False, recriar_capas: bool = False):
    pasta_path = Path(pasta)
    if not pasta_path.exists():
        print(f"❌ Pasta '{pasta}' não encontrada.")
        return

    # Pasta de capas fica na raiz do projeto (ao lado de index.html)
    pasta_capas = Path("capas")

    pdfs = sorted(pasta_path.glob("**/*.pdf"))
    print(f"📂 Encontrados {len(pdfs)} PDFs em '{pasta}'")

    # Carrega catálogo existente para preservar edições manuais
    existente = {}
    audiobooks = []  # audiobooks não têm PDF — preservar sempre
    saida_path = Path(saida)
    if saida_path.exists():
        try:
            todos = json.load(open(saida_path, encoding='utf-8'))
            for item in todos:
                if item.get('tipo') == 'audiobook':
                    audiobooks.append(item)  # preserva separado
                else:
                    existente[item.get('arquivo', '')] = item
            print(f"📋 Catálogo existente: {len(existente)} livros + {len(audiobooks)} audiobooks")
        except Exception:
            pass

    catalogo = []
    for pdf in pdfs:
        rel = str(pdf.relative_to(pasta_path.parent)).replace("\\", "/")
        chave = rel

        # ── PDF já no catálogo ──
        if chave in existente:
            item = existente[chave]
            # Regenera capa se pedido ou se estava vazia
            if not sem_capa and (recriar_capas or not item.get('capa')):
                item['capa'] = extrair_capa(pdf, pasta_capas, recriar=recriar_capas)
            catalogo.append(item)
            print(f"  ✏️  Mantido: {pdf.name}")
            continue

        # ── PDF novo ──
        meta = tentar_ler_metadados_pdf(pdf)
        titulo    = (meta and meta['titulo']) or formatar_titulo(pdf.name)
        autor     = (meta and meta['autor'])  or ""
        categoria = inferir_categoria(pdf.name)
        # PDFs sem categoria específica viram "Livros" em vez de "Documentos"
        if categoria == "Documentos":
            categoria = "Livros"
        cor = CORES_POR_CATEGORIA.get(categoria, "#e8a020")

        capa = ""
        if not sem_capa:
            capa = extrair_capa(pdf, pasta_capas)

        item = {
            "tipo":      "livro",
            "arquivo":   chave,
            "titulo":    titulo,
            "autor":     autor,
            "categoria": categoria,
            "descricao": "",
            "capa":      capa,
            "cor":       cor,
            "youtube":   ""
        }
        catalogo.append(item)
        print(f"  ➕ Adicionado: {pdf.name} → [{categoria}] {titulo}")

    # Reincorporar audiobooks preservados
    catalogo = catalogo + audiobooks
    if audiobooks:
        print(f"  🎧 {len(audiobooks)} audiobook(s) preservado(s)")

    # Salva JSON
    saida_path.parent.mkdir(parents=True, exist_ok=True)
    with open(saida_path, 'w', encoding='utf-8') as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)

    # Injeta no index.html — funciona sem servidor
    injetar_no_html(catalogo)

    total_capas = sum(1 for i in catalogo if i.get('capa'))
    print(f"\n✅ Concluído!")
    print(f"   📚 {len(catalogo)} documentos no catálogo")
    print(f"   🖼️  {total_capas} capas geradas")
    print(f"   📄 JSON salvo em: {saida}")
    print(f"   💉 Catálogo injetado em: index.html")
    if not sem_capa:
        print(f"   🗂️  Capas salvas em: capas/")
    print(f"\n   Abra index.html diretamente no navegador — sem servidor necessário!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera catalogo.json com capas extraídas dos PDFs")
    parser.add_argument("--pasta",         default="livros",             help="Pasta com os PDFs")
    parser.add_argument("--saida",         default="livros/catalogo.json", help="Arquivo de saída")
    parser.add_argument("--sem-capa",      action="store_true",          help="Pula extração de capas")
    parser.add_argument("--recriar-capas", action="store_true",          help="Recria todas as capas mesmo as existentes")
    args = parser.parse_args()

    gerar_catalogo(args.pasta, args.saida, args.sem_capa, args.recriar_capas)
