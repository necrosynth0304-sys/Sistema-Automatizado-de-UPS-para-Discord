import streamlit as st
import pandas as pd
from datetime import datetime
import os 
import gspread 
from google.oauth2.service_account import Credentials 

# --- CONFIGURAÇÃO DAS REGRAS DO SISTEMA (PONTUAÇÃO E CICLOS) ---

# Os valores são (Meta UP / Meta Manter) em Pontos Totais no Ciclo
METAS_PONTUACAO = {
    'f*ck':    {'ciclo': 1, 'meta_up': 1200, 'meta_manter': 800},    # 1 Semana
    '100%':    {'ciclo': 1, 'meta_up': 1800, 'meta_manter': 1200},   # 1 Semana
    'woo':     {'ciclo': 2, 'meta_up': 2500, 'meta_manter': 1800},    # 2 Semanas
    'sex':     {'ciclo': 2, 'meta_up': 3000, 'meta_manter': 2200},    # 2 Semanas
    '?':       {'ciclo': 3, 'meta_up': 3500, 'meta_manter': 2800},    # 3 Semanas
    '!':       {'ciclo': 3, 'meta_up': 4200, 'meta_manter': 3500},    # 3 Semanas
    'aura':    {'ciclo': 3, 'meta_up': 4800, 'meta_manter': 4000},    # 3 Semanas
    'all wild':{'ciclo': 4, 'meta_up': 5500, 'meta_manter': 4800},    # 4 Semanas
    'cute':    {'ciclo': 4, 'meta_up': 6200, 'meta_manter': 5500},    # 4 Semanas
    '$':       {'ciclo': 4, 'meta_up': 7000, 'meta_manter': 6000},    # 4 Semanas
    'void':    {'ciclo': 5, 'meta_up': 7800, 'meta_manter': 7000},    # 5 Semanas
    'dawn':    {'ciclo': 5, 'meta_up': 8500, 'meta_manter': 7500},    # 5 Semanas
    'upper':   {'ciclo': 5, 'meta_up': 9500, 'meta_manter': 8500},    # 5 Semanas
}

CARGOS_LISTA = list(METAS_PONTUACAO.keys())

# --- NOME DA ABA PRINCIPAL ---
SHEET_NAME_PRINCIPAL = "dados sistema"


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

# --- CONSTANTES DE COLUNAS (DataFrame) ---
COLUNAS_PADRAO = [
    'usuario', 'cargo', 'situação', 'Semana_Atual', 
    'Pontos_Acumulados_Ciclo', 'Pontos_Semana', 'Bonus_Semana', 
    'Multiplicador_Individual', 'Data_Ultima_Atualizacao', 'Pontos_Total_Final'
]

col_usuario = 'usuario'
col_cargo = 'cargo'
col_sit = 'situação'
col_sem = 'Semana_Atual'
col_pontos_acum = 'Pontos_Acumulados_Ciclo'
col_pontos_sem = 'Pontos_Semana'
col_bonus_sem = 'Bonus_Semana'
col_mult_ind = 'Multiplicador_Individual'
col_pontos_final = 'Pontos_Total_Final'


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
        
        # Lógica para carregar DADOS PRINCIPAIS
        worksheet = sh.worksheet(sheet_name)
        df = pd.DataFrame(worksheet.get_all_records())
        
        if df.empty or not all(col in df.columns for col in COLUNAS_PADRAO):
            df = pd.DataFrame(columns=COLUNAS_PADRAO)
        
        # Conversão de tipos para colunas numéricas
        cols_to_convert = [col_sem, col_pontos_acum, col_pontos_sem, col_bonus_sem, col_mult_ind, col_pontos_final]
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        return df

    except Exception as e:
        st.error(f"ERRO: A conexão com a aba '{sheet_name}' falhou. Verifique se a aba existe e as permissões. ({e})")
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
        
        # Garante a ordem e tipos
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
    total_semanas_ciclo = meta['ciclo']
    
    if semana_atual < total_semanas_ciclo:
        # Se o ciclo ainda não terminou
        semanas_restantes = total_semanas_ciclo - semana_atual
        return f"Em andamento ({semana_atual}/{total_semanas_ciclo})", semanas_restantes
    
    else:
        # Fim do ciclo: Avaliação (Meta 1x)
        meta_up = meta['meta_up']
        meta_manter = meta['meta_manter']
        
        if pontos_acumulados >= meta_up:
            situacao = "UPADO"
        elif pontos_acumulados >= meta_manter:
            situacao = "MANTEVE"
        else:
            situacao = "REBAIXADO"
            
        return situacao, 0


