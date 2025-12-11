import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÃO DAS REGRAS (Foco em Horas de Call) ---

# Os valores são (Meta UP / Meta Manter) em HORAS acumuladas por ciclo (1 semana)
# A hierarquia segue a ordem: 1 (Menor) a 13 (Maior/Topo)
METAS_CALL = {
    # Posições 1 a 4 (Base)
    'f*ck':      {'ciclo': 1, 'meta_up': 14, 'meta_manter': 12},      # Posição 1
    '100%':      {'ciclo': 1, 'meta_up': 21, 'meta_manter': 14},      # Posição 2
    'woo':       {'ciclo': 1, 'meta_up': 28, 'meta_manter': 21},      # Posição 3
    'sex':       {'ciclo': 1, 'meta_up': 33, 'meta_manter': 28},      # Posição 4
    
    # Posição 5 (Note)
    'note':      {'ciclo': 1, 'meta_up': 38, 'meta_manter': 33},      # Posição 5 (Antigo '?')
    
    # Posições 6 e 7 (Desceram 1 nível)
    'aura':      {'ciclo': 1, 'meta_up': 42, 'meta_manter': 38},      # Posição 6 (Ocupa vaga do antigo '!')
    'all wild':  {'ciclo': 1, 'meta_up': 45, 'meta_manter': 42},      # Posição 7 (Ocupa vaga do antigo 'aura')
    
    # Posições 8 e 9 (Cute e Mello)
    'cute':      {'ciclo': 1, 'meta_up': 51, 'meta_manter': 45},      # Posição 8 (Desceu, ocupa vaga do antigo 'all wild')
    'mello':     {'ciclo': 1, 'meta_up': 56, 'meta_manter': 51},      # Posição 9 (Subiu, ocupa vaga do antigo 'cute')
    
    # Posições 10 a 12 (Desceram 1 nível)
    'void':      {'ciclo': 1, 'meta_up': 60, 'meta_manter': 56},      # Posição 10 (Ocupa vaga do antigo '$')
    'dawn':      {'ciclo': 1, 'meta_up': 64, 'meta_manter': 60},      # Posição 11 (Ocupa vaga do antigo 'void')
    'upper':     {'ciclo': 1, 'meta_up': 67, 'meta_manter': 64},      # Posição 12 (Ocupa vaga do antigo 'dawn')
    
    # Posição 13 (Topo)
    'Light':     {'ciclo': 1, 'meta_up': 72, 'meta_manter': 67},      # Posição 13 (Subiu, ocupa vaga do antigo 'upper')
}

# Lista ordenada do Menor para o Maior
CARGOS_LISTA = [
    'f*ck', '100%', 'woo', 'sex', 'note', 'aura', 'all wild', 
    'cute', 'mello', 
    'void', 'dawn', 'upper', 'Light'
]

# --- CONSTANTES DE COLUNAS ---
COLUNAS_PADRAO = [
    'usuario', 'user_id', 'cargo', 'situação', 'Semana_Atual', 
    'Horas_Acumuladas_Ciclo', 'Horas_Semana', 'Data_Ultima_Atualizacao', 
    'Horas_Total_Final'
]

col_usuario = 'usuario'
col_user_id = 'user_id' # ID do Usuário
col_cargo = 'cargo'
col_sit = 'situação'
col_sem = 'Semana_Atual'
col_horas_acum = 'Horas_Acumuladas_Ciclo'
col_horas_semana = 'Horas_Semana'
col_horas_final = 'Horas_Total_Final' 


# --- FUNÇÕES DE CONEXÃO E LÓGICA ---

