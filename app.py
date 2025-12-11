import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÃO DAS REGRAS DO SISTEMA (PONTUAÇÃO E CICLOS) ---

# NOVO MAPA DE PONTUAÇÃO - HIERARQUIA REAJUSTADA
# Ciclo: 1 Semana para todos
# Metas baseadas no "deslize" dos cargos para baixo
METAS_PONTUACAO = {
    # Posições 1 a 4 (Base)
    'f*ck':      {'ciclo': 1, 'meta_up': 15, 'meta_manter': 10},      # Posição 1
    '100%':      {'ciclo': 1, 'meta_up': 20, 'meta_manter': 15},      # Posição 2
    'woo':       {'ciclo': 1, 'meta_up': 70, 'meta_manter': 60},      # Posição 3
    'sex':       {'ciclo': 1, 'meta_up': 100, 'meta_manter': 80},     # Posição 4
    
    # Posição 5
    'note':      {'ciclo': 1, 'meta_up': 195, 'meta_manter': 150},    # Posição 5 (Antigo '?')
    
    # Posições 6 a 8 (Deslizaram para baixo - Pegam metas do cargo anterior neles)
    'aura':      {'ciclo': 1, 'meta_up': 336, 'meta_manter': 260},    # Posição 6 (Meta do antigo '!')
    'all wild':  {'ciclo': 1, 'meta_up': 440, 'meta_manter': 336},    # Posição 7 (Meta do antigo 'aura')
    'cute':      {'ciclo': 1, 'meta_up': 580, 'meta_manter': 400},    # Posição 8 (Meta do antigo 'all wild') - Fica abaixo de Mello
    
    # Posição 9 (Mello - Ocupa lugar do antigo Cute)
    'mello':     {'ciclo': 1, 'meta_up': 681, 'meta_manter': 581},    # Posição 9 (Meta do antigo 'cute')
    
    # Posições 10 a 12 (Deslizaram para baixo)
    'void':      {'ciclo': 1, 'meta_up': 801, 'meta_manter': 740},    # Posição 10 (Meta do antigo '$')
    'dawn':      {'ciclo': 1, 'meta_up': 971, 'meta_manter': 880},    # Posição 11 (Meta do antigo 'void')
    'upper':     {'ciclo': 1, 'meta_up': 1141, 'meta_manter': 1025},  # Posição 12 (Meta do antigo 'dawn') - Fica abaixo de Light
    
    # Posição 13 (Light - Topo)
    'Light':     {'ciclo': 1, 'meta_up': 1321, 'meta_manter': 1180},  # Posição 13 (Meta do antigo 'upper')
}

# Lista ordenada do Menor para o Maior
CARGOS_LISTA = [
    'f*ck', '100%', 'woo', 'sex', 'note', 'aura', 'all wild', 
    'cute', 'mello', 
    'void', 'dawn', 'upper', 'Light'
]

# --- CONSTANTES DE CONVERSÃO ---
MENSAGENS_POR_PONTO = 50
DIAS_POR_SEMANA = 7

# --- NOME DA ABA PRINCIPAL ---
SHEET_NAME_PRINCIPAL = "dados sistema"


# --- CONSTANTES DE COLUNAS (DataFrame) ---
COLUNAS_PADRAO = [
    'usuario', 'user_id', 'cargo', 'situação', 'Semana_Atual',
    'Pontos_Acumulados_Ciclo', 'Pontos_Semana', 'Bonus_Semana',
    'Multiplicador_Individual', 'Data_Ultima_Atualizacao', 'Pontos_Total_Final'
]

col_usuario = 'usuario'
col_user_id = 'user_id' # ID do Usuário
col_cargo = 'cargo'
col_sit = 'situação'
col_sem = 'Semana_Atual'
col_pontos_acum = 'Pontos_Acumulados_Ciclo'
col_pontos_sem = 'Pontos_Semana'
col_bonus_sem = 'Bonus_Semana'
col_mult_ind = 'Multiplicador_Individual'
col_pontos_final = 'Pontos_Total_Final'


