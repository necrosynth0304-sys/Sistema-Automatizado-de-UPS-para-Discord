import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ==============================================================================
# --- 1. CONFIGURAÇÃO DE ESTÉTICA (DARK/GOTHIC) ---
# ==============================================================================
def configurar_estetica_visual():
    background_url = "https://images4.alphacoders.com/740/thumb-1920-740591.png"

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&display=swap');

        /* === 1. FUNDO === */
        .stApp {{
            background-color: #000000 !important;
            background-image: url("{background_url}") !important;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            background-attachment: fixed !important;
        }}

        /* === 2. LIMPEZA DE INTERFACE === */
        [data-testid="stElementToolbar"] {{ display: none !important; }}
        button[title="View fullscreen"] {{ display: none !important; }}
        label[data-testid="stLabel"] {{ display: none !important; }}

        /* === 3. DROPDOWNS E MENUS === */
        div[data-baseweb="select"] > div {{
            background-color: #000000 !important;
            color: #ffffff !important;
            border: 1px solid #ffffff !important;
        }}
        div[data-baseweb="menu"], div[data-baseweb="popover"], ul {{
            background-color: #000000 !important;
            border: 1px solid #333 !important;
        }}
        li[role="option"] {{
            background-color: #000000 !important;
            color: #ffffff !important;
        }}
        li[role="option"]:hover, li[role="option"][aria-selected="true"] {{
            background-color: #333333 !important;
            color: #ff0000 !important;
        }}

        /* === 4. CAIXAS DE AVISO (PRETAS) === */
        div[data-testid="stAlert"] {{
            background-color: #000000 !important;
            color: #ffffff !important;
            border: 1px solid #ffffff !important;
        }}
        div[data-testid="stAlert"] > div {{ background-color: transparent !important; }}
        div[data-testid="stAlert"] svg, div[data-testid="stAlert"] p {{
            fill: #ffffff !important;
            color: #ffffff !important;
        }}

        /* === 5. TABELAS (PRETO TOTAL) === */
        div[data-testid="stDataFrame"] {{
            background-color: #000000 !important;
            border: 1px solid #ffffff !important;
        }}
        /* Cabeçalho */
        [data-testid="stDataFrame"] th, [data-testid="stDataFrame"] thead tr {{
            background-color: #050505 !important; 
            color: #ffffff !important;
            border-bottom: 1px solid #ffffff !important;
        }}
        /* Células */
        [data-testid="stDataFrame"] td {{
            background-color: #000000 !important;
            color: #dddddd !important;
            border-bottom: 1px solid #222 !important;
        }}

        /* === 6. TIPOGRAFIA GERAL === */
        h1, h2, h3, h4, h5, h6 {{
            color: #ffffff !important;
            font-family: 'UnifrakturMaguntia', cursive !important;
            text-shadow: 2px 2px 0px #000000;
        }}
        p, label, span, div, caption {{
            color: #eeeeee !important;
            font-family: 'Courier New', monospace !important;
        }}

        /* === 7. INPUTS E BOTÕES === */
        .stTextInput input, .stNumberInput input {{
            background-color: #111111 !important;
            color: #ffffff !important;
            border: 1px solid #ffffff !important;
        }}
        button {{
            background-color: #000000 !important;
            color: #ff0000 !important;
            border: 2px solid #ff0000 !important;
            font-family: 'UnifrakturMaguntia', cursive !important;
            font-size: 18px !important;
            transition: 0.3s;
        }}
        button:hover {{
            background-color: #ff0000 !important;
            color: #000000 !important;
            box-shadow: 0 0 15px #ff0000;
            border-color: #ffffff !important;
        }}
        
        [data-testid="stMetricValue"] {{
            color: #ff0000 !important;
            font-family: 'UnifrakturMaguntia', cursive !important;
        }}
        
        /* Container Geral */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: rgba(0,0,0,0.85) !important;
            border: 1px solid #444 !important;
            border-radius: 5px;
        }}
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# --- 2. DADOS E LÓGICA (NOVA HIERARQUIA 1 > note) ---
# ==============================================================================

