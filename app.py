import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURAÇÃO DAS REGRAS DO SISTEMA (Base Final) ---

# 1. Metas de Pontuação e Ciclo
METAS = {
    'god':   {'ciclo': 4, 'meta_pts': 1335, 'manter': 1234},
    'all':   {'ciclo': 4, 'meta_pts': 1135, 'manter': 969},
    'boss':  {'ciclo': 3, 'meta_pts': 725,  'manter': 500},
    'upper': {'ciclo': 3, 'meta_pts': 550,  'manter': 420},
    'sad':   {'ciclo': 3, 'meta_pts': 420,  'manter': 325},
    'big':   {'ciclo': 2, 'meta_pts': 169,  'manter': 130},
    'damn':  {'ciclo': 2, 'meta_pts': 130,  'manter': 104},
    'power': {'ciclo': 2, 'meta_pts': 91,   'manter': 78},
    'root':  {'ciclo': 1, 'meta_pts': 27,   'manter': 20},
    'low':   {'ciclo': 1, 'meta_pts': 20,   'manter': 13},
}

# 2. Sequência de Promoção e Rebaixamento
CARGOS_LISTA = list(METAS.keys())
SEQUENCIA_PROMO = {cargo_atual: CARGOS_LISTA[i + 1] 
                   for i, cargo_atual in enumerate(CARGOS_LISTA[:-1])}
SEQUENCIA_PROMO['god'] = 'god' # Cargo máximo

# Configuração de Arquivo e Opções
ARQUIVO_DADOS = 'sistema_cargos_final.csv'
OPCOES_DESAFIO = ["Nenhum", "Engajamento (2.0x Call)", "Mensagens (1.5x)", "Presença (1.5x)"]

# --- FUNÇÕES DE DADOS E LÓGICA ---

def carregar_dados():
    colunas = [
        'Usuario', 'Cargo', 'Semana_Atual', 'Pts_Acumulados_Ciclo', 
        'Ultima_Semana_Msgs', 'Ultima_Semana_Horas', 'Pts_Semana', 
        'Pts_Total_Final', 'Situação', 'Data_Ultima_Atualizacao'
    ]
    if not os.path.exists(ARQUIVO_DADOS):
        return pd.DataFrame(columns=colunas)
        
    df = pd.read_csv(ARQUIVO_DADOS)
    for col in colunas:
        if col not in df.columns:
            df[col] = df[colunas[0]].apply(lambda x: 0 if 'Pts' in col or 'Semana' in col else 'N/A')
            
    return df

def salvar_dados(df):
    df.to_csv(ARQUIVO_DADOS, index=False)

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
    
    if semana_atual >= ciclo_max:
        if pts_acumulados >= meta_area:
            situacao = "UPADO"
        elif pts_acumulados >= meta_manter:
            situacao = "MANTEVE"
        else:
            situacao = "REBAIXADO"
    else:
        situacao = f"Em andamento ({semana_atual}/{ciclo_max})"
        
    return situacao

# --- INTERFACE (STREAMLIT) ---

st.set_page_config(page_title="Sistema de Ups EXY", layout="wide")
st.title("Sistema de Ups EXY")

df = carregar_dados()

# Sidebar - Configurações Globais da Semana
st.sidebar.header("Configurações da Semana")
weekend_ativo = st.sidebar.checkbox("Ativar Weekend (1.2x)?", value=False)
tipo_desafio = st.sidebar.selectbox("Desafio Semanal Ativo", OPCOES_DESAFIO)