# --- FUNÇÕES DE CONEXÃO E LÓGICA ---

@st.cache_resource(ttl=3600)
def get_gsheets_client():
    """Autoriza o cliente gspread."""
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
def carregar_dados(sheet_name):
    """Lê os dados da planilha Google."""
    if gc is None:
        if 'gsheets_error' in st.session_state:
             st.error(st.session_state['gsheets_error'])
        return pd.DataFrame(columns=COLUNAS_PADRAO)
        
    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        sh = gc.open_by_url(SPREADSHEET_URL)
        
        worksheet = sh.worksheet(sheet_name)
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
        
        cols_to_convert = [col_sem, col_pontos_acum, col_pontos_sem, col_bonus_sem, col_mult_ind, col_pontos_final]
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        return df

    except Exception as e:
        st.error(f"ERRO: A conexão com a aba '{sheet_name}' falhou. Verifique se a aba existe. ({e})")
        return pd.DataFrame(columns=COLUNAS_PADRAO)


def salvar_dados(df, sheet_name):
    """Sobrescreve a aba da planilha Google."""
    if gc is None:
        st.error("Não foi possível salvar os dados: Conexão Sheets inativa.")
        return False

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
        st.error("ERRO CRÍTICO: Falha na Escrita ou Permissão Negada (403)!")
        st.exception(e)
        return False


def calcular_pontuacao_semana(pontos_base, bonus, mult_ind):
    """Calcula a pontuação final da semana com o multiplicador individual."""
    pontos_final = (pontos_base + bonus) * mult_ind
    return round(pontos_final, 1)


def avaliar_situacao(cargo, semana_atual, pontos_acumulados):
    """Avalia o UP/MANTER/REBAIXAR no final do ciclo (Meta 1x fixa)."""
    meta = METAS_PONTUACAO[cargo]
    meta_up = meta['meta_up']
    meta_manter = meta['meta_manter']
    
    # Ciclo sempre 1 semana, avaliação direta
    if pontos_acumulados >= meta_up:
        situacao = "UPADO"
    elif pontos_acumulados >= meta_manter:
        situacao = "MANTEVE"
    else:
        situacao = "REBAIXADO"
        
    return situacao, 0


def limpar_campos_interface():
    """Limpa campos de input."""
    keys_to_delete = ['mensagens_input', 'bonus_input']
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]


# --- INTERFACE (STREAMLIT) ---

st.set_page_config(page_title="Sistema de Pontuação Ranking", layout="wide")
st.title("Sistema de Pontuação Ranking")
st.markdown("##### Gerenciamento de UP baseado em Pontuação (Chat)")

df = carregar_dados(SHEET_NAME_PRINCIPAL) 

# Inicializa estados
if 'salvar_button_clicked' not in st.session_state:
    st.session_state.salvar_button_clicked = False
if 'usuario_selecionado_id' not in st.session_state:
    st.session_state.usuario_selecionado_id = '-- Selecione o Membro --'
if 'novo_cargo_apos_ciclo' not in st.session_state:
    st.session_state.novo_cargo_apos_ciclo = None

col_ferramentas, col_upar, col_ranking = st.columns([1, 1.2, 2])

# Variável para cargo inicial
cargo_inicial_default = CARGOS_LISTA.index('f*ck') if CARGOS_LISTA else 0
usuario_input_upar = None