@st.cache_resource(ttl=3600)
def get_gsheets_client():
    """Autoriza o cliente gspread."""
    if "gcp_service_account" not in st.secrets or "gsheets_config" not in st.secrets:
        st.error("Configuração de secrets ausente. Verifique 'gcp_service_account' e 'gsheets_config'.")
        return None
        
    try:
        creds_json = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(creds_json, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as e:
        st.session_state['gsheets_error'] = f"Erro de conexão com Google Sheets: {e}"
        return None

gc = get_gsheets_client()


@st.cache_data(ttl=5)
def carregar_dados():
    """Lê os dados da planilha Google (worksheet ESPECÍFICA para CALL)."""
    if gc is None:
        if 'gsheets_error' in st.session_state:
             st.error(st.session_state['gsheets_error'])
        return pd.DataFrame(columns=COLUNAS_PADRAO)
        
    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        SHEET_NAME = "Call_Ranking" 
        
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.worksheet(SHEET_NAME)
        
        data = worksheet.get_all_records()
        
        if not data:
            df = pd.DataFrame(columns=COLUNAS_PADRAO)
        else:
            df = pd.DataFrame(data)
        
        # Validação de Colunas e Inserção Segura do ID
        if col_user_id not in df.columns:
            if col_usuario in df.columns:
                loc = df.columns.get_loc(col_usuario) + 1
            else:
                loc = 1 
            df.insert(loc, col_user_id, 'N/A')
            
        df = df.reindex(columns=COLUNAS_PADRAO, fill_value='0.0')
        
        cols_to_convert = [col_sem, col_horas_acum, col_horas_semana, col_horas_final]
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        return df

    except Exception as e:
        st.error(f"ERRO: A conexão com a aba '{SHEET_NAME}' falhou. Verifique se a aba existe. ({e})")
        return pd.DataFrame(columns=COLUNAS_PADRAO)


def salvar_dados(df):
    """Sobrescreve a aba da planilha Google com o novo DataFrame."""
    if gc is None:
        st.error("Não foi possível salvar os dados: Conexão Sheets inativa.")
        return False

    st.info("Tentando salvar dados na planilha...")

    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        SHEET_NAME = "Call_Ranking" 
        
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.worksheet(SHEET_NAME)
        
        df_to_save = df[COLUNAS_PADRAO].astype(str)
        data = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
        
        worksheet.clear()
        worksheet.update(range_name='A1', values=data)
        
        st.cache_data.clear() 
        
        return True
        
    except Exception as e:
        st.error("ERRO CRÍTICO: Falha na Escrita ou Permissão Negada (403)!")
        st.exception(e)
        return False


def avaliar_situacao_call(cargo, horas_acumuladas):
    """Avalia o UP/MANTER/REBAIXAR no sistema de Call (Ciclo = 1 semana)."""
    meta = METAS_CALL[cargo]
    meta_up = meta['meta_up']
    meta_manter = meta['meta_manter']
    
    if horas_acumuladas >= meta_up:
        situacao = "UPADO"
    elif horas_acumuladas >= meta_manter:
        situacao = "MANTEVE"
    else:
        situacao = "REBAIXADO"
        
    return situacao


def limpar_campos_interface_call():
    """Limpa campos de input."""
    keys_to_delete = ['horas_input_update']
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]


# --- INTERFACE (STREAMLIT) ---

st.set_page_config(page_title="Sistema de Call Ranking", layout="wide")
st.title("Sistema de Call Ranking 📞")
st.markdown("##### Gerenciamento Semanal de UP baseado **apenas em Horas em Call**.")

df = carregar_dados()

# Variável de estado para o botão salvar
if 'salvar_button_clicked_call' not in st.session_state:
    st.session_state.salvar_button_clicked_call = False