# Definição das Metas (Calculadas de ~700 a ~11.000)
METAS_PONTUACAO = {
    'note':  {'ciclo': 1, 'meta_up': 14,  'meta_manter': 11},  # ~700 msgs
    'sex':   {'ciclo': 1, 'meta_up': 24,  'meta_manter': 19},  # ~1.200 msgs
    'aura':  {'ciclo': 1, 'meta_up': 40,  'meta_manter': 32},  # ~2.000 msgs
    'cute':  {'ciclo': 1, 'meta_up': 64,  'meta_manter': 51},  # ~3.200 msgs
    'upper': {'ciclo': 1, 'meta_up': 96,  'meta_manter': 77},  # ~4.800 msgs
    'damn':  {'ciclo': 1, 'meta_up': 130, 'meta_manter': 104}, # ~6.500 msgs
    '3':     {'ciclo': 1, 'meta_up': 160, 'meta_manter': 128}, # ~8.000 msgs
    '2':     {'ciclo': 1, 'meta_up': 190, 'meta_manter': 152}, # ~9.500 msgs
    '1':     {'ciclo': 1, 'meta_up': 220, 'meta_manter': 176}, # ~11.000 msgs
}

# Lista ordenada do MENOR para o MAIOR (para o código saber qual é o próximo)
CARGOS_LISTA = [
    'note', 'sex', 'aura', 'cute',
    'upper', 'damn', '3', '2', '1'
]

MENSAGENS_POR_PONTO = 50
SHEET_NAME_PRINCIPAL = "dados sistema"

COLUNAS_PADRAO = [
    'usuario', 'user_id', 'cargo', 'situação', 'Semana_Atual',
    'Pontos_Acumulados_Ciclo', 'Pontos_Semana', 'Bonus_Semana',
    'Multiplicador_Individual', 'Data_Ultima_Atualizacao', 'Pontos_Total_Final'
]

col_usuario = 'usuario'
col_user_id = 'user_id'
col_cargo = 'cargo'
col_sit = 'situação'
col_sem = 'Semana_Atual'
col_pontos_acum = 'Pontos_Acumulados_Ciclo'
col_pontos_sem = 'Pontos_Semana'
col_bonus_sem = 'Bonus_Semana'
col_mult_ind = 'Multiplicador_Individual'
col_pontos_final = 'Pontos_Total_Final'