# =========================================================================
# === COLUNA 1: FERRAMENTAS DE GESTÃO (Adicionar/Remover/Reset) ===
# =========================================================================
with col_ferramentas:
    st.subheader("Ferramentas de Gestão")
    
    with st.container(border=True):
        st.markdown("##### Adicionar Novo Membro")
        
        usuario_input_add = st.text_input("Nome do Novo Usuário", key='usuario_input_add')
        user_id_input_add = st.text_input("ID do Usuário (Opcional)", key='user_id_input_add', value='N/A')
        cargo_input_add = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=cargo_inicial_default, key='cargo_select_add')
        
        if st.button("Adicionar Membro", type="primary", use_container_width=True):
            if usuario_input_add:
                if usuario_input_add in df[col_usuario].values:
                    st.error(f"O membro '{usuario_input_add}' já existe.")
                else:
                    total_ciclo_add = 1 # Ciclo sempre 1
                    
                    novo_dado_add = {
                        col_usuario: usuario_input_add, 
                        col_user_id: user_id_input_add, 
                        col_cargo: cargo_input_add, 
                        col_sit: f"Em andamento (1/{total_ciclo_add})",
                        col_sem: 1,
                        col_pontos_acum: 0.0, 
                        col_pontos_sem: 0.0,
                        col_bonus_sem: 0.0,
                        col_mult_ind: 1.0,
                        'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        col_pontos_final: 0.0,
                    }
                    
                    df = pd.concat([df, pd.DataFrame([novo_dado_add])], ignore_index=True)
                    
                    if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                        st.session_state.usuario_selecionado_id = usuario_input_add 
                        st.success(f"Membro **{usuario_input_add}** adicionado!")
                        st.rerun()
            else:
                 st.error("Digite o nome do novo membro.")
        
    st.markdown("---")
    
    with st.container(border=True):
        st.markdown("##### Remoção / Reset de Tabela")

        if 'confirm_reset' not in st.session_state:
            st.session_state.confirm_reset = False

        if not df.empty:
            opcoes_remocao = sorted(df[col_usuario].unique().tolist())
            usuario_a_remover = st.selectbox("Selecione o Usuário para Remover", ['-- Selecione --'] + opcoes_remocao, key='remove_user_select')
            
            if usuario_a_remover != '-- Selecione --':
                st.warning(f"Confirme a remoção de **{usuario_a_remover}**. Permanente.")
                
                if st.button(f"Confirmar Remoção de {usuario_a_remover}", type="secondary", key='final_remove_button', use_container_width=True):
                    df = df[df[col_usuario] != usuario_a_remover]
                    if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                        st.session_state.usuario_selecionado_id = '-- Selecione o Membro --' 
                        st.success(f"Membro {usuario_a_remover} removido com sucesso!")
                        st.rerun()
        
        st.markdown("---")
        
        if st.button("Resetar Tabela INTEIRA"):
            st.session_state.confirm_reset = True
            
        if st.session_state.confirm_reset:
            st.error("Tem certeza? Esta ação é IRREVERSÍVEL. Zera todos os dados dos membros.")
            
            if st.button("SIM, ZERAR TUDO", type="secondary", key='sim_reset', use_container_width=True):
                df_reset = pd.DataFrame(columns=df.columns) 
                if salvar_dados(df_reset, SHEET_NAME_PRINCIPAL):
                    st.session_state.usuario_selecionado_id = '-- Selecione o Membro --' 
                    st.success("Tabela zerada com sucesso!")
                    st.session_state.confirm_reset = False
                    st.rerun()

