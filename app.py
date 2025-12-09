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
    # Garante que o DataFrame tem todas as colunas
    for col in colunas:
        if col not in df.columns:
            # Inicializa colunas faltantes com 0 ou valor padrão
            df[col] = df[colunas[0]].apply(lambda x: 0 if 'Pts' in col or 'Semana' in col else 'N/A')
            
    return df

def salvar_dados(df):
    df.to_csv(ARQUIVO_DADOS, index=False)

def calcular_pontos_semana(msgs, horas, rush_hour, desafio_tipo, participou_desafio):
    # Regra: Pts_msg = msgs / 50 | Pts_voz = horas * 2
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
    
    # AVALIAÇÃO FINAL: Acontece APENAS na última semana do ciclo
    if semana_atual >= ciclo_max:
        if pts_acumulados >= meta_area:
            situacao = "UPADO 🚀"
        elif pts_acumulados >= meta_manter:
            situacao = "MANTEVE ⚓"
        else:
            situacao = "REBAIXADO 🔻"
    else:
        # AVALIAÇÃO INTERMEDIÁRIA
        situacao = f"Em andamento ({semana_atual}/{ciclo_max})"
        
    return situacao

# --- INTERFACE (STREAMLIT) ---

st.set_page_config(page_title="Gestor de Cargos V3", layout="wide")
st.title("EXY - Tabela de Ups")

df = carregar_dados()

# Sidebar - Configurações Globais da Semana
st.sidebar.header("⚙️ Configurações da Semana")
weekend_ativo = st.sidebar.checkbox("Ativar Weekend (1.2x)?", value=False)
tipo_desafio = st.sidebar.selectbox("Desafio Semanal Ativo", OPCOES_DESAFIO)