# --- ABA 1: ADICIONAR / EDITAR USUÁRIO ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Entrada de Dados Semanais")
    
    opcoes_usuarios = ['-- Novo Usuário --'] + sorted(df['Usuario'].unique().tolist())
    usuario_selecionado = st.selectbox("Selecione/Adicione o Usuário", opcoes_usuarios, key='select_user')
    
    cargo_atual_dados = CARGOS_LISTA[-1] 
    semana_input_value = 1
    pts_acumulados_anteriores = 0.0
    cargo_index_default = CARGOS_LISTA.index('low')

    if usuario_selecionado != '-- Novo Usuário --':
        dados_atuais = df[df['Usuario'] == usuario_selecionado].iloc[0]
        usuario_input = st.text_input("Nome do Usuário", value=dados_atuais['Usuario'], disabled=True)
        
        cargo_atual_dados = dados_atuais['Cargo']
        pts_acumulados_anteriores = dados_atuais['Pts_Acumulados_Ciclo']
        semana_atual = dados_atuais['Semana_Atual']
        ciclo_max = METAS[cargo_atual_dados]['ciclo']
        cargo_index_default = CARGOS_LISTA.index(cargo_atual_dados)
        
        st.info(f"Ciclo atual: **{cargo_atual_dados}** ({semana_atual}/{ciclo_max} semanas)")
        
        if dados_atuais['Situação'] in ["UPADO", "REBAIXADO", "MANTEVE"]:
            proxima_semana = 1
            pts_acumulados_anteriores = 0.0 
            st.warning("Usuário finalizou o ciclo. Próximo registro será na **Semana 1** do novo cargo.")
        else:
            proxima_semana = semana_atual + 1
            if proxima_semana > ciclo_max: proxima_semana = ciclo_max
            
        semana_input_value = int(proxima_semana)
        
        semana_input = st.number_input(f"Próxima Semana do Ciclo (Máx: {ciclo_max})", 
                                       min_value=1, max_value=ciclo_max, value=semana_input_value, key='semana_input')
        cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=cargo_index_default, key='cargo_select')

    else:
        usuario_input = st.text_input("Nome do Usuário")
        cargo_input = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=CARGOS_LISTA.index('low'))
        semana_input = st.number_input("Semana do Ciclo (Sempre comece na 1)", min_value=1, value=1)


    st.markdown("---")
    msgs_input = st.number_input("Mensagens NESTA SEMANA", min_value=0, value=0, key='msgs_input')
    horas_input = st.number_input("Horas em Call NESTA SEMANA", min_value=0.0, value=0.0, step=0.5, key='horas_input')
    
    st.markdown("---")
    st.write("**Bônus e Multiplicadores Individuais**")
    check_rush = st.checkbox("Participou Rush Hour? (1.5x)", key='rush_check')
    check_desafio = st.checkbox("Participou Desafio Semanal?", key='desafio_check')
    bonus_fixo_input = st.number_input("Bônus Fixo ÚNICO (Streak, Pts Extras)", value=0.0, key='bonus_input')
    
    
    # ----------------------------------------------------
    # --- BOTÃO DE SALVAR ---
    # ----------------------------------------------------

    if st.button("Salvar / Atualizar Semana", type="primary"):
        if usuario_input and usuario_input != '-- Novo Usuário --':
            
            # --- Lógica de Cálculo e Avaliação (Mantida) ---
            pts_semana_multi = calcular_pontos_semana(msgs_input, horas_input, check_rush, tipo_desafio, check_desafio)
            meta_do_cargo = METAS[cargo_input]['meta_pts']
            pts_semana_final = pts_semana_multi
            if weekend_ativo and pts_semana_multi >= (meta_do_cargo * 0.70):
                pts_semana_final = pts_semana_multi * 1.2
            pts_semana_final += bonus_fixo_input

            pts_acumulados_total = pts_acumulados_anteriores + pts_semana_final
            situacao = avaliar_situacao(cargo_input, pts_acumulados_total, semana_input)

            novo_cargo = cargo_input 
            
            # Determina a próxima semana e o novo acumulado APÓS a avaliação
            if situacao in ["UPADO", "REBAIXADO", "MANTEVE"]:
                nova_semana = 1
                novo_pts_acumulados = 0.0
                
                # Ajusta o cargo se UPADO/REBAIXADO
                if situacao == "UPADO":
                    novo_cargo = SEQUENCIA_PROMO.get(cargo_input, 'god')
                elif situacao == "REBAIXADO":
                    try:
                        indice_atual = CARGOS_LISTA.index(cargo_input)
                        if indice_atual > 0:
                            novo_cargo = CARGOS_LISTA[indice_atual - 1]
                        else:
                            novo_cargo = 'low'
                    except ValueError:
                        novo_cargo = 'low'
            else:
                nova_semana = semana_input + 1
                if nova_semana > METAS[cargo_input]['ciclo']:
                    nova_semana = METAS[cargo_input]['ciclo']
                novo_pts_acumulados = pts_acumulados_total


            # Prepara os novos dados
            novo_dado = {
                'Usuario': usuario_input, 'Cargo': novo_cargo, 'Semana_Atual': nova_semana,
                'Pts_Acumulados_Ciclo': novo_pts_acumulados, 'Ultima_Semana_Msgs': msgs_input,
                'Ultima_Semana_Horas': horas_input, 'Pts_Semana': round(pts_semana_final, 2),
                'Pts_Total_Final': round(pts_acumulados_total, 2), 'Situação': situacao,
                'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Salva no DataFrame (substitui a linha antiga ou cria uma nova)
            if usuario_input in df['Usuario'].values:
                df.loc[df[df['Usuario'] == usuario_input].index[0]] = novo_dado
            else:
                df = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)

            salvar_dados(df)
            
            st.success(f"Dados salvos! Situação: {situacao} | Próximo Cargo: **{novo_cargo}**")
            st.rerun()
        else:
            st.error("Selecione ou digite um nome de usuário válido.")
    
    st.markdown("---")

    # ------------------------------------------------------------------
    # --- SEÇÃO: REMOÇÃO DE USUÁRIOS POR LISTA ---
    # ------------------------------------------------------------------
    st.subheader("Remover Usuários")
    
    if not df.empty:
        opcoes_remocao = sorted(df['Usuario'].unique().tolist())
        usuario_a_remover = st.selectbox("Selecione o Usuário para Remover", ['-- Selecione --'] + opcoes_remocao, key='remove_user_select')
        
        if usuario_a_remover != '-- Selecione --':
            st.warning(f"Confirme a remoção de **{usuario_a_remover}**. Esta ação é permanente.")
            
            if st.button(f"Confirmar Remoção de {usuario_a_remover}", type="secondary", key='final_remove_button'):
                df = df[df['Usuario'] != usuario_a_remover]
                salvar_dados(df)
                st.success(f"Usuário {usuario_a_remover} removido com sucesso!")
                st.rerun()
    else:
        st.info("Não há usuários na tabela para remover.")


    st.markdown("---")

    # --- RESET TOTAL ---
    st.subheader("Reset Global")
    
    if 'confirm_reset' not in st.session_state:
        st.session_state.confirm_reset = False

    if st.button("Resetar Tabela INTEIRA"):
        st.session_state.confirm_reset = True
        
    if st.session_state.confirm_reset:
        st.warning("Tem certeza? Esta ação é irreversível e apagará TODOS os dados salvos.")
        col_reset1, col_reset2 = st.columns(2)
        
        with col_reset1:
            if st.button("SIM, ZERAR TUDO", type="secondary"):
                df = carregar_dados().iloc[0:0]
                salvar_dados(df)
                st.success("Tabela zerada com sucesso!")
                st.session_state.confirm_reset = False
                st.rerun()
        with col_reset2:
            if st.button("NÃO, CANCELAR", type="secondary"):
                st.session_state.confirm_reset = False
                st.rerun()