def limpar_campos_interface():
    """Remove as chaves de session_state ligadas aos widgets de input para forçar o valor padrão (0.0) na próxima execução."""
    keys_to_delete = [
        'pontos_base_input', 
        'bonus_input', 
    ]
    
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]


# --- INTERFACE (STREAMLIT) ---

st.set_page_config(page_title="Sistema de Pontuação Ranking", layout="wide")
st.title("Sistema de Pontuação Ranking")
st.markdown("##### Gerenciamento de UP baseado em Pontuação (Chat)")

df = carregar_dados(SHEET_NAME_PRINCIPAL) # Carrega a aba 'dados sistema'

# Inicializa o state para o botão salvar e a seleção do usuário
if 'salvar_button_clicked' not in st.session_state:
    st.session_state.salvar_button_clicked = False
if 'usuario_selecionado_id' not in st.session_state:
    st.session_state.usuario_selecionado_id = '-- Selecione o Membro --'

# REORGANIZAÇÃO DE COLUNAS: 
col_ferramentas, col_upar, col_ranking = st.columns([1, 1.2, 2])

# Variável para cargo inicial (usada nas Ferramentas e Upar)
if CARGOS_LISTA:
    cargo_inicial_default = CARGOS_LISTA.index('f*ck')
else:
    cargo_inicial_default = 0
    
usuario_input_upar = None


