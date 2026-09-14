import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import qrcode
import os
import base64
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont

APP_URL = "https://remanescentes-app-yjfbvyavhczpmccg4mckur.streamlit.app"

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
    marca TEXT,
    designacao TEXT,
    altura REAL,
    comprimento REAL,
    espessura REAL,
    localizacao TEXT,
    observacoes TEXT,
    estado TEXT DEFAULT 'Disponível',
    data_criacao TEXT,
    data_uso TEXT,
    ativo INTEGER DEFAULT 1
)
""")
conn.commit()

# --- LISTAS DE OPÇÕES ---
MATERIAIS = ["Mármore", "Granito", "Quartzo", "Cerâmica", "Outros"]
MARCAS_QUARTZO = ["Silestone", "RoyalStone", "Compac", "Outros"]
MARCAS_CERAMICA = ["Dekton", "Ascale", "Neolith", "Outros"]
ESTADOS = ["Disponível", "Reservado"]

# Chaves dos campos do formulário de inserção, usadas para os limpar depois de guardar
CAMPOS_FORMULARIO = [
    "material_novo", "marca_novo", "designacao_novo", "encomenda_novo",
    "altura_novo", "comprimento_novo", "espessura_novo",
    "localizacao_novo", "estado_novo", "observacoes_novo"
]

st.title("Ferramenta de Gestão de Stock")

# --- Se a app foi aberta a partir de um QR code, mostra logo esse remanescente ---
codigo_pesquisado = st.query_params.get("codigo")

if codigo_pesquisado:
    cursor.execute("SELECT * FROM remanescentes WHERE codigo = ? AND ativo = 1", (codigo_pesquisado,))
    colunas = [desc[0] for desc in cursor.description]
    resultado = cursor.fetchone()

    if resultado:
        info = dict(zip(colunas, resultado))
        st.success(f"📦 Remanescente encontrado: {info['codigo']}")
        st.write(f"**Material:** {info['material']}")
        st.write(f"**Marca:** {info['marca']}")
        st.write(f"**Designação:** {info['designacao']}")
        st.write(f"**Dimensões:** {info['altura']} x {info['comprimento']} x {info['espessura']} mm")
        st.write(f"**Localização:** {info['localizacao']}")
        st.write(f"**Estado:** {info['estado']}")
        if info['observacoes']:
            st.write(f"**Observações:** {info['observacoes']}")
        st.divider()
    else:
        st.warning(f"Não foi encontrado nenhum remanescente ativo com o código '{codigo_pesquisado}'.")
        st.divider()

# =========================================================
# INSERIR NOVO REMANESCENTE
# =========================================================
st.header("Inserir novo remanescente")

if st.session_state.get("limpar_formulario"):
    for chave in CAMPOS_FORMULARIO:
        if chave in st.session_state:
            del st.session_state[chave]
    st.session_state["limpar_formulario"] = False

with st.container(border=True):
    col_mat, col_marca = st.columns(2)
    with col_mat:
        material = st.selectbox("Material", MATERIAIS, index=None, placeholder="Selecionar Material", key="material_novo")
    with col_marca:
        if material == "Quartzo":
            marca = st.selectbox("Marca", MARCAS_QUARTZO, key="marca_novo")
        elif material == "Cerâmica":
            marca = st.selectbox("Marca", MARCAS_CERAMICA, key="marca_novo")
        else:
            marca = st.text_input("Marca", key="marca_novo")

    col_desig, col_encomenda = st.columns(2)
    with col_desig:
        designacao = st.text_input("Designação", key="designacao_novo")
    with col_encomenda:
        numero_encomenda = st.text_input("Order Number", key="encomenda_novo")

    col1, col2, col3 = st.columns(3)
    with col2:
        altura = st.number_input("Altura (mm)", min_value=0, step=1, value=None, key="altura_novo")
    with col1:
        comprimento = st.number_input("Comprimento (mm)", min_value=0, step=1, value=None, key="comprimento_novo")
    with col3:
        espessura = st.number_input("Espessura (mm)", min_value=0, step=1, value=None, key="espessura_novo")

    col_loc, col_estado = st.columns(2)
    with col_loc:
        localizacao = st.text_input("Localização", key="localizacao_novo")
    with col_estado:
        estado = st.selectbox("Estado", ESTADOS, key="estado_novo")

    observacoes = st.text_area("Observações", key="observacoes_novo")

    submitted = st.button("Guardar remanescente")

if submitted:
    if material is None:
        st.error("Escolhe um material.")
    elif designacao.strip() == "":
        st.error("A designação é obrigatória.")
    elif altura is None or comprimento is None or espessura is None:
        st.error("Preenche todas as medidas (altura, comprimento e espessura).")
    else:
        cursor.execute("""
            INSERT INTO remanescentes
            (numero_encomenda, material, marca, designacao, altura, comprimento, espessura, localizacao, observacoes, estado, data_criacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (numero_encomenda, material, marca, designacao, altura, comprimento, espessura, localizacao, observacoes, estado,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        novo_id = cursor.lastrowid
        codigo_gerado = f"REM-{novo_id:04d}"
        cursor.execute("UPDATE remanescentes SET codigo = ? WHERE id = ?", (codigo_gerado, novo_id))
        conn.commit()

        # --- Gerar QR Code (versão para imprimir, com etiqueta) ---
        qr_data = f"{APP_URL}/?codigo={codigo_gerado}"

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

        # Guarda o código do último remanescente guardado, para o mostrar
        # depois do "rerun" (os campos do formulário limpam-se ao mesmo tempo)
        st.session_state["ultimo_codigo"] = codigo_gerado
        st.session_state["limpar_formulario"] = True
        st.rerun()

# --- Mostra o resultado do último remanescente guardado (QR code + imprimir) ---
if st.session_state.get("ultimo_codigo"):
    codigo_mostrar = st.session_state["ultimo_codigo"]
    caminho_qr = f"qrcodes/{codigo_mostrar}.png"

    if os.path.exists(caminho_qr):
        st.success(f"Remanescente guardado com o código '{codigo_mostrar}'!")
        st.image(caminho_qr, caption=f"QR Code - {codigo_mostrar}", width=250)

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

pesquisa = st.text_input("Pesquisar (código, material, marca, designação, encomenda ou localização)")

df = pd.read_sql_query("SELECT * FROM remanescentes WHERE ativo = 1", conn)

if pesquisa.strip() != "":
    termo = pesquisa.lower()
    df = df[
        df["codigo"].str.lower().str.contains(termo, na=False) |
        df["material"].str.lower().str.contains(termo, na=False) |
        df["marca"].fillna("").str.lower().str.contains(termo) |
        df["designacao"].str.lower().str.contains(termo, na=False) |
        df["numero_encomenda"].fillna("").str.lower().str.contains(termo) |
        df["localizacao"].fillna("").str.lower().str.contains(termo)
    ]

st.caption("Faz duplo clique numa célula para editar. Para apagar uma linha (marcar como usada), clica no quadrado à esquerda dela e depois no ícone do caixote do lixo. No fim, carrega em 'Guardar alterações'.")

df_editado = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
    hide_index=True,
    key="editor_remanescentes",
    column_config={
        "id": None,
        "ativo": None,
        "data_uso": None,
        "codigo": st.column_config.TextColumn("Código", disabled=True),
        "data_criacao": st.column_config.TextColumn("Data de criação", disabled=True),
        "material": st.column_config.SelectboxColumn("Material", options=MATERIAIS),
        "estado": st.column_config.SelectboxColumn("Estado", options=ESTADOS),
    }
)

if st.button("Guardar alterações"):
    ids_originais = set(df["id"])
    ids_editados = set(df_editado["id"].dropna())

    ids_removidos = ids_originais - ids_editados
    for id_remov in ids_removidos:
        cursor.execute(
            "UPDATE remanescentes SET ativo = 0, data_uso = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(id_remov))
        )

    for _, linha in df_editado.iterrows():
        if pd.isna(linha["id"]):
            continue
        cursor.execute("""
            UPDATE remanescentes
            SET material = ?, marca = ?, designacao = ?, numero_encomenda = ?, altura = ?, comprimento = ?, espessura = ?, localizacao = ?, observacoes = ?, estado = ?
            WHERE id = ?
        """, (linha["material"], linha["marca"], linha["designacao"], linha["numero_encomenda"], linha["altura"], linha["comprimento"],
              linha["espessura"], linha["localizacao"], linha["observacoes"], linha["estado"], int(linha["id"])))

    conn.commit()
    st.success("Alterações guardadas!")
    st.rerun()

# =========================================================
# HISTÓRICO DE REMANESCENTES USADOS
# =========================================================
st.header("Histórico de remanescentes usados")

df_historico = pd.read_sql_query(
    "SELECT codigo, material, marca, designacao, altura, comprimento, espessura, localizacao, data_criacao, data_uso "
    "FROM remanescentes WHERE ativo = 0 ORDER BY data_uso DESC",
    conn
)

if df_historico.empty:
    st.info("Ainda não há remanescentes usados.")
else:
    st.dataframe(df_historico, use_container_width=True, hide_index=True)