import streamlit as st
import pandas as pd
import random
from datetime import datetime
import sqlite3
import os
import base64

# Nome do arquivo do banco de dados SQLite
DB_FILE = "sorteio.db"


# Função para inicializar o banco de dados
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Verifica se a tabela 'registros' existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registros'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT,
                nome_usuario TEXT,
                numeros TEXT
            )
        ''')

    # Verifica se a tabela 'texto_publico' existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='texto_publico'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE texto_publico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                texto TEXT
            )
        ''')
        # Insere um texto padrão na tabela texto_publico
        cursor.execute('INSERT INTO texto_publico (texto) VALUES ("Insira aqui o texto que deseja exibir na página pública.")')

    conn.commit()
    conn.close()


# Função para carregar dados do banco de dados
def load_data():
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT data_hora, nome_usuario, numeros FROM registros"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# Função para salvar um novo registro no banco de dados
def save_registro(nome, numeros):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    cursor.execute('''
        INSERT INTO registros (data_hora, nome_usuario, numeros)
        VALUES (?, ?, ?)
    ''', (agora, nome, numeros))
    conn.commit()
    conn.close()


# Função para limpar todos os registros do banco de dados
def clear_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM registros")
    conn.commit()
    conn.close()


# Função para carregar o texto público
def load_texto_publico():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT texto FROM texto_publico ORDER BY id DESC LIMIT 1")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else "Nenhuma mensagem disponível."


# Função para salvar o texto público
def save_texto_publico(texto):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO texto_publico (texto) VALUES (?)", (texto,))
    conn.commit()
    conn.close()


# Session state initialization
if 'registros' not in st.session_state:
    init_db()  # Inicializa o banco de dados
    st.session_state.registros = load_data()  # Carrega os dados do banco de dados
if 'sorteados' not in st.session_state:
    st.session_state.sorteados = []
if 'admin_logado' not in st.session_state:
    st.session_state.admin_logado = False
if 'mostrar_login' not in st.session_state:
    st.session_state.mostrar_login = False
if 'limpar_formulario' not in st.session_state:
    st.session_state.limpar_formulario = False

# Admin password
ADMIN_SENHA = "admin123"


def registrar(nome, numeros):
    """Register participant with name and chosen numbers"""
    if not nome or not numeros:
        return False, "⚠️ Preencha todos os campos."

    try:
        numeros_lista = [int(n.strip()) for n in numeros.split(",") if n.strip().isdigit()]
        if not numeros_lista:
            return False, "⚠️ Digite pelo menos um número válido."
    except:
        return False, "⚠️ Formato inválido. Use números separados por vírgula (ex: 1,2,3)."

    # Check for duplicate numbers
    todos_escolhidos = set()
    for nums in st.session_state.registros["numeros"]:
        if isinstance(nums, str):
            todos_escolhidos.update([int(n.strip()) for n in nums.split(",")])

    indisponiveis = [n for n in numeros_lista if n in todos_escolhidos]
    if indisponiveis:
        return False, f"⚠️ Número(s) {', '.join(map(str, indisponiveis))} já está(ão) em uso. Escolha outros."

    # Add new record
    numeros_str = ",".join(map(str, numeros_lista))
    save_registro(nome, numeros_str)  # Salva o registro no banco de dados
    st.session_state.registros = load_data()  # Recarrega os dados do banco de dados
    return True, f"✅ Registro realizado com sucesso!\nNome: {nome}\nNúmeros: {numeros_str}"


def realizar_sorteio(qtde_numeros):
    """Perform the raffle drawing"""
    if qtde_numeros <= 0:
        return "⚠️ Quantidade inválida.", None, None

    # Get all unique numbers
    todos_numeros = []
    participantes = {}

    for _, row in st.session_state.registros.iterrows():
        nums = row["numeros"]
        if isinstance(nums, str):
            numeros_usuario = [int(n.strip()) for n in nums.split(",")]
            todos_numeros.extend(numeros_usuario)
            for num in numeros_usuario:
                participantes[num] = row["nome_usuario"]

    if not todos_numeros:
        return "⚠️ Nenhum número registrado.", None, None

    numeros_unicos = list(set(todos_numeros))

    if qtde_numeros > len(numeros_unicos):
        return f"⚠️ Só há {len(numeros_unicos)} números únicos registrados.", None, None

    st.session_state.sorteados = random.sample(numeros_unicos, qtde_numeros)
    st.session_state.sorteados.sort()

    # Prepare results
    resultado = "🎉 Números sorteados:\n\n"
    for num in st.session_state.sorteados:
        resultado += f"🏆 Número {num} - {participantes.get(num, 'Não atribuído')}\n"

    df_resultado = pd.DataFrame({
        "Número": st.session_state.sorteados,
        "Ganhador": [participantes.get(num, "Não atribuído") for num in st.session_state.sorteados]
    })

    return resultado, ", ".join(map(str, st.session_state.sorteados)), df_resultado