@st.cache_resource(ttl=3600)
def get_gsheets_client():
    if "gcp_service_account" not in st.secrets or "gsheets_config" not in st.secrets:
        st.error("Secrets não configurados.")
        return None
    try:
        creds_json = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(creds_json, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Erro Conexão: {e}")
        return None

gc = get_gsheets_client()

@st.cache_data(ttl=5)
def carregar_dados(sheet_name):
    if gc is None: return pd.DataFrame(columns=COLUNAS_PADRAO)
    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        if not data: df = pd.DataFrame(columns=COLUNAS_PADRAO)
        else: df = pd.DataFrame(data)
        
        if col_user_id not in df.columns:
            if col_usuario in df.columns: loc = df.columns.get_loc(col_usuario) + 1
            else: loc = 1 
            df.insert(loc, col_user_id, 'N/A')
        
        df = df.reindex(columns=COLUNAS_PADRAO, fill_value='0.0')
        df[col_usuario] = df[col_usuario].astype(str)
        
        cols_num = [col_sem, col_pontos_acum, col_pontos_sem, col_bonus_sem, col_mult_ind, col_pontos_final]
        for col in cols_num:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro carregar: {e}")
        return pd.DataFrame(columns=COLUNAS_PADRAO)

def salvar_dados(df, sheet_name):
    if gc is None: return False
    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.worksheet(sheet_name)
        df_to_save = df[COLUNAS_PADRAO].astype(str)
        data = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
        worksheet.clear()
        worksheet.update(range_name='A1', values=data)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro salvar: {e}")
        return False

def calcular_pontuacao_semana(pontos_base, bonus, mult_ind):
    return round((pontos_base + bonus) * mult_ind, 1)

def avaliar_situacao(cargo, semana_atual, pontos_acumulados):
    meta = METAS_PONTUACAO.get(cargo)
    if not meta: return "ERRO CARGO", 0 # Proteção contra cargos antigos
    if pontos_acumulados >= meta['meta_up']: return "UPADO", 0
    elif pontos_acumulados >= meta['meta_manter']: return "MANTEVE", 0
    else: return "REBAIXADO", 0

def limpar_campos_interface():
    for key in ['mensagens_input', 'bonus_input']:
        if key in st.session_state: del st.session_state[key]

# ==============================================================================
# --- 3. INTERFACE ---
# ==============================================================================
st.set_page_config(page_title="Sistema de Ups", layout="wide")
configurar_estetica_visual()

st.title("Sistema de Ups")
st.markdown("##### Painel de Gerenciamento")

df = carregar_dados(SHEET_NAME_PRINCIPAL) 

if 'salvar_button_clicked' not in st.session_state: st.session_state.salvar_button_clicked = False
if 'usuario_selecionado_id' not in st.session_state: st.session_state.usuario_selecionado_id = '-- Selecione o Membro --'

col_ferramentas, col_upar, col_ranking = st.columns([1, 1.2, 2])
cargo_inicial_default = 0 # Define note como padrão
usuario_input_upar = None

# === COLUNA 1: FERRAMENTAS ===
with col_ferramentas:
    st.subheader("Ferramentas")
    
    with st.container(border=True):
        st.markdown("##### ➕ Adicionar Membro")
        usuario_input_add = st.text_input("Nome", key='usuario_input_add')
        user_id_input_add = st.text_input("ID (Opcional)", key='user_id_input_add', value='N/A')
        cargo_input_add = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=cargo_inicial_default, key='cargo_select_add')
        
        if st.button("Adicionar ao Sistema", type="primary", use_container_width=True):
            if usuario_input_add:
                if usuario_input_add in df[col_usuario].astype(str).values:
                    st.error(f"'{usuario_input_add}' já existe.")
                else:
                    novo = {col_usuario: usuario_input_add, col_user_id: user_id_input_add, col_cargo: cargo_input_add, 
                            col_sit: "Em andamento (1/1)", col_sem: 1, col_pontos_acum: 0.0, col_pontos_sem: 0.0, 
                            col_bonus_sem: 0.0, col_mult_ind: 1.0, 'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                            col_pontos_final: 0.0}
                    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                        st.session_state.usuario_selecionado_id = usuario_input_add 
                        st.success(f"**{usuario_input_add}** adicionado.")
                        st.rerun()
            else: st.error("O nome é necessário.")
    
    st.markdown("---")

    with st.container(border=True):
        st.markdown("##### ✏️ Editar Nome")
        if not df.empty:
            lista_edit = sorted(df[col_usuario].dropna().astype(str).unique().tolist())
            st.markdown("Selecione o membro antigo:") 
            usuario_para_editar = st.selectbox("Selecione para editar", lista_edit, key='user_edit_select', label_visibility="collapsed")
            
            st.markdown("Novo nome:")
            novo_nome_input = st.text_input("Digite o novo nome", key='new_name_input', label_visibility="collapsed")
            
            if st.button("Salvar Alteração", use_container_width=True):
                if novo_nome_input:
                    if novo_nome_input in df[col_usuario].astype(str).values:
                        st.error("Erro: Nome já existe.")
                    else:
                        idx = df[df[col_usuario].astype(str) == str(usuario_para_editar)].index[0]
                        df.at[idx, col_usuario] = novo_nome_input
                        if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                            if st.session_state.usuario_selecionado_id == usuario_para_editar:
                                st.session_state.usuario_selecionado_id = novo_nome_input
                            st.success(f"Renomeado: {usuario_para_editar} -> {novo_nome_input}")
                            st.rerun()
                else: st.warning("Digite o novo nome.")
        else: st.warning("Tabela vazia.")

    st.markdown("---")

    with st.container(border=True):
        st.markdown("##### 🗑️ Remover / Reset")
        if 'confirm_reset' not in st.session_state: st.session_state.confirm_reset = False
        if not df.empty:
            opcoes_remocao = sorted(df[col_usuario].dropna().astype(str).unique().tolist())
            st.markdown("Selecione para remover:")
            usuario_a_remover = st.selectbox("Selecione para remover", ['-- Selecione --'] + opcoes_remocao, key='remove_user_select', label_visibility="collapsed")
            
            if usuario_a_remover != '-- Selecione --':
                if st.button(f"Confirmar Remoção de {usuario_a_remover}", type="secondary", key='final_remove_button', use_container_width=True):
                    df = df[df[col_usuario].astype(str) != str(usuario_a_remover)]
                    if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                        st.session_state.usuario_selecionado_id = '-- Selecione o Membro --' 
                        st.success("Removido!")
                        st.rerun()
        st.markdown("---")
        if st.button("Resetar Tabela INTEIRA"): st.session_state.confirm_reset = True
        if st.session_state.confirm_reset:
            st.error("Cuidado: Ação IRREVERSÍVEL.")
            if st.button("SIM, ZERAR TUDO", type="secondary", key='sim_reset', use_container_width=True):
                if salvar_dados(pd.DataFrame(columns=df.columns), SHEET_NAME_PRINCIPAL):
                    st.success("Tabela zerada.")
                    st.session_state.confirm_reset = False
                    st.rerun()

# === COLUNA 2: UPAR ===
with col_upar:
    st.subheader("Registro de Metas")
    
    # Criar tabela de metas ordenadas do MAIOR (1) para o MENOR (note)
    metas_ordenadas = []
    # Inverter a lista para exibição (1 -> note)
    for cargo in reversed(CARGOS_LISTA):
        if cargo in METAS_PONTUACAO:
            meta = METAS_PONTUACAO[cargo]
            msgs_up = meta['meta_up'] * MENSAGENS_POR_PONTO
            msgs_manter = meta['meta_manter'] * MENSAGENS_POR_PONTO
            metas_ordenadas.append({
                "Cargo": cargo, 
                "Meta UP ⬆️": f"{msgs_up:,.0f}", 
                "Manter ⚓": f"{msgs_manter:,.0f}"
            })
    
    # --- TABELA DE METAS FIXA ---
    st.markdown("##### 📋 Tabela de Metas")
    st.dataframe(pd.DataFrame(metas_ordenadas), hide_index=True, use_container_width=True)
    
    st.markdown("---")
    
    with st.container(border=True):
        lista_opcoes = sorted(df[col_usuario].dropna().astype(str).unique().tolist())
        opcoes_usuarios = ['-- Selecione o Membro --'] + lista_opcoes
        try: def_idx = opcoes_usuarios.index(str(st.session_state.usuario_selecionado_id))
        except: def_idx = 0
        
        st.markdown("##### Selecione o Membro")
        usuario_selecionado = st.selectbox(
            "Selecione o Membro (Oculto)",
            opcoes_usuarios, 
            index=def_idx, 
            key='select_user_update',
            label_visibility="collapsed",
            on_change=lambda: st.session_state.__setitem__('usuario_selecionado_id', st.session_state.select_user_update)
        )
        st.session_state.usuario_selecionado_id = usuario_selecionado

        if usuario_selecionado != '-- Selecione o Membro --' and not df.empty and usuario_selecionado in df[col_usuario].astype(str).values:
            dados = df[df[col_usuario].astype(str) == str(usuario_selecionado)].iloc[0]
            usuario_input_upar = dados[col_usuario]
            
            with st.container():
                if dados[col_cargo] in METAS_PONTUACAO:
                    st.markdown(f"**Membro:** `{usuario_input_upar}`") 
                    st.markdown(f"""<div style="margin-bottom: 5px;"><strong>ID:</strong> <span style="color: #32CD32; font-family: 'Courier New'; font-weight: bold;">{dados.get(col_user_id, 'N/A')}</span></div>""", unsafe_allow_html=True)
                    
                    c_idx = CARGOS_LISTA.index(dados[col_cargo])
                    st.markdown("Cargo Atual:")
                    cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=c_idx, key='cargo_select_update', label_visibility="collapsed")
                    
                    if dados[col_sit] in ["UPADO", "REBAIXADO", "MANTEVE"]: st.info(f"Ciclo finalizado.")
                    else: st.info("Ciclo semanal.")

                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Acumulado", f"{dados[col_pontos_acum]:.1f}")
                    with c2: st.metric("Semana", f"{dados[col_pontos_sem]:.1f}")
                    with c3: st.metric("Mult.", f"{dados[col_mult_ind]:.1f}x")
                    st.markdown("---")
                    st.markdown("Semana do Ciclo:")
                    semana_input = st.number_input("Semana (1/1)", min_value=1, max_value=1, value=1, key='semana_input_update', label_visibility="collapsed")
                else:
                    st.error(f"Cargo '{dados[col_cargo]}' inválido ou antigo.")
                    st.warning("Atualize o cargo deste membro na caixa abaixo para um da nova lista.")
                    cargo_input = st.selectbox("Novo Cargo", CARGOS_LISTA, index=0, key='cargo_select_update')

            st.divider()
            st.markdown("##### Dados Semanais")
            cp1, cp2 = st.columns(2)
            with cp1: 
                st.markdown("Mensagens:")
                msgs_in = st.number_input("Mensagens", min_value=0, value=int(st.session_state.get('mensagens_input', 0)), step=10, key='mensagens_input', label_visibility="collapsed")
            with cp2: 
                st.markdown("Bônus (Pts):")
                bonus_in = st.number_input("Bônus", min_value=0.0, value=st.session_state.get('bonus_input', 0.0), step=1.0, key='bonus_input', label_visibility="collapsed")
            
            st.markdown("Multiplicador:")
            mult_in = st.number_input("Multiplicador", min_value=0.1, value=float(dados[col_mult_ind]), step=0.1, key='mult_ind_input', label_visibility="collapsed")

            st.markdown("---")
            if st.button("Processar Semana", type="primary", key="save_update_button", use_container_width=True):
                st.session_state.salvar_button_clicked = True
        else:
            usuario_input_upar = None
            
    if st.session_state.salvar_button_clicked and usuario_input_upar:
        st.session_state.salvar_button_clicked = False
        df = carregar_dados(SHEET_NAME_PRINCIPAL)
        dados = df[df[col_usuario].astype(str) == str(usuario_input_upar)].iloc[0]
        pts_base = st.session_state.mensagens_input / 50.0
        pts_semana = calcular_pontuacao_semana(pts_base, st.session_state.bonus_input, st.session_state.mult_ind_input)
        
        # Proteção contra cargo inexistente na hora de calcular
        if st.session_state.cargo_select_update not in METAS_PONTUACAO:
             st.error("Cargo selecionado inválido.")
             st.stop()

        situacao, _ = avaliar_situacao(st.session_state.cargo_select_update, 1, pts_semana)
        novo_cargo = st.session_state.cargo_select_update
        if situacao == "UPADO":
            try: 
                idx_c = CARGOS_LISTA.index(novo_cargo)
                if idx_c < len(CARGOS_LISTA)-1: novo_cargo = CARGOS_LISTA[idx_c+1]
            except: pass
        elif situacao == "REBAIXADO":
            try: 
                idx_c = CARGOS_LISTA.index(novo_cargo)
                if idx_c > 0: novo_cargo = CARGOS_LISTA[idx_c-1]
                else: novo_cargo = 'note' # Cargo base fallback
            except: pass
        
        novo_reg = {
            col_usuario: usuario_input_upar, col_user_id: dados.get(col_user_id, 'N/A'), col_cargo: novo_cargo, col_sit: situacao,
            col_sem: 1, col_pontos_acum: 0.0, col_pontos_sem: round(pts_semana, 1), col_bonus_sem: round(st.session_state.bonus_input, 1),
            col_mult_ind: round(st.session_state.mult_ind_input, 1), 'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            col_pontos_final: round(dados[col_pontos_final] + pts_semana, 1)
        }
        df.loc[df[df[col_usuario].astype(str) == str(usuario_input_upar)].index[0]] = novo_reg
        if salvar_dados(df, SHEET_NAME_PRINCIPAL):
            limpar_campos_interface()
            st.session_state.usuario_selecionado_id = usuario_input_upar
            st.success(f"Atualizado: {situacao}. Novo Cargo: {novo_cargo}")
            st.rerun()

# === COLUNA 3: RANKING ===
with col_ranking:
    st.subheader("Ranking")
    st.info(f"Membros: **{len(df)}**")
    if not df.empty:
        df_d = df.copy()
        c_ord = {c: i for i, c in enumerate(CARGOS_LISTA)}
        
        # Proteção se houver cargo antigo no ranking que não está na lista nova
        df_d['rank'] = df_d[col_cargo].map(c_ord).fillna(-1) 
        
        df_d = df_d.sort_values(by=[col_pontos_final, 'rank'], ascending=[False, False])
        st.dataframe(df_d.style.map(lambda x: 'background-color:rgba(50,205,50,0.3);color:#ccffcc' if 'UPADO' in str(x) else ('background-color:rgba(200,0,0,0.4);color:#ffcccc' if 'REBAIXADO' in str(x) else ('background-color:rgba(218,165,32,0.3);color:#ffffcc' if 'MANTEVE' in str(x) else '')), subset=[col_sit]).format(precision=1), use_container_width=True, height=600, column_order=[col_usuario, col_user_id, col_cargo, col_sit, col_pontos_acum, col_pontos_sem, 'Data_Ultima_Atualizacao'])
    else: st.warning("Sem dados.")
