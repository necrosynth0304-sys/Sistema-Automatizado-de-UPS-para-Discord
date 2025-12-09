import streamlit as st
import pandas as pd
from datetime import datetime
import os 
import gspread 
from google.oauth2.service_account import Credentials 

# --- CONFIGURAÇÃO DAS REGRAS DO SISTEMA (PONTUAÇÃO E CICLOS) ---

# Os valores são (Meta UP / Meta Manter) em Pontos Totais no Ciclo
# CICLOS ATUALIZADOS CONFORME SOLICITADO:
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
CARGOS_COM_MULT_ESPECIAL = ['f*ck', '100%'] # Cargos onde a Meta pode ser dobrada/triplicada

# --- CONFIGURAÇÃO DA SEMANA ATUAL (Global) ---
CONFIG_DEFAULT = {
    'semana_desafio_atual': 1,
    'total_semanas_ciclo': 3,
    'multiplicador_global': 1.0, 
    'meta_dobrada': False,
    'meta_triplicada': False
}
CONFIG_COLUNAS = list(CONFIG_DEFAULT.keys())

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
    """Lê os dados da planilha Google (aba de dados principais ou config)."""
    if gc is None:
        if 'gsheets_error' in st.session_state:
             st.error(st.session_state['gsheets_error'])
        return pd.DataFrame(columns=COLUNAS_PADRAO)
        
    try:
        SPREADSHEET_URL = st.secrets["gsheets_config"]["spreadsheet_url"]
        sh = gc.open_by_url(SPREADSHEET_URL)
        
        # Lógica para carregar CONFIGURAÇÕES
        if sheet_name == "Config":
            try:
                worksheet = sh.worksheet("Config")
                data = worksheet.get_all_records()
                if not data:
                    return pd.DataFrame([CONFIG_DEFAULT])
                df = pd.DataFrame(data)
                
                # Garante que as colunas numéricas da config são tratadas como tal
                for key in ['semana_desafio_atual', 'total_semanas_ciclo']:
                    if key in df.columns:
                        df[key] = pd.to_numeric(df[key], errors='coerce').fillna(CONFIG_DEFAULT.get(key, 0))
                for key in ['multiplicador_global']:
                    if key in df.columns:
                        df[key] = pd.to_numeric(df[key], errors='coerce').fillna(CONFIG_DEFAULT.get(key, 1.0))

                return df
            except gspread.WorksheetNotFound:
                st.warning("A aba 'Config' não foi encontrada. Usando configurações padrão.")
                return pd.DataFrame([CONFIG_DEFAULT])
        
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
        
        # Se for a aba principal, garantimos a ordem e tipos
        if sheet_name == SHEET_NAME_PRINCIPAL:
            df_to_save = df[COLUNAS_PADRAO].astype(str)
        # Se for a aba de Config, garantimos as colunas da config
        elif sheet_name == "Config":
             df_to_save = df[CONFIG_COLUNAS].astype(str)

        data = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
        
        worksheet.clear()
        worksheet.update(range_name='A1', values=data)
        
        st.cache_data.clear() 
        
        return True
        
    except Exception as e:
        st.error("ERRO CRÍTICO: Falha na Escrita ou Permissão Negada (403)!")
        st.exception(e)
        return False


def calcular_pontuacao_semana(pontos_base, bonus, mult_ind, mult_global):
    """Calcula a pontuação final da semana com todos os multiplicadores."""
    
    # Apenas o multiplicador de pontuação é aplicado aqui.
    pontos_final = (pontos_base + bonus) * mult_ind * mult_global
    
    return round(pontos_final, 1)


def avaliar_multiplicador_meta(cargo, meta_dobrada, meta_triplicada):
    """Determina o multiplicador de meta (1x, 2x ou 3x) baseado no cargo."""
    
    if cargo in CARGOS_COM_MULT_ESPECIAL:
        if meta_dobrada:
            return 2.0
        elif meta_triplicada:
            return 3.0
    
    # Para todos os outros cargos, ou se as flags não estiverem ativas, o multiplicador é 1x
    return 1.0