# Page configuration
st.set_page_config(page_title="Sistema de Sorteio", layout="wide")

# Public Page
if not st.session_state.admin_logado:
    st.title("🎯 Participe do Sorteio!")

    # Carrega o texto público
    texto_publico = load_texto_publico()
    if texto_publico:
        st.markdown(f"📝 **Mensagem do Administrador:** {texto_publico}")

    with st.form("form_registro"):
        # Campos de entrada
        nome = st.text_input("Seu Nome", key="nome",
                             value="" if st.session_state.get("limpar_formulario", False) else "")
        numeros = st.text_input("Números desejados (separados por vírgula, ex: 1,2,3)", key="numeros",
                                value="" if st.session_state.get("limpar_formulario", False) else "")

        # Botão de envio
        submitted = st.form_submit_button("Enviar")

        if submitted:
            # Registrar os dados e obter resultado
            sucesso, mensagem = registrar(nome, numeros)

            if sucesso:
                st.success(mensagem)  # Exibe mensagem de sucesso
                # Limpa os campos após o envio bem-sucedido
                st.session_state.limpar_formulario = True  # Ativa o estado de limpeza
            else:
                st.error(mensagem)  # Exibe mensagem de erro
                st.session_state.limpar_formulario = False  # Mantém os campos preenchidos

    st.markdown("---")
    if st.button("🔒 Acessar Área Administrativa"):
        st.session_state.mostrar_login = True
        st.rerun()

# Admin Login Page
if not st.session_state.admin_logado and st.session_state.mostrar_login:
    st.title("🔐 Área do Administrador")

    senha = st.text_input("Senha", type="password")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Entrar"):
            if senha == ADMIN_SENHA:
                st.session_state.admin_logado = True
                st.session_state.mostrar_login = False
                st.rerun()
            else:
                st.error("Senha incorreta!")

    with col2:
        if st.button("Voltar"):
            st.session_state.mostrar_login = False
            st.rerun()

# Admin Area
if st.session_state.admin_logado:
    st.title("👨‍💼 Área Administrativa")

    if st.button("← Sair"):
        st.session_state.admin_logado = False
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visualização", "⚙️ Ferramentas", "🎰 Sorteio", "📝 Editar Texto Público"])

    with tab1:
        st.header("Registros de Participantes")
        st.dataframe(st.session_state.registros, use_container_width=True)

    with tab2:
        st.header("Ferramentas Administrativas")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Exportar Dados")
            csv = st.session_state.registros.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="registros.csv">Baixar CSV</a>'
            st.markdown(href, unsafe_allow_html=True)

        with col2:
            st.subheader("Limpar Dados")
            confirmacao = st.checkbox("Confirmar limpeza de todos os dados")
            if st.button("🗑️ Limpar Tudo", disabled=not confirmacao):
                clear_data()  # Limpa os dados no banco de dados
                st.session_state.registros = load_data()  # Recarrega os dados do banco de dados
                st.success("Base de dados limpa com sucesso!")
                st.rerun()

    with tab3:
        st.header("Realizar Sorteio")

        qtde = st.number_input("Quantidade de números para sortear", min_value=1, value=1, step=1)

        if st.button("🎯 Sortear"):
            resultado, numeros_str, df_resultado = realizar_sorteio(qtde)

            st.subheader("Resultado do Sorteio")
            st.text(resultado)

            st.text_input("Números sorteados (para cópia)", numeros_str, key="numeros_sorteados")

            st.dataframe(df_resultado, use_container_width=True)

    with tab4:
        st.header("Editar Texto Público")
        texto_atual = load_texto_publico()
        novo_texto = st.text_area("Texto Público", value=texto_atual, height=150)

        if st.button("Salvar Texto"):
            save_texto_publico(novo_texto)
            st.success("Texto público atualizado com sucesso!")