# --- ABA 2: VISUALIZAÇÃO DA TABELA ---
with col2:
    st.subheader("Tabela de Acompanhamento")
    
    st.info(f"Total de Usuários: **{len(df)}** | Próxima Ação: Atualizar Semana e Salvar.")
    
    if not df.empty:
        df_display = df.sort_values(by=['Pts_Acumulados_Ciclo', 'Cargo'], 
                                    ascending=[False, True])
                                    
        st.dataframe(
            df_display.style.applymap(
                lambda x: 'background-color: #d4edda; color: green' if 'UPADO' in str(x) else 
                          ('background-color: #f8d7da; color: red' if 'REBAIXADO' in str(x) else ''),
                subset=['Situação']
            ),
            use_container_width=True,
            height=600,
            column_order=['Usuario', 'Cargo', 'Situação', 'Semana_Atual', 'Pts_Acumulados_Ciclo', 'Pts_Semana', 'Data_Ultima_Atualizacao']
        )
    else:
        st.warning("Nenhum usuário cadastrado. Adicione um usuário na coluna ao lado.")

    st.markdown("---")

    ## Nova Seção: Métricas de Atividade
    
    if not df.empty:
        # 1. Métricas Globais (Soma de todos os últimos registros)
        st.subheader("Atividade Agregada do Grupo")
        total_msgs = df['Ultima_Semana_Msgs'].sum()
        total_call = df['Ultima_Semana_Horas'].sum()
        st.metric("Total Mensagens (Última Rodada)", total_msgs)
        st.metric("Total Horas Call (Última Rodada)", total_call)
        
        # 2. Métricas Individuais (Filtradas pelo usuário selecionado na col1)
        # O 'usuario_selecionado' vem da col1
        if usuario_selecionado != '-- Novo Usuário --' and usuario_selecionado in df['Usuario'].values:
            
            dados_individuais = df[df['Usuario'] == usuario_selecionado].iloc[0]
            
            st.markdown("---")
            st.subheader(f"Última Atividade de {usuario_selecionado}")
            st.metric("Mensagens Registradas", dados_individuais['Ultima_Semana_Msgs'])
            st.metric("Horas em Call Registradas", dados_individuais['Ultima_Semana_Horas'])
```