def avaliar_situacao(cargo, semana_atual, pontos_acumulados, mult_meta_config):
    """Avalia o UP/MANTER/REBAIXAR no final do ciclo."""
    
    meta = METAS_PONTUACAO[cargo]
    total_semanas_ciclo = meta['ciclo']
    
    if semana_atual < total_semanas_ciclo:
        # Se o ciclo ainda não terminou
        semanas_restantes = total_semanas_ciclo - semana_atual
        return f"Em andamento ({semana_atual}/{total_semanas_ciclo})", semanas_restantes
    
    else:
        # Fim do ciclo: Avaliação
        meta_up = meta['meta_up'] * mult_meta_config
        meta_manter = meta['meta_manter'] * mult_meta_config
        
        if pontos_acumulados >= meta_up:
            situacao = "UPADO"
        elif pontos_acumulados >= meta_manter:
            situacao = "MANTEVE"
        else:
            situacao = "REBAIXADO"
            
        return situacao, 0


# --- INTERFACE (STREAMLIT) ---

st.set_page_config(page_title="Sistema de Pontuação Ranking", layout="wide")
st.title("Sistema de Pontuação Ranking")
st.markdown("##### Gerenciamento de UP baseado em Pontuação (Chat)")

df = carregar_dados(SHEET_NAME_PRINCIPAL) # Carrega a aba 'dados sistema'
df_config = carregar_dados("Config") # Carrega a aba 'Config'
config_atual = df_config.iloc[0].to_dict()