# =========================================================================
# === COLUNA 2: UPAR (Entrada de Dados/Registro da Semana) ===
# =========================================================================
with col_upar:
    st.subheader("Upar (Registro de Dados)")
    
    # --- BLOCO: VISUALIZAÇÃO SIMPLES DE METAS ---
    metas_data_pontos_simples = []
    for idx, (cargo, metas) in enumerate(METAS_PONTUACAO.items()):
        mensagens_up = metas['meta_up'] * MENSAGENS_POR_PONTO
        dias_ciclo = 7 
        
        metas_data_pontos_simples.append({
            "Cargo (#)": f"{cargo} ({idx+1})",
            "Ciclo (Sem)": 1,
            "Meta UP (pts)": metas['meta_up'],
            "Meta UP (msgs)": f"{mensagens_up:,.0f}",
            "Meta Manter (pts)": metas['meta_manter'], 
            "Msgs/Dia (UP)": f"{mensagens_up / dias_ciclo:,.0f}",
        })
    df_metas_pontos_simples = pd.DataFrame(metas_data_pontos_simples)

    with st.expander("Tabela de Metas (Pontos e Mensagens) 📋", expanded=False):
        st.dataframe(df_metas_pontos_simples, hide_index=True, use_container_width=True)
    
    st.markdown("---")
    
    # Entrada de Dados
    with st.container(border=True):
        
        opcoes_usuarios = ['-- Selecione o Membro --'] + sorted(df[col_usuario].unique().tolist()) 
        
        try:
            default_index = opcoes_usuarios.index(st.session_state.usuario_selecionado_id)
        except ValueError:
            default_index = 0
            
        usuario_selecionado = st.selectbox(
            "Selecione o Membro", 
            opcoes_usuarios, 
            index=default_index,
            key='select_user_update',
            on_change=lambda: st.session_state.__setitem__('usuario_selecionado_id', st.session_state.select_user_update)
        )
        
        st.session_state.usuario_selecionado_id = usuario_selecionado


        if usuario_selecionado != '-- Selecione o Membro --' and not df.empty and usuario_selecionado in df[col_usuario].values:
            
            dados_atuais = df[df[col_usuario] == usuario_selecionado].iloc[0]
            usuario_input_upar = dados_atuais[col_usuario]
            user_id_atual = dados_atuais.get(col_user_id, 'N/A')
            
            cargo_atual_dados = dados_atuais[col_cargo] 
            pontos_acumulados_anteriores = dados_atuais[col_pontos_acum]
            semana_atual_dados = int(dados_atuais[col_sem]) 
            mult_ind_anterior = dados_atuais[col_mult_ind]
            
            # Bloco de Informação do Membro
            with st.container():
                if cargo_atual_dados in METAS_PONTUACAO:
                    
                    cargo_index_default = CARGOS_LISTA.index(cargo_atual_dados)
                    
                    st.markdown(f"**Membro Selecionado:** `{usuario_input_upar}`") 
                    
                    # DESTAQUE: ID do Usuário (VERDE, SEM FUNDO)
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 5px;">
                            <strong>ID do Usuário:</strong> <span style="color: #198754; font-weight: bold;">{user_id_atual}</span>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    # 1. CARGO ATUAL
                    cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select_update')
                    
                    # --- Lógica para Mensagem de Info e Sugestão de Semana ---
                    
                    if dados_atuais[col_sit] in ["UPADO", "REBAIXADO", "MANTEVE"]:
                        st.info(f"Ciclo finalizado ({dados_atuais[col_sit]}). Registre a **Semana 1** do cargo atual (**{cargo_input}**).")
                        st.session_state.novo_cargo_apos_ciclo = None
                    else:
                        st.info("O ciclo é de 1 semana. O próximo registro será sempre a Semana 1.")

                    # --- MÉTRICAS PESSOAIS ---
                    st.markdown("---")
                    st.markdown("##### Métricas Pessoais (Dados Atuais)")
                    col_met_pessoal1, col_met_pessoal2, col_met_pessoal3 = st.columns(3)
                    
                    with col_met_pessoal1:
                        st.metric("Pontos Acumulados", f"{pontos_acumulados_anteriores:.1f}")
                    with col_met_pessoal2:
                        st.metric("Última Pontuação Semanal", f"{dados_atuais[col_pontos_sem]:.1f}")
                    with col_met_pessoal3:
                        st.metric("Multiplicador Atual", f"{mult_ind_anterior:.1f}x")
                    st.markdown("---")
                        
                    # 2. SEMANA DO CICLO (Fixado em 1)
                    semana_input = st.number_input(
                        f"Semana do Ciclo (1/1)", 
                        min_value=1, 
                        max_value=1, 
                        value=1, 
                        key='semana_input_update'
                    )
                    
                    st.markdown(f"**Status Ciclo:** Semana `{int(semana_input)}/1`")

                else:
                    st.error(f"Cargo '{cargo_atual_dados}' desconhecido. Revertendo para 'f*ck'.")
                    cargo_index_default = CARGOS_LISTA.index('f*ck')
                    cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select_update_err')
                    semana_input = st.number_input("Semana do Ciclo", min_value=1, value=1, key='semana_input_update_err')
            
            st.divider()

            st.markdown("##### Dados para o Registro Semanal")
            col_pts1, col_pts2 = st.columns(2)
            with col_pts1:
                mensagens_input = st.number_input("Mensagens Enviadas (Chat)", min_value=0, value=int(st.session_state.get('mensagens_input', 0)), step=10, key='mensagens_input', format="%d")
                
            with col_pts2:
                bonus_input = st.number_input("Bônus Extras (Pts)", min_value=0.0, value=st.session_state.get('bonus_input', 0.0), step=1.0, key='bonus_input')

            mult_ind_input = st.number_input(f"Multiplicador Individual (Atual: {mult_ind_anterior:.1f}x)", 
                                             min_value=0.1, value=float(mult_ind_anterior), step=0.1, key='mult_ind_input')

            st.markdown("---")
            if st.button("Salvar / Processar Semana", type="primary", key="save_update_button", use_container_width=True):
                st.session_state.salvar_button_clicked = True
            
        else:
            st.info("Selecione um membro acima para registrar a pontuação da semana.")
            usuario_input_upar = None
            
    # --- LÓGICA DE PROCESSAMENTO (EXECUÇÃO) ---
    if st.session_state.salvar_button_clicked and usuario_input_upar is not None:
        st.session_state.salvar_button_clicked = False
        
        df_reloaded = carregar_dados(SHEET_NAME_PRINCIPAL)
        dados_atuais = df_reloaded[df_reloaded[col_usuario] == st.session_state.select_user_update].iloc[0]
        
        mensagens_input = st.session_state.mensagens_input
        user_id_salvar = dados_atuais.get(col_user_id, 'N/A')
        pontos_base_input = mensagens_input / float(MENSAGENS_POR_PONTO)
        bonus_input = st.session_state.bonus_input
        mult_ind_input = st.session_state.mult_ind_input
        cargo_input = st.session_state.cargo_select_update 
        semana_registrada_manual = 1 
        
        pontos_acumulados_anteriores = dados_atuais[col_pontos_acum]
        pontos_total_final_anterior = dados_atuais[col_pontos_final]
        total_semanas_ciclo_cargo = 1

        # 1. Cálculo da Pontuação da Semana 
        pontos_semana_calc = calcular_pontuacao_semana(pontos_base_input, bonus_input, mult_ind_input)
        
        # Pontos acumulados sempre resetam a cada processamento
        pontos_acumulados_a_somar = 0.0 
        pontos_acumulados_total = pontos_acumulados_a_somar + pontos_semana_calc
        
        # 2. Avaliação de Situação
        is_ultima_semana = True
        multiplicador_up = 0 
        
        situacao_final, semanas_restantes = avaliar_situacao(
            cargo_input, 
            semana_registrada_manual, 
            pontos_acumulados_total
        )
        
        # 3. Lógica de UP/REBAIXAR
        novo_cargo_para_tabela = cargo_input 
        nova_semana_para_tabela = 1 
        novo_pontos_acumulados_para_tabela = 0.0 
        situacao_para_tabela = situacao_final
        
        if situacao_final in ["UPADO", "REBAIXADO", "MANTEVE"]:
            
            if situacao_final == "UPADO":
                try:
                    indice_atual = CARGOS_LISTA.index(cargo_input)
                    meta_up = METAS_PONTUACAO[cargo_input]['meta_up']
                    multiplicador_up = max(1, int(pontos_acumulados_total / float(meta_up)))
                    novo_indice = indice_atual + multiplicador_up
                    novo_cargo_para_tabela = CARGOS_LISTA[min(novo_indice, len(CARGOS_LISTA) - 1)]
                    if novo_indice >= len(CARGOS_LISTA):
                         multiplicador_up = len(CARGOS_LISTA) - 1 - indice_atual 
                except ValueError:
                    pass 

            elif situacao_final == "REBAIXADO":
                try:
                    indice_atual = CARGOS_LISTA.index(cargo_input)
                    if indice_atual > 0:
                        novo_cargo_para_tabela = CARGOS_LISTA[indice_atual - 1]
                        multiplicador_up = -1
                    else:
                        novo_cargo_para_tabela = 'f*ck'
                        multiplicador_up = 0
                except ValueError:
                    novo_cargo_para_tabela = 'f*ck'
                    multiplicador_up = 0
            
        # 4. Prepara os novos dados
        novo_dado = {
            col_usuario: usuario_input_upar, 
            col_user_id: user_id_salvar,
            col_cargo: novo_cargo_para_tabela, 
            col_sit: situacao_para_tabela, 
            col_sem: nova_semana_para_tabela, 
            col_pontos_acum: round(novo_pontos_acumulados_para_tabela, 1), 
            col_pontos_sem: round(pontos_semana_calc, 1),
            col_bonus_sem: round(bonus_input, 1),
            col_mult_ind: round(mult_ind_input, 1),
            'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            col_pontos_final: round(pontos_total_final_anterior + pontos_semana_calc, 1), 
        }
        
        # 5. Atualiza o DataFrame e salva
        df.loc[df[df[col_usuario] == usuario_input_upar].index[0]] = novo_dado

        if salvar_dados(df, SHEET_NAME_PRINCIPAL):
            limpar_campos_interface() 
            st.session_state.usuario_selecionado_id = usuario_input_upar 
            st.session_state.novo_cargo_apos_ciclo = novo_cargo_para_tabela
            
            msg_avanco = ""
            if situacao_final == "UPADO":
                msg_avanco = f" (Avançou **{multiplicador_up}** níveis para **{novo_cargo_para_tabela}**!)"
            elif situacao_final == "REBAIXADO":
                msg_avanco = f" (Rebaixou 1 nível para **{novo_cargo_para_tabela}**)"
            
            st.success(f"Dados salvos! Situação: **{situacao_para_tabela}** | Novo Cargo: **{novo_cargo_para_tabela}**{msg_avanco}")
            st.rerun()
    elif st.session_state.salvar_button_clicked:
         st.session_state.salvar_button_clicked = False
         st.error("Selecione um membro válido antes de salvar.")