if 'usuario_selecionado_id_call' not in st.session_state:
    st.session_state.usuario_selecionado_id_call = '-- Selecione o Membro --'

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Entrada de Dados e Gestão")
    
    # Ordem de abas invertida: Adicionar Membro | Upar
    tab_add, tab_update = st.tabs(["Adicionar Novo Membro", "Upar"])

    usuario_input = None
    cargo_inicial_default = CARGOS_LISTA.index('f*ck') if CARGOS_LISTA else 0

    # === ABA 1: ADICIONAR NOVO MEMBRO ===
    with tab_add:
        st.subheader("Registrar Novo Membro") 
        
        usuario_input_add = st.text_input("Nome do Novo Usuário", key='usuario_input_add')
        user_id_input_add = st.text_input("ID do Usuário (Opcional)", key='user_id_input_add', value='N/A')
        cargo_input_add = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=cargo_inicial_default, key='cargo_select_add')
        
        st.markdown("---")
        if st.button("Adicionar Membro", type="secondary", use_container_width=True):
            if usuario_input_add:
                if usuario_input_add in df[col_usuario].values:
                    st.error(f"O membro '{usuario_input_add}' já existe. Use a aba 'Upar'.")
                else:
                    novo_dado_add = {
                        col_usuario: usuario_input_add, 
                        col_user_id: user_id_input_add, 
                        col_cargo: cargo_input_add, 
                        col_sit: f"Em andamento (1/1)",
                        col_sem: 1,
                        col_horas_acum: 0.0, 
                        col_horas_semana: 0.0,
                        'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        col_horas_final: 0.0,
                    }
                    
                    df = pd.concat([df, pd.DataFrame([novo_dado_add])], ignore_index=True)
                    
                    if salvar_dados(df):
                        st.session_state.usuario_selecionado_id_call = usuario_input_add 
                        st.success(f"Membro **{usuario_input_add}** adicionado! Use a aba 'Upar' para registrar a primeira semana.")
                        st.rerun()
            else:
                 st.error("Digite o nome do novo membro.")


    # === ABA 2: ATUALIZAR/UPAR MEMBRO EXISTENTE ===
    with tab_update:
        
        opcoes_usuarios = ['-- Selecione o Membro --'] + sorted(df[col_usuario].unique().tolist()) 
        
        try:
            default_index = opcoes_usuarios.index(st.session_state.usuario_selecionado_id_call)
        except ValueError:
            default_index = 0
            
        usuario_selecionado = st.selectbox(
            "Selecione o Membro", 
            opcoes_usuarios, 
            index=default_index,
            key='select_user_update_call',
            on_change=lambda: st.session_state.__setitem__('usuario_selecionado_id_call', st.session_state.select_user_update_call)
        )
        
        st.session_state.usuario_selecionado_id_call = usuario_selecionado

        if usuario_selecionado != '-- Selecione o Membro --' and not df.empty and usuario_selecionado in df[col_usuario].values:
            
            dados_atuais = df[df[col_usuario] == usuario_selecionado].iloc[0]
            usuario_input = dados_atuais[col_usuario]
            user_id_atual = dados_atuais.get(col_user_id, 'N/A')
            
            cargo_atual_dados = dados_atuais[col_cargo]
            horas_acumuladas_anteriores = dados_atuais[col_horas_acum]
            semana_atual = dados_atuais[col_sem]
            
            # --- Bloco de Informação do Membro ---
            with st.container(border=True):
                if cargo_atual_dados in METAS_CALL:
                    
                    cargo_index_default = CARGOS_LISTA.index(cargo_atual_dados)
                    st.markdown(f"**Membro:** `{usuario_input}`")
                    
                    # DESTAQUE: ID do Usuário (VERDE, SEM FUNDO)
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 5px;">
                            <strong>ID do Usuário:</strong> <span style="color: #198754; font-weight: bold;">{user_id_atual}</span>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    if dados_atuais[col_sit] in ["UPADO", "REBAIXADO", "MANTEVE"]:
                        semana_input_value = 1
                        horas_acumuladas_anteriores = 0.0 
                        st.info(f"Ciclo finalizado. Registre a **Semana 1** do cargo **{cargo_atual_dados}**.")
                    else:
                        semana_input_value = 1 
                        
                else:
                    st.error(f"Cargo '{cargo_atual_dados}' desconhecido. Revertendo para 'f*ck'.")
                    cargo_index_default = CARGOS_LISTA.index('f*ck')
                    semana_input_value = 1
            # --- Fim Bloco de Informação do Membro ---
            
            st.divider()

            semana_input = st.number_input("Semana do Ciclo (1/1)", 
                                           min_value=1, max_value=1, value=semana_input_value, 
                                           key='semana_input_update')
            
            cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select_update')

            st.markdown("##### Horas em Call Semanal")
            horas_input = st.number_input("Horas em Call NESTA SEMANA", min_value=0.0, value=0.0, step=0.5, key='horas_input_update')
            
            st.markdown("---")
            if st.button("Salvar / Processar Semana", type="primary", key="save_update_button_call", use_container_width=True):
                st.session_state.salvar_button_clicked_call = True
            
        else:
            st.info("Selecione um membro acima para registrar a pontuação da semana.")
            usuario_input = None


    # ----------------------------------------------------
    # --- LÓGICA DE PROCESSAMENTO (EXECUÇÃO) ---
    # ----------------------------------------------------
    
    if st.session_state.salvar_button_clicked_call:
        st.session_state.salvar_button_clicked_call = False
        
        if usuario_input is not None:
            
            df_reloaded = carregar_dados() 
            dados_atuais = df_reloaded[df_reloaded[col_usuario] == st.session_state.select_user_update_call].iloc[0]
            
            usuario_input = dados_atuais[col_usuario]
            user_id_salvar = dados_atuais.get(col_user_id, 'N/A')
            
            horas_acumuladas_anteriores = dados_atuais[col_horas_acum] 
            cargo_input = st.session_state.cargo_select_update
            horas_input = st.session_state.horas_input_update 
            
            # --- Lógica de Cálculo e Avaliação ---
            
            # Zera se for novo ciclo, senão acumula
            if dados_atuais[col_sit] in ["UPADO", "REBAIXADO", "MANTEVE"]:
                 horas_acumuladas_total = horas_input
            else:
                 horas_acumuladas_total = horas_acumuladas_anteriores + horas_input
            
            situacao = avaliar_situacao_call(cargo_input, horas_acumuladas_total)

            novo_cargo = cargo_input 
            
            # Lógica de UP/REBAIXAR
            if situacao in ["UPADO", "REBAIXADO", "MANTEVE"]:
                nova_semana = 1
                novo_horas_acumuladas = 0.0 # Zera para o próximo ciclo
                
                if situacao == "UPADO":
                    indice_atual = CARGOS_LISTA.index(cargo_input)
                    if indice_atual < len(CARGOS_LISTA) - 1:
                        novo_cargo = CARGOS_LISTA[indice_atual + 1]
                    else:
                        novo_cargo = CARGOS_LISTA[-1] 
                        
                elif situacao == "REBAIXADO":
                    try:
                        indice_atual = CARGOS_LISTA.index(cargo_input)
                        if indice_atual > 0:
                            novo_cargo = CARGOS_LISTA[indice_atual - 1]
                        else:
                            novo_cargo = 'f*ck'
                    except ValueError:
                        novo_cargo = 'f*ck'
                else:
                    # MANTEVE
                    novo_cargo = cargo_input 
                    
            else:
                # Em andamento (embora com ciclo 1 isso raramente ocorra se meta não for atingida em 1 sem)
                # Se não atingiu meta em 1 semana, tecnicamente 'REBAIXADO' ou 'MANTEVE' dependendo da regra
                # Mas aqui, como o ciclo é 1, a função avaliar_situacao já retorna o veredito final.
                nova_semana = 1
                novo_horas_acumuladas = horas_acumuladas_total


            # Prepara os novos dados
            novo_dado = {
                col_usuario: usuario_input, 
                col_user_id: user_id_salvar, 
                col_cargo: novo_cargo, 
                col_sit: situacao,
                col_sem: nova_semana,
                col_horas_acum: round(novo_horas_acumuladas, 1), 
                col_horas_semana: round(horas_input, 1),
                'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                col_horas_final: round(dados_atuais[col_horas_final] + horas_input, 1), 
            }
            
            # Atualiza o DataFrame e salva
            df.loc[df[df[col_usuario] == usuario_input].index[0]] = novo_dado

            if salvar_dados(df):
                limpar_campos_interface_call()
                st.session_state.usuario_selecionado_id_call = usuario_input 
                
                msg_avanco = ""
                if situacao == "UPADO":
                    msg_avanco = f" (Subiu de nível!)"
                elif situacao == "REBAIXADO":
                    msg_avanco = f" (Desceu de nível)"
                
                st.success(f"Dados salvos! Situação: **{situacao}** | Próximo Cargo: **{novo_cargo}**{msg_avanco}")
                st.rerun()
        else:
            st.error("Selecione um membro válido antes de salvar.")

    
    # ----------------------------------------------------
    # --- NOVO BLOCO: VISUALIZAÇÃO DE METAS ---
    # ----------------------------------------------------
    st.markdown("---")
    
    metas_data = []
    for idx, (cargo, metas) in enumerate(METAS_CALL.items()):
        metas_data.append({
            "Cargo (#)": f"{cargo} ({idx+1})",
            "Meta UP (Horas)": metas['meta_up'],
            "Meta Manter (Horas)": metas['meta_manter']
        })
    df_metas = pd.DataFrame(metas_data)

    with st.expander("Tabela de Metas por Cargo (Horas Semanais) 📋", expanded=False):
        st.dataframe(df_metas, hide_index=True, use_container_width=True)
        
    # ----------------------------------------------------
    # --- FERRAMENTAS DE GESTÃO ---
    # ----------------------------------------------------
    st.subheader("Ferramentas de Gestão")
    with st.container(border=True):
        st.markdown("##### Remover Usuários")
        
        if 'confirm_reset' not in st.session_state:
            st.session_state.confirm_reset = False

        if not df.empty:
            opcoes_remocao = sorted(df[col_usuario].unique().tolist())
            usuario_a_remover = st.selectbox("Selecione o Usuário para Remover", ['-- Selecione --'] + opcoes_remocao, key='remove_user_select')
            
            if usuario_a_remover != '-- Selecione --':
                st.warning(f"Confirme a remoção de **{usuario_a_remover}**. Permanente.")
                
                if st.button(f"Confirmar Remoção de {usuario_a_remover}", type="secondary", key='final_remove_button', use_container_width=True):
                    df = df[df[col_usuario] != usuario_a_remover]
                    salvar_dados(df) 
                    st.success(f"Membro {usuario_a_remover} removido com sucesso!")
                    st.rerun()
        
        st.markdown("---")
        st.markdown("##### Reset Global da Tabela")
        
        if st.button("Resetar Tabela INTEIRA"):
            st.session_state.confirm_reset = True
            
        if st.session_state.confirm_reset:
            st.error("Tem certeza? Esta ação é IRREVERSÍVEL.")
            col_reset1, col_reset2 = st.columns(2)
            
            with col_reset1:
                if st.button("SIM, ZERAR TUDO", type="secondary", key='sim_reset'):
                    df_reset = pd.DataFrame(columns=df.columns) 
                    salvar_dados(df_reset) 
                    st.success("Tabela zerada com sucesso!")
                    st.session_state.confirm_reset = False
                    st.rerun()