# =========================================================================
# === COLUNA 1: FERRAMENTAS DE GESTÃO (Adicionar/Remover/Reset) ===
# =========================================================================
with col_ferramentas:
    st.subheader("Ferramentas de Gestão")
    
    # 1. Adicionar Novo Membro
    with st.container(border=True):
        st.markdown("##### Adicionar Novo Membro")
        
        usuario_input_add = st.text_input("Nome do Novo Usuário", key='usuario_input_add')
        cargo_input_add = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=cargo_inicial_default, key='cargo_select_add')
        
        if st.button("Adicionar Membro", type="primary", use_container_width=True):
            if usuario_input_add:
                if usuario_input_add in df[col_usuario].values:
                    st.error(f"O membro '{usuario_input_add}' já existe.")
                else:
                    # Define o ciclo inicial (1/Total)
                    total_ciclo_add = METAS_PONTUACAO.get(cargo_input_add, {'ciclo': 3})['ciclo']
                    
                    novo_dado_add = {
                        col_usuario: usuario_input_add, 
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
                    
                    # Concatena o novo membro ao DataFrame
                    df = pd.concat([df, pd.DataFrame([novo_dado_add])], ignore_index=True)
                    
                    if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                        st.session_state.usuario_selecionado_id = usuario_input_add # Seleciona o novo membro
                        st.success(f"Membro **{usuario_input_add}** adicionado!")
                        st.rerun()
            else:
                 st.error("Digite o nome do novo membro.")
        
    st.markdown("---")
    
    # 2. Remoção / Reset
    with st.container(border=True):
        st.markdown("##### Remoção / Reset de Tabela")

        if 'confirm_reset' not in st.session_state:
            st.session_state.confirm_reset = False

        # Remoção de Usuário
        if not df.empty:
            opcoes_remocao = sorted(df[col_usuario].unique().tolist())
            usuario_a_remover = st.selectbox("Selecione o Usuário para Remover", ['-- Selecione --'] + opcoes_remocao, key='remove_user_select')
            
            if usuario_a_remover != '-- Selecione --':
                st.warning(f"Confirme a remoção de **{usuario_a_remover}**. Permanente.")
                
                if st.button(f"Confirmar Remoção de {usuario_a_remover}", type="secondary", key='final_remove_button', use_container_width=True):
                    df = df[df[col_usuario] != usuario_a_remover]
                    if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                        st.session_state.usuario_selecionado_id = '-- Selecione o Membro --' # Limpa seleção
                        st.success(f"Membro {usuario_a_remover} removido com sucesso!")
                        st.rerun()
        
        st.markdown("---")
        
        # Reset Total
        if st.button("Resetar Tabela INTEIRA"):
            st.session_state.confirm_reset = True
            
        if st.session_state.confirm_reset:
            st.error("Tem certeza? Esta ação é IRREVERSÍVEL. Zera todos os dados dos membros.")
            
            if st.button("SIM, ZERAR TUDO", type="secondary", key='sim_reset', use_container_width=True):
                df_reset = pd.DataFrame(columns=df.columns) 
                if salvar_dados(df_reset, SHEET_NAME_PRINCIPAL):
                    st.session_state.usuario_selecionado_id = '-- Selecione o Membro --' # Limpa seleção
                    st.success("Tabela zerada com sucesso!")
                    st.session_state.confirm_reset = False
                    st.rerun()

# =========================================================================
# === COLUNA 2: UPAR (Entrada de Dados/Registro da Semana) ===
# =========================================================================
with col_upar:
    st.subheader("Upar (Registro de Dados)")
    
    # --- BLOCO: VISUALIZAÇÃO SIMPLES DE METAS ---
    
    # Cria um DataFrame de Metas para visualização
    metas_data_pontos_simples = []
    
    for cargo, metas in METAS_PONTUACAO.items():
        metas_data_pontos_simples.append({
            "Cargo": cargo,
            "Ciclo (Semanas)": metas['ciclo'],
            "Meta UP (Pts)": metas['meta_up'],
            "Meta Manter (Pts)": metas['meta_manter']
        })
        
    df_metas_pontos_simples = pd.DataFrame(metas_data_pontos_simples)

    with st.expander("Tabela de Metas (Ciclos e Pontos) 📋", expanded=False):
        st.dataframe(
            df_metas_pontos_simples,
            hide_index=True,
            use_container_width=True,
        )
    
    st.markdown("---")
    
    # Entrada de Dados
    with st.container(border=True):
        
        opcoes_usuarios = ['-- Selecione o Membro --'] + sorted(df[col_usuario].unique().tolist()) 
        
        # Encontra o índice da opção selecionada anteriormente (ou a default)
        try:
            default_index = opcoes_usuarios.index(st.session_state.usuario_selecionado_id)
        except ValueError:
            default_index = 0
            
        # Selectbox usa o state para persistir a seleção
        usuario_selecionado = st.selectbox(
            "Selecione o Membro", 
            opcoes_usuarios, 
            index=default_index,
            key='select_user_update',
            on_change=lambda: st.session_state.__setitem__('usuario_selecionado_id', st.session_state.select_user_update)
        )
        
        # Atualiza o state com o valor recém-selecionado
        st.session_state.usuario_selecionado_id = usuario_selecionado


        if usuario_selecionado != '-- Selecione o Membro --' and not df.empty and usuario_selecionado in df[col_usuario].values:
            
            dados_atuais = df[df[col_usuario] == usuario_selecionado].iloc[0]
            usuario_input_upar = dados_atuais[col_usuario]
            
            # --- CHAVE: LER O CARGO MAIS ATUALIZADO DO DATAFRAME ---
            cargo_atual_dados = dados_atuais[col_cargo] 
            # --------------------------------------------------------
            
            pontos_acumulados_anteriores = dados_atuais[col_pontos_acum]
            semana_atual_dados = int(dados_atuais[col_sem]) # Esta é a próxima semana a ser registrada
            mult_ind_anterior = dados_atuais[col_mult_ind]
            
            # Bloco de Informação do Membro
            with st.container():
                if cargo_atual_dados in METAS_PONTUACAO:
                    
                    # Usa o cargo_atual_dados (lido do DataFrame recarregado) como default
                    cargo_index_default = CARGOS_LISTA.index(cargo_atual_dados)
                    
                    st.markdown(f"**Membro:** `{usuario_input_upar}` | **Cargo Atual no DF:** `{cargo_atual_dados}`")
                    
                    # 1. CARGO ATUAL
                    # Garante que a caixa de seleção inicie no cargo lido do DF (o novo cargo, se houver UP)
                    cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select_update')
                    
                    # Atualiza o total de semanas do ciclo baseado no cargo SELECIONADO (CHAVE DINÂMICA)
                    total_semanas_ciclo_cargo_selecionado = METAS_PONTUACAO.get(cargo_input, {'ciclo': 1})['ciclo']
                    
                    # Determina o valor sugerido para a semana de entrada
                    if dados_atuais[col_sit] in ["UPADO", "REBAIXADO", "MANTEVE"]:
                        proxima_semana_sugerida = 1
                        # Mensagem clara sobre o resultado do ciclo anterior - USANDO O CARGO DO DF (cargo_atual_dados)
                        st.info(f"Ciclo finalizado ({dados_atuais[col_sit]}). Registre a **Semana 1** do cargo atual (**{cargo_input}**).")
                    else:
                        proxima_semana_sugerida = semana_atual_dados
                        if semana_atual_dados > total_semanas_ciclo_cargo_selecionado:
                            st.warning(f"O ciclo do cargo **{cargo_input}** está incompleto. Sugestão: Semana {total_semanas_ciclo_cargo_selecionado}.")
                            proxima_semana_sugerida = total_semanas_ciclo_cargo_selecionado
                        
                    # 2. SEMANA DO CICLO (Permitindo Edição Manual)
                    # A semana máxima é baseada no cargo SELECIONADO (cargo_input)
                    semana_input = st.number_input(
                        f"Semana do Ciclo (Máx: {total_semanas_ciclo_cargo_selecionado})", 
                        min_value=1, 
                        max_value=total_semanas_ciclo_cargo_selecionado, # Limita ao ciclo do cargo SELECIONADO
                        value=int(proxima_semana_sugerida), 
                        key='semana_input_update'
                    )
                    
                    st.markdown(f"**Status Ciclo:** Semana `{int(semana_input)}/{total_semanas_ciclo_cargo_selecionado}`")

                else:
                    st.error(f"Cargo '{cargo_atual_dados}' desconhecido. Revertendo para 'f*ck'.")
                    cargo_index_default = CARGOS_LISTA.index('f*ck')
                    cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select_update_err')
                    semana_input = st.number_input("Semana do Ciclo", min_value=1, value=1, key='semana_input_update_err')
            
            st.divider()

            st.markdown("##### Pontuação Semanal")
            col_pts1, col_pts2 = st.columns(2)
            with col_pts1:
                # Usa .get() para valores que serão limpos
                pontos_base_input = st.number_input("Pontos Base (Chat)", min_value=0.0, value=st.session_state.get('pontos_base_input', 0.0), step=1.0, key='pontos_base_input')
            with col_pts2:
                bonus_input = st.number_input("Bônus Extras", min_value=0.0, value=st.session_state.get('bonus_input', 0.0), step=1.0, key='bonus_input')

            mult_ind_input = st.number_input(f"Multiplicador Individual (Atual: {mult_ind_anterior:.1f}x)", 
                                             min_value=0.1, value=float(mult_ind_anterior), step=0.1, key='mult_ind_input')

            st.markdown("---")
            if st.button("Salvar / Processar Semana", type="primary", key="save_update_button", use_container_width=True):
                st.session_state.salvar_button_clicked = True
            
        else:
            st.info("Selecione um membro acima para registrar a pontuação da semana.")
            usuario_input_upar = None
            
    # --- LÓGICA DE PROCESSAMENTO (EXECUÇÃO) ---
    
    if st.session_state.salvar_button_clicked:
        st.session_state.salvar_button_clicked = False
        
        if usuario_input_upar is not None:
            
            # Recarrega para garantir dados frescos 
            df_reloaded = carregar_dados(SHEET_NAME_PRINCIPAL)
            
            # Use o valor do selectbox `select_user_update` para encontrar o membro no DF
            dados_atuais = df_reloaded[df_reloaded[col_usuario] == st.session_state.select_user_update].iloc[0]
            
            # Captura os dados de entrada
            pontos_base_input = st.session_state.pontos_base_input
            bonus_input = st.session_state.bonus_input
            mult_ind_input = st.session_state.mult_ind_input
            cargo_input = st.session_state.cargo_select_update # Cargo que ele estava no momento do registro
            semana_registrada_manual = st.session_state.semana_input_update 
            
            pontos_acumulados_anteriores = dados_atuais[col_pontos_acum]
            pontos_total_final_anterior = dados_atuais[col_pontos_final]
            total_semanas_ciclo_cargo = METAS_PONTUACAO.get(cargo_input, {'ciclo': 1})['ciclo']

            # 1. Cálculo da Pontuação da Semana 
            pontos_semana_calc = calcular_pontuacao_semana(
                pontos_base_input, 
                bonus_input, 
                mult_ind_input
            )
            
            # Lógica de Acumulação e Reset 
            if semana_registrada_manual == 1:
                 pontos_acumulados_a_somar = 0.0
            else:
                 pontos_acumulados_a_somar = pontos_acumulados_anteriores
            
            pontos_acumulados_total = pontos_acumulados_a_somar + pontos_semana_calc
            
            # 2. Determina se esta é a última semana
            is_ultima_semana = (semana_registrada_manual == total_semanas_ciclo_cargo)
            multiplicador_up = 0 
            
            if is_ultima_semana:
                situacao_final, semanas_restantes = avaliar_situacao(
                    cargo_input, 
                    semana_registrada_manual, 
                    pontos_acumulados_total
                )
            else:
                situacao_final = f"Em andamento ({semana_registrada_manual}/{total_semanas_ciclo_cargo})"
            
            # 3. Lógica de UP/REBAIXAR
            novo_cargo_para_tabela = cargo_input 
            nova_semana_para_tabela = semana_registrada_manual + 1
            novo_pontos_acumulados_para_tabela = pontos_acumulados_total
            situacao_para_tabela = situacao_final
            
            if is_ultima_semana and situacao_final in ["UPADO", "REBAIXADO", "MANTEVE"]:
                
                # Prepara o estado para o PRÓXIMO ciclo (Semana 1)
                nova_semana_para_tabela = 1
                novo_pontos_acumulados_para_tabela = 0.0 # Zera para o próximo ciclo
                
                if situacao_final == "UPADO":
                    try:
                        indice_atual = CARGOS_LISTA.index(cargo_input)
                        meta_up = METAS_PONTUACAO[cargo_input]['meta_up']
                        
                        # --- CORREÇÃO CÁLCULO DE UP MÚLTIPLO ---
                        # Usa float para garantir precisão e então floor para pegar o número inteiro de metas
                        multiplicador_up = max(1, int(pontos_acumulados_total / float(meta_up)))
                        
                        novo_indice = indice_atual + multiplicador_up
                        
                        # Limita para não ultrapassar o último cargo
                        if novo_indice < len(CARGOS_LISTA):
                            novo_cargo_para_tabela = CARGOS_LISTA[novo_indice]
                        else:
                            novo_cargo_para_tabela = CARGOS_LISTA[-1] 
                            multiplicador_up = len(CARGOS_LISTA) - 1 - indice_atual 
                        # --- FIM CORREÇÃO CÁLCULO DE UP MÚLTIPLO ---
                            
                    except ValueError:
                        pass 

                        
                elif situacao_final == "REBAIXADO":
                    try:
                        indice_atual = CARGOS_LISTA.index(cargo_input)
                        if indice_atual > 0:
                            novo_cargo_para_tabela = CARGOS_LISTA[indice_atual - 1]
                        else:
                            novo_cargo_para_tabela = 'f*ck' 
                    except ValueError:
                        novo_cargo_para_tabela = 'f*ck'
            
            # 4. Prepara os novos dados
            novo_dado = {
                col_usuario: usuario_input_upar, 
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
                limpar_campos_interface() # Limpa os campos de input de pontos/bônus
                st.session_state.usuario_selecionado_id = usuario_input_upar # Persiste o usuário selecionado
                
                # --- CHAVE: FORÇAR O NOVO CARGO NO SELECTBOX APÓS O UP ---
                if 'cargo_select_update' in st.session_state:
                    try:
                        novo_cargo_index = CARGOS_LISTA.index(novo_cargo_para_tabela)
                        st.session_state['cargo_select_update'] = novo_cargo_para_tabela # Atualiza o valor do selectbox antes do rerun
                    except ValueError:
                        pass # Se o cargo for inválido, deixa o selectbox como está.
                
                msg_avanco = ""
                if situacao_final == "UPADO":
                    msg_avanco = f" (**{multiplicador_up}** níveis!)"
                elif situacao_final == "REBAIXADO":
                    msg_avanco = " (1 nível)"
                
                # --- CHAVE: MENSAGEM DE SUCESSO EXIBINDO O NOVO CARGO ---
                st.success(f"Dados salvos! Situação: **{situacao_para_tabela}** | Próximo Cargo/Cargo Atual: **{novo_cargo_para_tabela}**{msg_avanco}")
                st.rerun()
        else:
            st.error("Selecione um membro válido antes de salvar.")


# =========================================================================
# === COLUNA 3: TABELA DE ACOMPANHAMENTO (RANKING) ===
# =========================================================================
with col_ranking:
    st.subheader("Tabela de Acompanhamento e Ranking")
    
    st.info(f"Total de Membros Registrados: **{len(df)}**")
    
    if not df.empty: 
        # Classifica por Pontuação Final (Total Geral) e Cargo
        df_display = df.sort_values(by=[col_pontos_final, col_cargo], ascending=[False, True])
                                    
        st.dataframe(
            df_display.style.map(
                lambda x: 'background-color: #e6ffed; color: green' if 'UPADO' in str(x) else 
                          ('background-color: #ffe6e6; color: red' if 'REBAIXADO' in str(x) else 
                           ('background-color: #fffac2; color: #8a6d3b' if 'MANTEVE' in str(x) else '')),
                subset=[col_sit]
            ),
            use_container_width=True,
            height=600,
            # Ordem das colunas na tabela de ranking
            column_order=[col_usuario, col_cargo, col_sit, col_pontos_acum, col_pontos_sem, col_bonus_sem, col_mult_ind, 'Data_Ultima_Atualizacao']
        )
    else:
        st.warning("Nenhum membro cadastrado. Adicione um na coluna ao lado.")

    st.divider()

    if not df.empty:
        st.subheader("Métricas Agregadas")
        
        total_pontos_sem = df[col_pontos_sem].sum()
        total_bonus_sem = df[col_pontos_sem].sum()
        
        col_met1, col_met2 = st.columns(2)
        
        with col_met1:
            st.metric("Total Pontos (Última Rodada)", f"{total_pontos_sem:.1f}")
        with col_met2:
            st.metric("Total Bônus (Última Rodada)", f"{total_bonus_sem:.1f}")