# =========================================================================
# === COLUNA 3: TABELA DE ACOMPANHAMENTO (RANKING) ===
# =========================================================================
with col_ranking:
    st.subheader("Tabela de Acompanhamento e Ranking")
    
    st.info(f"Total de Membros Registrados: **{len(df)}**")
    
    if not df.empty: 
        df_display = df.copy()
        cargo_order = {cargo: i for i, cargo in enumerate(CARGOS_LISTA)}
        df_display['cargo_rank'] = df_display[col_cargo].map(cargo_order)
        
        df_display = df_display.sort_values(
            by=[col_pontos_final, 'cargo_rank'], 
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
            column_order=[col_usuario, col_user_id, col_cargo, col_sit, col_pontos_acum, col_pontos_sem, col_bonus_sem, col_mult_ind, 'Data_Ultima_Atualizacao']
        )
    else:
        st.warning("Nenhum membro cadastrado. Adicione um na coluna ao lado.")

    st.divider()

    st.subheader("Métricas Agregadas")

    if not df.empty:
        total_pontos_sem = df[col_pontos_sem].sum()
        total_bonus_sem = df[col_bonus_sem].sum() 
        
        col_met1, col_met2 = st.columns(2)
        
        with col_met1:
            st.metric("Total Pontos (Última Rodada)", f"{total_pontos_sem:.1f}")
        with col_met2:
            st.metric("Total Bônus (Última Rodada)", f"{total_bonus_sem:.1f}")
    else:
        st.info("Nenhuma métrica para agregar. Tabela vazia.")
