import streamlit as st
import io
import re

st.set_page_config(page_title="TP2 - Pipeline de Texto", layout="wide")
st.title("Pipeline de Pré-Processamento de Texto")

# ── Bibliotecas opcionais ─────────────────────────────────────────────────────
try:
    import fitz
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from docx import Document
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

# ── Extração de texto ─────────────────────────────────────────────────────────
def extrair_texto(ficheiro):
    nome = ficheiro.name.lower()
    dados = ficheiro.read()

    if nome.endswith(".txt"):
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return dados.decode(enc)
            except:
                continue
        return dados.decode("utf-8", errors="replace")

    elif nome.endswith(".pdf"):
        if not PDF_OK:
            return "ERRO: instala pymupdf com:  pip install pymupdf"
        doc = fitz.open(stream=dados, filetype="pdf")
        return "\n".join(p.get_text() for p in doc)

    elif nome.endswith(".docx"):
        if not DOCX_OK:
            return "ERRO: instala python-docx com:  pip install python-docx"
        doc = Document(io.BytesIO(dados))
        return "\n".join(p.text for p in doc.paragraphs)

    return "ERRO: formato não suportado."

# ── Limpeza ───────────────────────────────────────────────────────────────────
def limpar_texto(texto, cfg):
    t = texto

    if cfg["artefactos"]:
        t = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]', '', t)
        t = re.sub(r'[_\-=~]{4,}', '', t)

    if cfg["encoding"]:
        subs = {'\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '--'}
        for k, v in subs.items():
            t = t.replace(k, v)

    if cfg["cabecalhos"]:
        from collections import Counter
        linhas = t.split('\n')
        contagem = Counter(l.strip() for l in linhas if l.strip())
        repetidas = {l for l, c in contagem.items() if c >= 3 and len(l) < 120}
        t = '\n'.join(l for l in linhas if l.strip() not in repetidas)

    if cfg["quebras"]:
        t = re.sub(r'(?<![.!?:])\n(?!\n)', ' ', t)

    if cfg["paragrafos"]:
        t = re.sub(r'\n{3,}', '\n\n', t)

    if cfg["espacos"]:
        t = '\n'.join(re.sub(r'[ \t]+', ' ', l).strip() for l in t.split('\n'))

    return t.strip()

# ── Detecção de idioma ────────────────────────────────────────────────────────
def detectar_idioma(texto):
    amostra = texto[:2000].lower()
    palavras = re.findall(r'\b\w+\b', amostra)
    pt = sum(1 for w in palavras if w in ['de','que','em','para','com','uma','por','não','como','mais'])
    en = sum(1 for w in palavras if w in ['the','of','and','to','in','is','it','for','on','with'])
    return "Português" if pt >= en else "English"

# ── Chunking ──────────────────────────────────────────────────────────────────
def dividir_chunks(texto, tamanho):
    paragrafos = re.split(r'\n{2,}', texto)
    chunks, atual = [], ""
    for p in paragrafos:
        if len(atual) + len(p) + 2 <= tamanho:
            atual += ("\n\n" if atual else "") + p
        else:
            if atual:
                chunks.append(atual.strip())
            atual = p
    if atual:
        chunks.append(atual.strip())
    return [c for c in chunks if c]

# ── Prompt ────────────────────────────────────────────────────────────────────
def gerar_prompt(chunk, idioma, tipo):
    tipos = {
        "Correção gramatical": f"You are a text normalization assistant. The text is in {idioma}. Correct grammar, punctuation and spacing. Return ONLY the corrected text.\n\nText:\n{chunk}",
        "Resumo":              f"You are a summarization assistant. The text is in {idioma}. Write a concise summary. Return ONLY the summary.\n\nText:\n{chunk}",
        "Estruturação":        f"You are a text structuring assistant. The text is in {idioma}. Organize into clear paragraphs. Return ONLY the restructured text.\n\nText:\n{chunk}",
    }
    return tipos[tipo]

# ══════════════════════════════════════════════════════════════════════════════
# INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Configuração da Pipeline")
    cfg = {
        "artefactos": st.checkbox("Remover artefactos", value=True),
        "encoding":   st.checkbox("Corrigir encoding", value=True),
        "cabecalhos": st.checkbox("Remover cabeçalhos/rodapés repetidos", value=True),
        "quebras":    st.checkbox("Corrigir quebras de linha", value=True),
        "paragrafos": st.checkbox("Reconstruir parágrafos", value=True),
        "espacos":    st.checkbox("Normalizar espaços", value=True),
    }
    st.divider()
    tamanho_chunk = st.slider("Tamanho do chunk (caracteres)", 300, 3000, 1000, 100)
    tipo_prompt = st.selectbox("Tipo de normalização", ["Correção gramatical", "Resumo", "Estruturação"])

# ── Etapa 1: Upload ───────────────────────────────────────────────────────────
st.header("1. Upload de Ficheiro")
ficheiro = st.file_uploader("Escolhe um ficheiro PDF, DOCX ou TXT", type=["pdf", "docx", "txt"])

if ficheiro:
    texto_bruto = extrair_texto(ficheiro)
    st.session_state["bruto"] = texto_bruto
    st.success(f"Ficheiro '{ficheiro.name}' carregado.")

if "bruto" in st.session_state:
    st.text_area("Texto extraído (bruto)", st.session_state["bruto"], height=200)
    st.caption(f"{len(st.session_state['bruto'])} caracteres · {len(st.session_state['bruto'].split())} palavras")

    st.divider()

    # ── Etapa 2: Limpeza ──────────────────────────────────────────────────────
    st.header("2. Limpeza e Pré-Processamento")

    if st.button("Executar Pipeline de Limpeza", type="primary"):
        st.session_state["limpo"] = limpar_texto(st.session_state["bruto"], cfg)

    if "limpo" in st.session_state:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Antes")
            st.text_area("", st.session_state["bruto"], height=250, key="antes")
            st.caption(f"{len(st.session_state['bruto'])} caracteres")
        with col2:
            st.subheader("Depois")
            st.text_area("", st.session_state["limpo"], height=250, key="depois")
            st.caption(f"{len(st.session_state['limpo'])} caracteres")

        st.divider()

        # ── Etapa 3: Chunks e Prompts ─────────────────────────────────────────
        st.header("3. Segmentação e Prompts")

        idioma = detectar_idioma(st.session_state["limpo"])
        st.info(f"Idioma detectado: **{idioma}**")

        chunks = dividir_chunks(st.session_state["limpo"], tamanho_chunk)
        st.write(f"**{len(chunks)} chunk(s)** gerados")

        for i, chunk in enumerate(chunks):
            with st.expander(f"Chunk {i+1} ({len(chunk)} caracteres)"):
                t1, t2 = st.tabs(["Texto", "Prompt"])
                with t1:
                    st.text_area("", chunk, height=150, key=f"c{i}")
                with t2:
                    prompt = gerar_prompt(chunk, idioma, tipo_prompt)
                    st.text_area("", prompt, height=200, key=f"p{i}")

        st.divider()
        st.download_button("⬇ Descarregar texto limpo", st.session_state["limpo"].encode(), "texto_limpo.txt")