# --- ABA 1: ADICIONAR / EDITAR USUÁRIO ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 Entrada de Dados Semanais")
    
    # Seleção de Usuário (Novo ou Existente)
    opcoes_usuarios = ['-- Novo Usuário --'] + sorted(df['Usuario'].unique().tolist())
    usuario_selecionado = st.selectbox("Selecione/Adicione o Usuário", opcoes_usuarios)
    
    # Variáveis de inicialização
    cargo_atual_dados = CARGOS_LISTA[-1] # Padrão 'low'
    semana_input = 1
    pts_acumulados_anteriores = 0.0

    if usuario_selecionado != '-- Novo Usuário --':
        dados_atuais = df[df['Usuario'] == usuario_selecionado].iloc[0]
        usuario_input = st.text_input("Nome do Usuário", value=dados_atuais['Usuario'], disabled=True)
        
        # Carrega dados do usuário existente
        cargo_atual_dados = dados_atuais['Cargo']
        pts_acumulados_anteriores = dados_atuais['Pts_Acumulados_Ciclo']
        semana_atual = dados_atuais['Semana_Atual']
        ciclo_max = METAS[cargo_atual_dados]['ciclo']
        
        st.info(f"Ciclo atual: **{cargo_atual_dados}** ({semana_atual}/{ciclo_max} semanas)")
        
        if dados_atuais['Situação'] in ["UPADO 🚀", "REBAIXADO 🔻", "MANTEVE ⚓"]:
            proxima_semana = 1
            pts_acumulados_anteriores = 0.0 # Zera para o novo ciclo
            st.warning("Usuário finalizou o ciclo. O próximo registro será para a **Semana 1** do novo cargo.")
        else:
            proxima_semana = semana_atual + 1
            if proxima_semana > ciclo_max: proxima_semana = ciclo_max
            
        semana_input = st.number_input(f"Próxima Semana do Ciclo (Máx: {ciclo_max})", 
                                       min_value=1, max_value=ciclo_max, value=int(proxima_semana))
        cargo_input = st.selectbox("Cargo Atual", CARGOS_LISTA, index=CARGOS_LISTA.index(cargo_atual_dados))

    else:
        usuario_input = st.text_input("Nome do Usuário")
        cargo_input = st.selectbox("Cargo Inicial", CARGOS_LISTA, index=CARGOS_LISTA.index('low'))
        semana_input = st.number_input("Semana do Ciclo (Sempre comece na 1)", min_value=1, value=1)


    st.markdown("---")
    msgs_input = st.number_input("Mensagens NESTA SEMANA", min_value=0, value=0)
    horas_input = st.number_input("Horas em Call NESTA SEMANA", min_value=0.0, value=0.0, step=0.5)
    
    st.markdown("---")
    st.write("**Bônus & Multiplicadores Individuais**")
    check_rush = st.checkbox("Participou Rush Hour? (1.5x)")
    check_desafio = st.checkbox("Participou Desafio Semanal?")
    bonus_fixo_input = st.number_input("Bônus Fixo ÚNICO (Streak, Pts Extras)", value=0.0)
    
    if st.button("Salvar / Atualizar Semana"):
        if usuario_input and usuario_input != '-- Novo Usuário --':
            
            # 1. Calcula os pontos da semana (com multiplicadores)
            pts_semana_multi = calcular_pontos_semana(msgs_input, horas_input, check_rush, tipo_desafio, check_desafio)
            
            # 2. Verifica a regra do Weekend (1.2x)
            meta_do_cargo = METAS[cargo_input]['meta_pts']
            pts_semana_final = pts_semana_multi
            if weekend_ativo and pts_semana_multi >= (meta_do_cargo * 0.70):
                pts_semana_final = pts_semana_multi * 1.2
                
            # 3. Adiciona bônus fixo
            pts_semana_final += bonus_fixo_input

            # 4. Acumula os pontos
            pts_acumulados_total = pts_acumulados_anteriores + pts_semana_final
            
            # 5. Avalia a situação (usa a nova semana de input)
            situacao = avaliar_situacao(cargo_input, pts_acumulados_total, semana_input)

            # --- Lógica de Atualização de Cargo e Reset (Bug Fix) ---
            novo_cargo = cargo_input 
            nova_semana = semana_input
            novo_pts_acumulados = pts_acumulados_total
            
            if situacao == "UPADO 🚀":
                novo_cargo = SEQUENCIA_PROMO.get(cargo_input, 'god')
                nova_semana = 1
                novo_pts_acumulados = 0.0
            elif situacao == "REBAIXADO 🔻":
                # Rebaixamento: um nível abaixo
                try:
                    indice_atual = CARGOS_LISTA.index(cargo_input)
                    if indice_atual > 0:
                        novo_cargo = CARGOS_LISTA[indice_atual - 1]
                    else:
                        novo_cargo = 'low'
                except ValueError:
                    novo_cargo = 'low'
                nova_semana = 1
                novo_pts_acumulados = 0.0
            elif situacao == "MANTEVE ⚓":
                nova_semana = 1
                novo_pts_acumulados = 0.0
            else:
                # Em andamento - Incrementa a semana para a próxima rodada (apenas para exibição na tabela)
                nova_semana = semana_input + 1


            # Prepara os novos dados
            novo_dado = {
                'Usuario': usuario_input,
                'Cargo': novo_cargo,
                'Semana_Atual': nova_semana,
                'Pts_Acumulados_Ciclo': novo_pts_acumulados,
                'Ultima_Semana_Msgs': msgs_input,
                'Ultima_Semana_Horas': horas_input,
                'Pts_Semana': round(pts_semana_final, 2),
                'Pts_Total_Final': round(pts_acumulados_total, 2), # Pontuação total final do ciclo (para visualização)
                'Situação': situacao,
                'Data_Ultima_Atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Salva no DataFrame (substitui a linha antiga ou cria uma nova)
            if usuario_input in df['Usuario'].values:
                df.loc[df[df['Usuario'] == usuario_input].index[0]] = novo_dado
            else:
                df = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)

            salvar_dados(df)
            
            # Mensagem de Feedback
            if situacao in ["UPADO 🚀", "REBAIXADO 🔻", "MANTEVE ⚓"]:
                 st.success(f"AVALIAÇÃO CONCLUÍDA! {usuario_input} | Novo Cargo: **{novo_cargo}** | Próximo Ciclo: Semana 1. (Resetado)")
            else:
                 st.success(f"Usuário {usuario_input} atualizado. Pontos Acumulados: {round(pts_acumulados_total, 2)}")
                 
            st.rerun()
        else:
            st.error("Digite um nome de usuário válido.")
            
    # Botão de Limpeza Total
    if st.button("🗑️ Limpar Tabela Inteira (Reset Total)") and st.checkbox("CONFIRMAR EXCLUSÃO TOTAL?"):
        df = carregar_dados() # Cria um DF vazio
        salvar_dados(df)
        st.rerun()

# --- ABA 2: VISUALIZAÇÃO DA TABELA ---
with col2:
    st.subheader("📊 Tabela de Acompanhamento")
    
    st.info(f"Total de Usuários: **{len(df)}** | Próxima Ação: Atualizar Semana e Salvar.")
    
    # Exibir a Tabela Principal
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
    if not df.empty:
        total_msgs = df['Ultima_Semana_Msgs'].sum()
        total_call = df['Ultima_Semana_Horas'].sum()
        st.metric("Total de Mensagens na Última Semana", total_msgs)
        st.metric("Total de Horas em Call na Última Semana", total_call)