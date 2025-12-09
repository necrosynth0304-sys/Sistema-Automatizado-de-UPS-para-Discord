import streamlit as st
import pandas as pd
from datetime import datetime
import os 

# --- DEPENDÊNCIAS GOOGLE SHEETS ---
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    st.error("Dependências gspread ou google-oauth2-service-account ausentes. Instale via 'pip install gspread google-oauth2-service-account'.")
    gspread = None
    Credentials = None


# --- CONFIGURAÇÃO DAS REGRAS DO SISTEMA (MANTIDA) ---

METAS = {
    'f*ck':    {'ciclo': 1, 'meta_pts': 20,   'manter': 13}, 
    '100%':    {'ciclo': 1, 'meta_pts': 27,   'manter': 20},
    'woo':     {'ciclo': 2, 'meta_pts': 91,   'manter': 78},
    'sex':     {'ciclo': 2, 'meta_pts': 130,  'manter': 104},
    '?':       {'ciclo': 2, 'meta_pts': 169,  'manter': 130},
    '!':       {'ciclo': 3, 'meta_pts': 420,  'manter': 325},
    'aura':    {'ciclo': 3, 'meta_pts': 550,  'manter': 420},
    'all wild':{'ciclo': 3, 'meta_pts': 725,  'manter': 500},
    'cute':    {'ciclo': 4, 'meta_pts': 1135, 'manter': 969},
    '$':       {'ciclo': 4, 'meta_pts': 1335, 'manter': 1234}, 
    'void':    {'ciclo': 4, 'meta_pts': 1600, 'manter': 1450},
    'dawn':    {'ciclo': 4, 'meta_pts': 1900, 'manter': 1700},
    'upper':   {'ciclo': 4, 'meta_pts': 2500, 'manter': 2200}, 
}

CARGOS_LISTA = list(METAS.keys())
OPCOES_DESAFIO = ["Nenhum", "Engajamento (2.0x Call)", "Mensagens (1.5x)", "Presença (1.5x)"]

# --- CONFIGURAÇÃO DA CONEXÃO GOOGLE SHEETS (MANTIDA) ---

