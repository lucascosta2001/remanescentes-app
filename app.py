import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import qrcode
import os
import base64
import streamlit.components.v1 as components

# Pasta onde ficam guardadas as imagens dos QR codes
os.makedirs("qrcodes", exist_ok=True)

# --- Ligação à base de dados ---
conn = sqlite3.connect("remanescentes.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS remanescentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE,
    numero_encomenda TEXT,
    material TEXT,
    designacao TEXT,
    altura REAL,
    comprimento REAL,
    espessura REAL,
    localizacao TEXT,
    observacoes TEXT,
    data_criacao TEXT,
    ativo INTEGER DEFAULT 1
)
""")
conn.commit()

# --- LISTA DE MATERIAIS ---
MATERIAIS = ["Mármore", "Granito", "Quartzo", "Cerâmica", "Outros"]

st.title("Ferramenta de Gestão de Stock")

# =========================================================
# INSERIR NOVO REMANESCENTE
# =========================================================
st.header("Inserir novo remanescente")

with st.form("form_remanescente", clear_on_submit=True):
    material = st.selectbox("Material", MATERIAIS)
    designacao = st.text_input("Designação")
    numero_encomenda = st.text_input("Order Number")

    col1, col2, col3 = st.columns(3)
    with col2:
        altura = st.number_input("Altura (mm)", min_value=0.0, step=0.1)
    with col1:
        comprimento = st.number_input("Comprimento (mm)", min_value=0.0, step=0.1)
    with col3:
        espessura = st.number_input("Espessura (mm)", min_value=0.0, step=0.1)

    localizacao = st.text_input("Localização")
    observacoes = st.text_area("Observações")

    submitted = st.form_submit_button("Guardar remanescente")

# --- A partir daqui já está FORA do formulário ---
if submitted:
    if designacao.strip() == "":
        st.error("A designação é obrigatória.")
    else:
        cursor.execute("""
            INSERT INTO remanescentes
            (numero_encomenda, material, designacao, altura, comprimento, espessura, localizacao, observacoes, data_criacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (numero_encomenda, material, designacao, altura, comprimento, espessura, localizacao, observacoes,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        novo_id = cursor.lastrowid
        codigo_gerado = f"REM-{novo_id:04d}"
        cursor.execute("UPDATE remanescentes SET codigo = ? WHERE id = ?", (codigo_gerado, novo_id))
        conn.commit()

        st.success(f"Remanescente guardado com o código '{codigo_gerado}'!")

        # --- Gerar QR Code (versão para imprimir, com etiqueta) ---
        from PIL import Image, ImageDraw, ImageFont

        qr_data = f"Codigo: {codigo_gerado} | Material: {material} | Designacao: {designacao} | Localizacao: {localizacao}"

        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        largura_qr, altura_qr = qr_img.size
        altura_texto = 60
        etiqueta = Image.new("RGB", (largura_qr, altura_qr + altura_texto), "white")
        etiqueta.paste(qr_img, (0, 0))

        desenho = ImageDraw.Draw(etiqueta)
        try:
            fonte = ImageFont.truetype("arial.ttf", 28)
        except:
            fonte = ImageFont.load_default()

        texto = f"{codigo_gerado} - {designacao}"
        bbox = desenho.textbbox((0, 0), texto, font=fonte)
        largura_texto = bbox[2] - bbox[0]
        posicao_x = (largura_qr - largura_texto) // 2
        desenho.text((posicao_x, altura_qr + 15), texto, fill="black", font=fonte)

        caminho_qr = f"qrcodes/{codigo_gerado}.png"
        etiqueta.save(caminho_qr)

        st.image(caminho_qr, caption=f"QR Code - {codigo_gerado}", width=250)


        # --- Botão para imprimir diretamente ---
        with open(caminho_qr, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode()

        print_html = f"""
        <button onclick="imprimirQR()" style="padding:10px 20px; font-size:16px; cursor:pointer;">
            🖨️ Imprimir QR Code
        </button>
        <script>
        function imprimirQR() {{
            var janela = window.open('', '_blank');
            janela.document.write('<img src="data:image/png;base64,{img_base64}" style="width:100%;">');
            janela.document.close();
            janela.focus();
            setTimeout(function() {{ janela.print(); }}, 250);
        }}
        </script>
        """
        components.html(print_html, height=60)

# =========================================================
# PESQUISAR, EDITAR E ELIMINAR
# =========================================================
st.header("Remanescentes em stock")

pesquisa = st.text_input("Pesquisar (código, material, designação, encomenda ou localização)")

df = pd.read_sql_query("SELECT * FROM remanescentes WHERE ativo = 1", conn)

if pesquisa.strip() != "":
    termo = pesquisa.lower()
    df = df[
        df["codigo"].str.lower().str.contains(termo, na=False) |
        df["material"].str.lower().str.contains(termo, na=False) |
        df["designacao"].str.lower().str.contains(termo, na=False) |
        df["numero_encomenda"].fillna("").str.lower().str.contains(termo) |
        df["localizacao"].fillna("").str.lower().str.contains(termo)
    ]

st.caption("Faz duplo clique numa célula para editar. Para apagar uma linha, clica no quadrado à esquerda dela e depois no ícone do caixote do lixo. No fim, carrega em 'Guardar alterações'.")

df_editado = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
    hide_index=True,
    key="editor_remanescentes",
    column_config={
        "id": None,
        "ativo": None,
        "codigo": st.column_config.TextColumn("Código", disabled=True),
        "data_criacao": st.column_config.TextColumn("Data de criação", disabled=True),
        "material": st.column_config.SelectboxColumn("Material", options=MATERIAIS),
    }
)

if st.button("Guardar alterações"):
    ids_originais = set(df["id"])
    ids_editados = set(df_editado["id"].dropna())

    # Linhas que foram apagadas na tabela -> marcar como inativas
    ids_removidos = ids_originais - ids_editados
    for id_remov in ids_removidos:
        cursor.execute("UPDATE remanescentes SET ativo = 0 WHERE id = ?", (int(id_remov),))

    # Linhas que continuam -> atualizar com os valores editados
    for _, linha in df_editado.iterrows():
        if pd.isna(linha["id"]):
            continue  # ignora linhas novas criadas sem querer com o "+"
        cursor.execute("""
            UPDATE remanescentes
            SET material = ?, designacao = ?, numero_encomenda = ?, altura = ?, comprimento = ?, espessura = ?, localizacao = ?, observacoes = ?
            WHERE id = ?
        """, (linha["material"], linha["designacao"], linha["numero_encomenda"], linha["altura"], linha["comprimento"],
              linha["espessura"], linha["localizacao"], linha["observacoes"], int(linha["id"])))

    conn.commit()
    st.success("Alterações guardadas!")
    st.rerun()