# Variável de estado para o botão salvar
if 'salvar_button_clicked' not in st.session_state:
    st.session_state.salvar_button_clicked = False

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Entrada de Dados e Gestão")
    
    # Bloco de Métricas Globais
    mult_meta_display = "1.0x"
    if config_atual['meta_dobrada']:
        mult_meta_display = "2.0x (DOBRADA)"
    elif config_atual['meta_triplicada']:
        mult_meta_display = "3.0x (TRIPLICADA)"
        
    with st.container(border=True):
        st.markdown(f"**Semana do Desafio:** `{int(config_atual['semana_desafio_atual'])}`")
        st.markdown(f"**Multiplicador Global (Pontos):** `{config_atual['multiplicador_global']:.1f}x`")
        st.markdown(f"**Multiplicador Meta (f*ck/100%):** `{mult_meta_display}`")

    # Abas
    tab_reg, tab_conf = st.tabs(["Registro da Semana", "Configurações"])

    usuario_input = None
    if CARGOS_LISTA:
        cargo_inicial_default = CARGOS_LISTA.index('f*ck')
    else:
        cargo_inicial_default = 0

    # === ABA 1: REGISTRO DA SEMANA ===
    with tab_reg:
        
        opcoes_usuarios = ['-- Selecione o Membro --'] + sorted(df[col_usuario].unique().tolist()) 
        usuario_selecionado = st.selectbox("Selecione o Membro", opcoes_usuarios, key='select_user_update')
        
        if usuario_selecionado != '-- Selecione o Membro --' and not df.empty and usuario_selecionado in df[col_usuario].values:
            
            dados_atuais = df[df[col_usuario] == usuario_selecionado].iloc[0]
            usuario_input = dados_atuais[col_usuario]
            
            cargo_atual_dados = dados_atuais[col_cargo]
            pontos_acumulados_anteriores = dados_atuais[col_pontos_acum]
            semana_atual = int(dados_atuais[col_sem])
            mult_ind_anterior = dados_atuais[col_mult_ind]
            
            # Bloco de Informação do Membro
            with st.container(border=True):
                if cargo_atual_dados in METAS_PONTUACAO:
                    cargo_index_default = CARGOS_LISTA.index(cargo_atual_dados)
                    total_semanas_ciclo_cargo = METAS_PONTUACAO[cargo_atual_dados]['ciclo']
                    
                    st.markdown(f"**Membro:** `{usuario_input}` | **Cargo Atual:** `{cargo_atual_dados}`")
                    
                    if dados_atuais[col_sit] in ["UPADO", "REBAIXADO", "MANTEVE"]:
                        proxima_semana = 1
                        pontos_acumulados_anteriores = 0.0 
                        st.info("Ciclo finalizado. O próximo registro será na **Semana 1** do novo cargo.")
                    elif semana_atual == total_semanas_ciclo_cargo:
                        proxima_semana = total_semanas_ciclo_cargo # Mantém na última semana até processar
                        st.warning("Fim do ciclo! Registre os pontos finais e clique em processar.")
                    else:
                        proxima_semana = semana_atual + 1
                        
                    st.markdown(f"**Próxima Semana do Ciclo:** `{proxima_semana}/{total_semanas_ciclo_cargo}`")
                else:
                    st.error(f"Cargo '{cargo_atual_dados}' desconhecido. Revertendo para 'f*ck'.")
                    proxima_semana = 1
                    cargo_index_default = CARGOS_LISTA.index('f*ck')
            
            st.divider()

            semana_input = st.number_input("Semana do Ciclo (Leitura)", min_value=1, value=int(proxima_semana), disabled=True, key='semana_input_update')
            cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select_update')

            st.markdown("##### Pontuação Semanal")
            col_pts1, col_pts2 = st.columns(2)
            with col_pts1:
                pontos_base_input = st.number_input("Pontos Base (Chat)", min_value=0.0, value=0.0, step=1.0, key='pontos_base_input')
            with col_pts2:
                bonus_input = st.number_input("Bônus Extras", min_value=0.0, value=0.0, step=1.0, key='bonus_input')

            mult_ind_input = st.number_input(f"Multiplicador Individual (Atual: {mult_ind_anterior:.1f}x)", 
                                             min_value=0.1, value=float(mult_ind_anterior), step=0.1, key='mult_ind_input')

            st.markdown("---")
            if st.button("Salvar / Processar Semana", type="primary", key="save_update_button", use_container_width=True):
                st.session_state.salvar_button_clicked = True
            
        else:
            st.info("Selecione um membro acima para registrar a pontuação da semana.")
            usuario_input = None
            
    # === ABA 2: CONFIGURAÇÕES GLOBAIS ===
    with tab_conf:
        st.subheader("Configuração da Semana e Metas")
        
        # Leitura dos valores atuais da config
        semana_desafio = int(config_atual['semana_desafio_atual'])
        mult_global = config_atual['multiplicador_global']
        meta_dobrada = config_atual['meta_dobrada']
        meta_triplicada = config_atual['meta_triplicada']
        
        nova_semana_desafio = st.number_input("Semana Global de Desafio (Usada para reset de ciclo)", 
                                              min_value=1, value=semana_desafio, key='nova_semana_desafio')
        
        novo_mult_global = st.number_input("Multiplicador Global de Pontuação (Ex: 1.0, 1.5, 2.0)", 
                                           min_value=0.1, value=float(mult_global), step=0.1, key='novo_mult_global')
        
        st.markdown("##### Modificadores de Meta (Apenas para `f*ck` e `100%`)")
        
        col_meta1, col_meta2 = st.columns(2)
        with col_meta1:
            nova_meta_dobrada = st.checkbox("Meta Dobrada (x2)", value=meta_dobrada, key='nova_meta_dobrada')
        with col_meta2:
            nova_meta_triplicada = st.checkbox("Meta Triplicada (x3)", value=meta_triplicada, key='nova_meta_triplicada')

        if nova_meta_dobrada and nova_meta_triplicada:
            st.error("A meta não pode ser Dobrada E Triplicada ao mesmo tempo.")
            if 'salvar_config_button' in st.session_state:
                 st.session_state['salvar_config_button'] = False


        if st.button("Salvar Configurações Globais", type="secondary", use_container_width=True, key='salvar_config_button'):
            
            if nova_meta_dobrada and nova_meta_triplicada:
                st.error("Não foi possível salvar: Conflito de metas (Dobrada e Triplicada ativas).")
            else:
                novo_config = {
                    'semana_desafio_atual': nova_semana_desafio,
                    'total_semanas_ciclo': 3, # Valor fixo, mas mantido na config
                    'multiplicador_global': novo_mult_global, 
                    'meta_dobrada': nova_meta_dobrada,
                    'meta_triplicada': nova_meta_triplicada
                }
                
                df_config_novo = pd.DataFrame([novo_config])
                
                if salvar_dados(df_config_novo, sheet_name="Config"):
                    st.success("Configurações globais salvas com sucesso!")
                    st.cache_data.clear() 
                    st.rerun()

    # ----------------------------------------------------
    # --- LÓGICA DE PROCESSAMENTO (EXECUÇÃO) ---
    # ----------------------------------------------------
    
    if st.session_state.salvar_button_clicked:
        st.session_state.salvar_button_clicked = False
        
        if usuario_input is not None:
            
            # Recarrega para garantir dados frescos
            df_reloaded = carregar_dados(SHEET_NAME_PRINCIPAL)
            config_reloaded = carregar_dados("Config").iloc[0].to_dict()
            
            dados_atuais = df_reloaded[df_reloaded[col_usuario] == st.session_state.select_user_update].iloc[0]
            
            pontos_base_input = st.session_state.pontos_base_input
            bonus_input = st.session_state.bonus_input
            mult_ind_input = st.session_state.mult_ind_input
            cargo_input = st.session_state.cargo_select_update
            
            pontos_acumulados_anteriores = dados_atuais[col_pontos_acum]
            semana_atual = int(dados_atuais[col_sem])
            pontos_total_final_anterior = dados_atuais[col_pontos_final]

            # 1. Cálculo da Pontuação da Semana
            pontos_semana_calc = calcular_pontuacao_semana(
                pontos_base_input, 
                bonus_input, 
                mult_ind_input, 
                config_reloaded['multiplicador_global']
            )
            
            # 2. Avalia Multiplicador de Meta para o Cargo Específico
            mult_meta_config = avaliar_multiplicador_meta(
                cargo_input, 
                config_reloaded['meta_dobrada'],
                config_reloaded['meta_triplicada']
            )
            
            pontos_acumulados_total = pontos_acumulados_anteriores + pontos_semana_calc
            proxima_semana = semana_atual + 1
            
            # 3. Avaliação de Situação
            total_semanas_ciclo_cargo = METAS_PONTUACAO.get(cargo_input, {'ciclo': 3})['ciclo']
            
            if proxima_semana > total_semanas_ciclo_cargo:
                # É o final do ciclo, faz a avaliação
                situacao, semanas_restantes = avaliar_situacao(
                    cargo_input, 
                    total_semanas_ciclo_cargo, # Passa a semana final para forçar a avaliação
                    pontos_acumulados_total,
                    mult_meta_config
                )
            else:
                # Ciclo em andamento
                situacao = f"Em andamento ({proxima_semana}/{total_semanas_ciclo_cargo})"
                semanas_restantes = total_semanas_ciclo_cargo - proxima_semana
            
            # 4. Lógica de UP/REBAIXAR
            novo_cargo = cargo_input 
            nova_semana = proxima_semana
            novo_pontos_acumulados = pontos_acumulados_total
            
            if situacao in ["UPADO", "REBAIXADO", "MANTEVE"]:
                nova_semana = 1
                novo_pontos_acumulados = 0.0 # Zera para o próximo ciclo
                
                if situacao == "UPADO":
                    indice_atual = CARGOS_LISTA.index(cargo_input)
                    if indice_atual < len(CARGOS_LISTA) - 1:
                        novo_cargo = CARGOS_LISTA[indice_atual + 1]
                    else:
                        novo_cargo = CARGOS_LISTA[-1] # Cargo Máximo
                        
                elif situacao == "REBAIXADO":
                    try:
                        indice_atual = CARGOS_LISTA.index(cargo_input)
                        if indice_atual > 0:
                            novo_cargo = CARGOS_LISTA[indice_atual - 1]
                        else:
                            novo_cargo = 'f*ck' # Cargo Mínimo
                    except ValueError:
                        novo_cargo = 'f*ck'
            
            # 5. Prepara os novos dados
            novo_dado = {
                col_usuario: usuario_input, 
                col_cargo: novo_cargo, 
                col_sit: situacao,
                col_sem: nova_semana,
                col_pontos_acum: round(novo_pontos_acumulados, 1), 
                col_pontos_sem: round(pontos_semana_calc, 1),
                col_bonus_sem: round(bonus_input, 1),
                col_mult_ind: round(mult_ind_input, 1),
                'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                col_pontos_final: round(pontos_total_final_anterior + pontos_semana_calc, 1), 
            }
            
            # 6. Atualiza o DataFrame e salva
            df.loc[df[df[col_usuario] == usuario_input].index[0]] = novo_dado

            if salvar_dados(df, SHEET_NAME_PRINCIPAL):
                st.success(f"Dados salvos! Situação: {situacao} | Próximo Cargo: **{novo_cargo}**")
                st.rerun()
        else:
            st.error("Selecione um membro válido antes de salvar.")

    
    # ----------------------------------------------------
    # --- BLOCO: VISUALIZAÇÃO SIMPLES DE METAS ---
    # ----------------------------------------------------
    st.markdown("---")
    
    # Cria um DataFrame de Metas para visualização
    metas_data_pontos_simples = []
    
    for cargo, metas in METAS_PONTUACAO.items():
        metas_data_pontos_simples.append({
            "Cargo": cargo,
            "Ciclo (Semanas)": metas['ciclo'],
            "Meta UP (Pontos)": metas['meta_up'],
            "Meta Manter (Pontos)": metas['meta_manter']
        })
        
    df_metas_pontos_simples = pd.DataFrame(metas_data_pontos_simples)

    with st.expander("Tabela de Metas por Cargo (Pontos e Ciclos) 📋", expanded=False):
        st.dataframe(
            df_metas_pontos_simples,
            hide_index=True,
            use_container_width=True,
        )
    # ----------------------------------------------------
    
    st.subheader("Ferramentas de Gestão")
    with st.container(border=True):
        st.markdown("##### Adicionar Novo Membro")
        
        usuario_input_add = st.text_input("Nome do Novo Usuário", key='usuario_input_add')
        cargo_input_add = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=cargo_inicial_default, key='cargo_select_add')
        
        if st.button("Adicionar Membro", type="secondary", use_container_width=True):
            if usuario_input_add:
                if usuario_input_add in df[col_usuario].values:
                    st.error(f"O membro '{usuario_input_add}' já existe. Use a aba 'Registro da Semana'.")
                else:
                    novo_dado_add = {
                        col_usuario: usuario_input_add, 
                        col_cargo: cargo_input_add, 
                        col_sit: f"Em andamento (1/{METAS_PONTUACAO.get(cargo_input_add, {'ciclo': 3})['ciclo']})",
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
                        st.success(f"Membro **{usuario_input_add}** adicionado!")
                        st.rerun()
            else:
                 st.error("Digite o nome do novo membro.")
        
        st.markdown("---")
        st.markdown("##### Remoção / Reset")

        if 'confirm_reset' not in st.session_state:
            st.session_state.confirm_reset = False

        if not df.empty:
            opcoes_remocao = sorted(df[col_usuario].unique().tolist())
            usuario_a_remover = st.selectbox("Selecione o Usuário para Remover", ['-- Selecione --'] + opcoes_remocao, key='remove_user_select')
            
            if usuario_a_remover != '-- Selecione --':
                st.warning(f"Confirme a remoção de **{usuario_a_remover}**. Permanente.")
                
                if st.button(f"Confirmar Remoção de {usuario_a_remover}", type="secondary", key='final_remove_button', use_container_width=True):
                    df = df[df[col_usuario] != usuario_a_remover]
                    salvar_dados(df, SHEET_NAME_PRINCIPAL) 
                    st.success(f"Membro {usuario_a_remover} removido com sucesso!")
                    st.rerun()
        
        st.markdown("---")
        
        if st.button("Resetar Tabela INTEIRA"):
            st.session_state.confirm_reset = True
            
        if st.session_state.confirm_reset:
            st.error("Tem certeza? Esta ação é IRREVERSÍVEL. Zera todos os dados dos membros.")
            col_reset1, col_reset2 = st.columns(2)
            
            with col_reset1:
                if st.button("SIM, ZERAR TUDO", type="secondary", key='sim_reset'):
                    df_reset = pd.DataFrame(columns=df.columns) 
                    salvar_dados(df_reset, SHEET_NAME_PRINCIPAL) 
                    st.success("Tabela zerada com sucesso!")
                    st.session_state.confirm_reset = False
                    st.rerun()


# --- TABELA DE VISUALIZAÇÃO (COLUNA 2) ---
with col2:
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
            column_order=[col_usuario, col_cargo, col_sit, col_pontos_acum, col_pontos_sem, col_bonus_sem, col_mult_ind, 'Data_Ultima_Atualizacao']
        )
    else:
        st.warning("Nenhum membro cadastrado. Adicione um na coluna ao lado.")

    st.divider()

    if not df.empty:
        st.subheader("Métricas Agregadas")
        
        total_pontos_sem = df[col_pontos_sem].sum()
        total_bonus_sem = df[col_bonus_sem].sum()
        
        col_met1, col_met2 = st.columns(2)
        
        with col_met1:
            st.metric("Total Pontos (Última Rodada)", f"{total_pontos_sem:.1f}")
        with col_met2:
            st.metric("Total Bônus (Última Rodada)", f"{total_bonus_sem:.1f}")