@st.cache_resource(ttl=3600) 
def get_gsheets_client():
    if gspread is None or Credentials is None:
        return None
        
    try:
        creds_json = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(creds_json, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as e:
        return None

gc = get_gsheets_client()

# --- CONSTANTES DE COLUNAS (MANTIDAS) ---

COLUNAS_PADRAO = [
    'usuario', 'cargo', 'situação', 'Semana_Atual', 
    'Pts_Acumulados_Ciclo', 'Pts_Semana', 'Data_Ultima_Atualizacao', 
    'Pts_Total_Final', 'Ultima_Semana_Horas', 'Ultima_Semana_Msgs'
]

col_usuario = 'usuario'
col_cargo = 'cargo'
col_sit = 'situação'
col_sem = 'Semana_Atual'
col_pts_acum = 'Pts_Acumulados_Ciclo'
col_pts_semana = 'Pts_Semana'
col_pts_final = 'Pts_Total_Final'
col_horas = 'Ultima_Semana_Horas'
col_msgs = 'Ultima_Semana_Msgs'

# --- FUNÇÕES DE CARREGAMENTO E SALVAMENTO DE DADOS (MANTIDAS) ---

@st.cache_data(ttl=5) 
def carregar_dados():
    if gc is None:
        st.error("ERRO: A conexão com o Google Sheets falhou. Os dados NÃO serão salvos na nuvem.")
        return pd.DataFrame(columns=COLUNAS_PADRAO)
        
    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        SHEET_NAME = st.secrets["gsheets_config"]["worksheet_name"]
        
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.worksheet(SHEET_NAME)
        
        df = pd.DataFrame(worksheet.get_all_records())
        
        if df.empty or not all(col in df.columns for col in COLUNAS_PADRAO):
            df = pd.DataFrame(columns=COLUNAS_PADRAO)
        
        cols_to_convert = [col_sem, col_pts_acum, col_pts_semana, col_pts_final, col_horas, col_msgs]
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        return df

    except Exception as e:
        st.error(f"ERRO: A conexão com o Google Sheets falhou. Verifique a URL e o nome da aba. ({e})")
        return pd.DataFrame(columns=COLUNAS_PADRAO)


def salvar_dados(df):
    if gc is None:
        st.error("Não foi possível salvar os dados: Conexão Sheets inativa.")
        return False

    st.info("Tentando salvar dados na planilha...")

    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        SHEET_NAME = st.secrets["gsheets_config"]["worksheet_name"]
        
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


# --- FUNÇÕES DE LÓGICA (MANTIDAS) ---

def calcular_pontos_semana(msgs, horas, rush_hour, desafio_tipo, participou_desafio):
    pts_msg = msgs / 50
    pts_voz = horas * 2
    pts_total_atividade = pts_msg + pts_voz
    
    multiplicador = 1.0
    
    if rush_hour: multiplicador += 0.5
        
    if participou_desafio:
        if desafio_tipo == "Engajamento (2.0x Call)":
            multiplicador += 1.0
        elif desafio_tipo in ["Mensagens (1.5x)", "Presença (1.5x)"]:
            multiplicador += 0.5

    return round(pts_total_atividade * multiplicador, 2)

def avaliar_situacao(cargo, pts_acumulados, semana_atual):
    meta = METAS[cargo]
    meta_area = meta['meta_pts']
    meta_manter = meta['manter']
    ciclo_max = meta['ciclo']
    
    situacao = ""
    fator_multiplicacao = 0 
    
    if semana_atual >= ciclo_max:
        if pts_acumulados >= meta_area:
            situacao = "UPADO"
            fator_multiplicacao = int(pts_acumulados // meta_area)
            if fator_multiplicacao < 1: fator_multiplicacao = 1
                
        elif pts_acumulados >= meta_manter:
            situacao = "MANTEVE"
        else:
            situacao = "REBAIXADO"
    else:
        situacao = f"Em andamento ({semana_atual}/{ciclo_max})"
        
    return situacao, fator_multiplicacao


# --- INTERFACE (STREAMLIT) ---

st.set_page_config(page_title="🔥 Sistema de Ups EXY", layout="wide")
st.title("🔥 Sistema de Ups EXY")

df = carregar_dados()

# Sidebar - Configurações Globais da Semana
st.sidebar.header("⚙️ Configurações da Semana")
weekend_ativo = st.sidebar.checkbox("Ativar Weekend (1.2x)?", value=False)
tipo_desafio = st.sidebar.selectbox("Desafio Semanal Ativo", OPCOES_DESAFIO)

# --- COLUNAS PRINCIPAIS ---
col1, col2 = st.columns([1, 2])

# Variável de estado para o botão salvar
if 'salvar_button_clicked' not in st.session_state:
    st.session_state.salvar_button_clicked = False

with col1:
    st.subheader("Entrada de Dados e Gestão")
    
    tab_update, tab_add = st.tabs(["⬆️ Atualizar Semana / Upar", "➕ Adicionar Novo Membro"])

    # --- Variáveis de estado iniciais ---
    usuario_input = None
    
    if CARGOS_LISTA:
        cargo_inicial_default = CARGOS_LISTA.index('f*ck')
    else:
        cargo_inicial_default = 0


    # === ABA 1: ATUALIZAR/UPAR MEMBRO EXISTENTE ===
    with tab_update:
        
        opcoes_usuarios = ['-- Selecione o Membro --'] + sorted(df[col_usuario].unique().tolist()) 
        usuario_selecionado = st.selectbox("Selecione o Membro", opcoes_usuarios, key='select_user_update')
        
        if usuario_selecionado != '-- Selecione o Membro --' and not df.empty and usuario_selecionado in df[col_usuario].values:
            
            dados_atuais = df[df[col_usuario] == usuario_selecionado].iloc[0]
            usuario_input = dados_atuais[col_usuario]
            
            cargo_atual_dados = dados_atuais[col_cargo]
            pts_acumulados_anteriores = dados_atuais[col_pts_acum]
            semana_atual = dados_atuais[col_sem]
            
            # --- Bloco de Informação do Membro ---
            with st.container(border=True):
                if cargo_atual_dados in METAS:
                    ciclo_max = METAS[cargo_atual_dados]['ciclo']
                    cargo_index_default = CARGOS_LISTA.index(cargo_atual_dados)
                    st.markdown(f"**Membro:** `{usuario_input}` | **Cargo:** `{cargo_atual_dados}`")
                    st.markdown(f"**Ciclo:** *{semana_atual}* / *{ciclo_max}* semanas")
                    
                    if dados_atuais[col_sit] in ["UPADO", "REBAIXADO", "MANTEVE"]:
                        proxima_semana = 1
                        pts_acumulados_anteriores = 0.0 
                        st.info("⚠️ Ciclo finalizado. O próximo registro será na **Semana 1** do novo cargo.")
                    else:
                        proxima_semana = semana_atual + 1
                        if proxima_semana > ciclo_max: proxima_semana = ciclo_max
                        
                    semana_input_value = int(proxima_semana)
                else:
                    ciclo_max = 1
                    st.error(f"Cargo '{cargo_atual_dados}' desconhecido. Revertendo para 'f*ck'.")
                    semana_input_value = 1
            # --- Fim Bloco de Informação do Membro ---
            
            # --- Entradas de Dados ---
            st.divider() # Divisor visual

            # Organização dos inputs
            col_semana, col_cargo_select = st.columns(2)
            with col_semana:
                semana_input = st.number_input("Semana do Ciclo (Máx: {ciclo_max})", 
                                            min_value=1, max_value=ciclo_max, value=semana_input_value, 
                                            key='semana_input_update')
            with col_cargo_select:
                cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select_update')

            st.markdown("##### 📊 Dados de Atividade Semanal")
            col_msgs, col_horas = st.columns(2)
            with col_msgs:
                msgs_input = st.number_input("Mensagens", min_value=0, value=0, key='msgs_input_update')
            with col_horas:
                horas_input = st.number_input("Horas em Call", min_value=0.0, value=0.0, step=0.5, key='horas_input_update')
            
            st.divider() # Divisor visual

            st.markdown("##### 🚀 Bônus e Multiplicadores")
            check_rush = st.checkbox("Participou Rush Hour? (+0.5x)", key='rush_check_update')
            check_desafio = st.checkbox("Participou Desafio Semanal? (x1.5/x2.0)", key='desafio_check_update')
            bonus_fixo_input = st.number_input("Bônus Fixo (Pontos Extras)", value=0.0, key='bonus_input_update')
            
            # Botão de salvar
            st.markdown("---")
            if st.button("Salvar / Atualizar Semana", type="primary", key="save_update_button", use_container_width=True):
                st.session_state.salvar_button_clicked = True
            
        else:
            st.info("Selecione um membro acima para registrar a pontuação da semana e processar o UP.")
            usuario_input = None
            
    # === ABA 2: ADICIONAR NOVO MEMBRO ===
    with tab_add:
        # CORREÇÃO: Texto do cabeçalho
        st.subheader("Registrar Novo Membro") 
        
        usuario_input_add = st.text_input("Nome do Novo Usuário", key='usuario_input_add')
        cargo_input_add = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=cargo_inicial_default, key='cargo_select_add')
        
        st.markdown("---")
        if st.button("✅ Adicionar Membro", type="secondary", use_container_width=True):
            if usuario_input_add:
                # Verifica se o usuário já existe
                if usuario_input_add in df[col_usuario].values:
                    st.error(f"❌ O membro '{usuario_input_add}' já existe. Use a aba 'Atualizar Semana / Upar'.")
                else:
                    # Prepara os novos dados
                    novo_dado_add = {
                        col_usuario: usuario_input_add, 
                        col_cargo: cargo_input_add, 
                        col_sit: f"Em andamento (1/{METAS[cargo_input_add]['ciclo']})",
                        col_sem: 1,
                        col_pts_acum: 0.0, 
                        col_pts_semana: 0.0,
                        'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        col_pts_final: 0.0,
                        col_horas: 0.0,
                        col_msgs: 0.0
                    }
                    
                    df = pd.concat([df, pd.DataFrame([novo_dado_add])], ignore_index=True)
                    
                    escrita_foi_bem_sucedida = salvar_dados(df)
                    
                    if escrita_foi_bem_sucedida:
                        st.success(f"🎉 Membro **{usuario_input_add}** adicionado! Use a aba 'Atualizar Semana / Upar' para registrar a primeira semana.")
                        st.rerun()
                    else:
                         pass
            else:
                 st.error("Digite o nome do novo membro.")


    # ----------------------------------------------------
    # --- LÓGICA DE PROCESSAMENTO (FORA DAS ABAS) ---
    # ----------------------------------------------------
    
    if st.session_state.salvar_button_clicked:
        st.session_state.salvar_button_clicked = False
        
        if usuario_input is not None:
            
            # Recaptura os dados da aba de atualização usando session_state
            # Nota: O dado 'dados_atuais' precisa ser reavaliado aqui, pois os inputs usam o estado
            
            # Certifica-se de que estamos usando o DF mais recente no Cloud
            df_reloaded = carregar_dados() 
            dados_atuais = df_reloaded[df_reloaded[col_usuario] == st.session_state.select_user_update].iloc[0]
            pts_acumulados_anteriores = dados_atuais[col_pts_acum]

            usuario_input = dados_atuais[col_usuario]
            cargo_input = st.session_state.cargo_select_update
            semana_input = st.session_state.semana_input_update
            msgs_input = st.session_state.msgs_input_update
            horas_input = st.session_state.horas_input_update
            check_rush = st.session_state.rush_check_update
            check_desafio = st.session_state.desafio_check_update
            bonus_fixo_input = st.session_state.bonus_input_update
            
            # --- Lógica de Cálculo e Avaliação (MANTIDA) ---
            pts_semana_multi = calcular_pontos_semana(msgs_input, horas_input, check_rush, tipo_desafio, check_desafio)
            
            if cargo_input not in METAS:
                 st.error(f"Cargo '{cargo_input}' inválido nas METAS.")
                 st.stop()
                 
            meta_do_cargo = METAS[cargo_input]['meta_pts']
            pts_semana_final = pts_semana_multi
            if weekend_ativo and pts_semana_multi >= (meta_do_cargo * 0.70):
                pts_semana_final = pts_semana_multi * 1.2
            pts_semana_final += bonus_fixo_input

            pts_acumulados_total = pts_acumulados_anteriores + pts_semana_final
            
            situacao, fator_multiplicacao = avaliar_situacao(cargo_input, pts_acumulados_total, semana_input)

            novo_cargo = cargo_input 
            
            # Lógica de UP MÚLTIPLO (MANTIDA)
            if situacao in ["UPADO", "REBAIXADO", "MANTEVE"]:
                nova_semana = 1
                novo_pts_acumulados = 0.0
                
                if situacao == "UPADO":
                    indice_atual = CARGOS_LISTA.index(cargo_input)
                    niveis_a_avancar = 1 
                    
                    if cargo_input == 'f*ck':
                        if fator_multiplicacao >= 3:
                            indice_limite = CARGOS_LISTA.index('sex')
                            niveis_a_avancar = indice_limite - indice_atual
                        elif fator_multiplicacao == 2:
                            indice_limite = CARGOS_LISTA.index('woo')
                            niveis_a_avancar = indice_limite - indice_atual
                    elif cargo_input == '100%':
                        if fator_multiplicacao >= 3:
                            indice_limite = CARGOS_LISTA.index('?')
                            niveis_a_avancar = indice_limite - indice_atual
                        elif fator_multiplicacao == 2:
                            indice_limite = CARGOS_LISTA.index('sex')
                            niveis_a_avancar = indice_limite - indice_atual

                    novo_indice = indice_atual + niveis_a_avancar
                    
                    if novo_indice >= len(CARGOS_LISTA) - 1:
                        novo_cargo = CARGOS_LISTA[-1] 
                    else:
                        novo_cargo = CARGOS_LISTA[novo_indice]
                        
                    if niveis_a_avancar > 1:
                        st.balloons()
                        st.warning(f"UP MÚLTIPLO ATIVADO! O usuário subiu {niveis_a_avancar} níveis para o cargo **{novo_cargo}**!")
                        
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
                nova_semana = semana_input + 1
                if nova_semana > METAS[cargo_input]['ciclo']:
                    nova_semana = METAS[cargo_input]['ciclo']
                novo_pts_acumulados = pts_acumulados_total


            # Prepara os novos dados na ORDEM CORRETA
            novo_dado = {
                col_usuario: usuario_input, 
                col_cargo: novo_cargo, 
                col_sit: situacao,
                col_sem: nova_semana,
                col_pts_acum: novo_pts_acumulados, 
                col_pts_semana: round(pts_semana_final, 2),
                'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                col_pts_final: round(pts_acumulados_total, 2),
                col_horas: horas_input,
                col_msgs: msgs_input
            }
            
            # Salva no DataFrame (substitui a linha antiga)
            df.loc[df[df[col_usuario] == usuario_input].index[0]] = novo_dado

            escrita_foi_bem_sucedida = salvar_dados(df)
            
            if escrita_foi_bem_sucedida:
                st.success(f"✅ Dados salvos no Drive! Situação: {situacao} | Próximo Cargo: **{novo_cargo}**")
                st.rerun()
            else:
                pass
        else:
            st.error("Selecione um membro válido na aba 'Atualizar Semana / Upar' antes de salvar.")


    st.markdown("---")

    # --- SEÇÃO: REMOÇÃO DE USUÁRIOS POR LISTA e RESET GLOBAL (MANTIDA) ---
    
    st.subheader("🗑️ Ferramentas de Gestão")
    
    # Colocando remoção e reset em uma box para organizar visualmente
    with st.container(border=True):
        st.markdown("##### Remover Usuários")
        
        if 'confirm_reset' not in st.session_state:
            st.session_state.confirm_reset = False

        if not df.empty:
            opcoes_remocao = sorted(df[col_usuario].unique().tolist())
            usuario_a_remover = st.selectbox("Selecione o Usuário para Remover", ['-- Selecione --'] + opcoes_remocao, key='remove_user_select')
            
            if usuario_a_remover != '-- Selecione --':
                st.warning(f"⚠️ Confirme a remoção de **{usuario_a_remover}**. Permanente.")
                
                if st.button(f"🗑️ Confirmar Remoção de {usuario_a_remover}", type="secondary", key='final_remove_button', use_container_width=True):
                    df = df[df[col_usuario] != usuario_a_remover]
                    salvar_dados(df) 
                    st.success(f"Membro {usuario_a_remover} removido com sucesso!")
                    st.rerun()
        else:
            st.info("Não há membros na tabela para remover.")

        st.markdown("---")

        st.markdown("##### 💣 Reset Global da Tabela")
        
        if st.button("Resetar Tabela INTEIRA"):
            st.session_state.confirm_reset = True
            
        if st.session_state.confirm_reset:
            st.error("⚠️ Tem certeza? Esta ação é IRREVERSÍVEL e apagará TODOS os dados salvos.")
            col_reset1, col_reset2 = st.columns(2)
            
            with col_reset1:
                if st.button("SIM, ZERAR TUDO", type="secondary", key='sim_reset'):
                    df_reset = pd.DataFrame(columns=df.columns) 
                    salvar_dados(df_reset) 
                    st.success("Tabela zerada com sucesso!")
                    st.session_state.confirm_reset = False
                    st.rerun()
            with col_reset2:
                if st.button("NÃO, CANCELAR", type="secondary", key='nao_reset'):
                    st.session_state.confirm_reset = False
                    st.rerun()


# --- ABA 2: VISUALIZAÇÃO DA TABELA (COLUNA 2) ---
with col2:
    st.subheader("⭐ Tabela de Acompanhamento e Ranking")
    
    if gc is None:
        st.error("ERRO: A conexão com o Google Sheets falhou.")
    
    st.info(f"Total de Membros Registrados: **{len(df)}**")
    
    if not df.empty: 
        df_display = df.sort_values(by=[col_pts_acum, col_cargo], 
                                    ascending=[False, True])
                                    
        # Configurando a exibição da tabela com cores
        st.dataframe(
            df_display.style.map(
                lambda x: 'background-color: #e6ffed; color: green' if 'UPADO' in str(x) else 
                          ('background-color: #ffe6e6; color: red' if 'REBAIXADO' in str(x) else 
                           ('background-color: #fffac2; color: #8a6d3b' if 'MANTEVE' in str(x) else '')),
                subset=[col_sit]
            ),
            use_container_width=True,
            height=600,
            column_order=[col_usuario, col_cargo, col_sit, col_sem, col_pts_acum, col_pts_semana, 'Data_Ultima_Atualizacao']
        )
    else:
        st.warning("Nenhum membro cadastrado. Adicione um na coluna ao lado.")

    st.divider()

    ## Seção de Métricas de Atividade
    
    if not df.empty:
        st.subheader("📈 Métricas Agregadas e Detalhes")
        
        df[col_msgs] = pd.to_numeric(df[col_msgs], errors='coerce').fillna(0)
        df[col_horas] = pd.to_numeric(df[col_horas], errors='coerce').fillna(0)

        total_msgs = df[col_msgs].sum()
        total_call = df[col_horas].sum()
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("Total Mensagens (Última Rodada)", f"{total_msgs:,.0f} 💬")
        with col_m2:
            st.metric("Total Horas Call (Última Rodada)", f"{total_call:.1f} 🎙️")
        
        # 2. Métricas Individuais
        usuario_selecionado_display = st.session_state.get('select_user_update')
        
        if usuario_selecionado_display and usuario_selecionado_display != '-- Selecione o Membro --' and usuario_selecionado_display in df[col_usuario].values:
            
            dados_individuais = df[df[col_usuario] == usuario_selecionado_display].iloc[0]
            
            st.markdown("---")
            st.subheader(f"Detalhes da Última Atividade de `{usuario_selecionado_display}`")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.metric("Mensagens Registradas", dados_individuais[col_msgs])
            with col_d2:
                st.metric("Horas em Call Registradas", dados_individuais[col_horas])