# --- TABELA DE VISUALIZAÇÃO (COLUNA 2) ---
with col2:
    st.subheader("Tabela de Acompanhamento e Ranking")
    
    st.info(f"Total de Membros Registrados: **{len(df)}**")
    
    if not df.empty: 
        # Mapeamento para ordenação por cargo
        cargo_order = {cargo: i for i, cargo in enumerate(CARGOS_LISTA)}
        df_display = df.copy()
        df_display['cargo_rank'] = df_display[col_cargo].map(cargo_order)
        
        # Ordena: 1. Horas Totais (Decrescente), 2. Rank do Cargo (Decrescente/Maior Primeiro)
        df_display = df_display.sort_values(
            by=[col_horas_final, 'cargo_rank'], 
            ascending=[False, False]
        )
                                        
        st.dataframe(
            df_display.style.map(
                lambda x: 'background-color: #e6ffed; color: green' if 'UPADO' in str(x) else 
                          ('background-color: #ffe6e6; color: red' if 'REBAIXADO' in str(x) else 
                           ('background-color: #fffac2; color: #8a6d3b' if 'MANTEVE' in str(x) else '')),
                subset=[col_sit]
            ).format(precision=1),
            use_container_width=True,
            height=600,
            column_order=[col_usuario, col_user_id, col_cargo, col_sit, col_horas_acum, col_horas_semana, 'Data_Ultima_Atualizacao']
        )
    else:
        st.warning("Nenhum membro cadastrado. Adicione um na coluna ao lado.")

    st.divider()

    if not df.empty:
        st.subheader("Métricas Agregadas")
        df[col_horas_semana] = pd.to_numeric(df[col_horas_semana], errors='coerce').fillna(0)
        total_call = df[col_horas_semana].sum()
        
        st.metric("Total Horas Call (Última Rodada)", f"{total_call:.1f}")
