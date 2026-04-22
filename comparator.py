"""
comparator.py — Engine de comparação e categorização de NFs
============================================================
Recebe dois DataFrames normalizados (saída do normalizer.py) e produz
um relatório de conciliação completo.

Regras de divergência aplicadas:

  Valor:
    R-V1  abs(valor_A - valor_B) <= 0.01  → OK
    R-V2  abs(valor_A - valor_B) >  0.01  → CRITICO

  Data:
    R-D1  datas idênticas                 → OK
    R-D2  diferença de 1 a 7 dias         → LEVE
    R-D3  diferença > 7 dias              → CRITICO

  CPF/CNPJ:
    R-C1  documentos idênticos            → OK
    R-C2  ambos preenchidos e diferentes  → CRITICO
    R-C3  um dos lados vazio/não-padrão   → LEVE

Classificação geral da NF:
    ✅ CONCILIADA          todos os campos OK
    ⚠️  DIVERGENCIA_LEVE   pelo menos 1 LEVE, nenhum CRITICO
    🔴 DIVERGENCIA_CRITICA pelo menos 1 CRITICO

Schema de saída (ResultadoComparacao):
    df_conciliadas         — NFs presentes em ambas as fontes, sem divergência
    df_divergentes         — NFs presentes em ambas as fontes, com divergência
    df_so_prefeitura       — NFs só na Fonte A (Prefeitura)
    df_so_sistema          — NFs só na Fonte B (Sistema)
    resumo                 — dict com totais e percentuais
"""

from __future__ import annotations

import pandas as pd
from datetime import date
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

OK      = 'OK'
LEVE    = 'LEVE'
CRITICO = 'CRITICO'

STATUS_CONCILIADA          = 'CONCILIADA'
STATUS_DIVERGENCIA_LEVE    = 'DIVERGENCIA_LEVE'
STATUS_DIVERGENCIA_CRITICA = 'DIVERGENCIA_CRITICA'

TOLERANCIA_VALOR_REAIS = 0.01   # R-V1
LIMITE_DATA_LEVE_DIAS  = 7      # R-D2 / R-D3


# ---------------------------------------------------------------------------
# Resultado principal
# ---------------------------------------------------------------------------

class ResultadoComparacao(NamedTuple):
    df_conciliadas:    pd.DataFrame
    df_divergentes:    pd.DataFrame
    df_so_prefeitura:  pd.DataFrame
    df_so_sistema:     pd.DataFrame
    resumo:            dict


# ---------------------------------------------------------------------------
# Regras individuais de campo
# ---------------------------------------------------------------------------

def _comparar_valor(valor_a: float, valor_b: float) -> tuple[str, float]:
    """
    Retorna (status, diferenca).
    R-V1: diferença <= 0.01 → OK
    R-V2: diferença >  0.01 → CRITICO
    """
    diff = abs(valor_a - valor_b)
    status = OK if diff <= TOLERANCIA_VALOR_REAIS else CRITICO
    return status, round(diff, 2)


def _comparar_data(data_a: date | None, data_b: date | None) -> tuple[str, int | None]:
    """
    Retorna (status, diferenca_dias).
    R-D1: datas idênticas         → OK
    R-D2: 1-7 dias de diferença   → LEVE
    R-D3: > 7 dias de diferença   → CRITICO
    Qualquer lado nulo             → LEVE (dado faltante)
    """
    if data_a is None or data_b is None:
        return LEVE, None

    diff_dias = abs((data_a - data_b).days)

    if diff_dias == 0:
        return OK, 0
    elif diff_dias <= LIMITE_DATA_LEVE_DIAS:
        return LEVE, diff_dias
    else:
        return CRITICO, diff_dias


def _comparar_cpf_cnpj(doc_a: str, doc_b: str) -> str:
    """
    Retorna status.
    R-C1: idênticos               → OK
    R-C2: ambos preenchidos e ≠   → CRITICO
    R-C3: um dos lados vazio      → LEVE
    """
    a_vazio = not doc_a or doc_a in ('', 'nan', 'None')
    b_vazio = not doc_b or doc_b in ('', 'nan', 'None')

    if a_vazio or b_vazio:
        return LEVE

    return OK if doc_a == doc_b else CRITICO


# ---------------------------------------------------------------------------
# Classificação geral da NF
# ---------------------------------------------------------------------------

def _classificar_nf(status_valor: str, status_data: str, status_doc: str) -> str:
    statuses = {status_valor, status_data, status_doc}
    if CRITICO in statuses:
        return STATUS_DIVERGENCIA_CRITICA
    if LEVE in statuses:
        return STATUS_DIVERGENCIA_LEVE
    return STATUS_CONCILIADA


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def comparar(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
) -> ResultadoComparacao:
    """
    Compara dois DataFrames normalizados (saída do normalizer.py).

    Parâmetros
    ----------
    df_a : DataFrame da Fonte A (Prefeitura), pós-normalização
    df_b : DataFrame da Fonte B (Sistema), pós-normalização

    Retorna
    -------
    ResultadoComparacao com os quatro DataFrames de saída e o resumo.
    """
    # --- validar schema de entrada ---
    colunas_esperadas = {'nf', 'valor', 'data', 'cpf_cnpj', 'tomador'}
    for nome, df in [('Fonte A', df_a), ('Fonte B', df_b)]:
        faltando = colunas_esperadas - set(df.columns)
        if faltando:
            raise ValueError(f'comparar(): {nome} — colunas ausentes: {faltando}')

    # --- índices por NF ---
    idx_a = df_a.set_index('nf')
    idx_b = df_b.set_index('nf')

    nfs_a = set(idx_a.index)
    nfs_b = set(idx_b.index)

    nfs_ambos      = nfs_a & nfs_b
    nfs_so_a       = nfs_a - nfs_b
    nfs_so_b       = nfs_b - nfs_a

    # --- NFs só em A ---
    df_so_prefeitura = (
        df_a[df_a['nf'].isin(nfs_so_a)]
        .copy()
        .reset_index(drop=True)
    )

    # --- NFs só em B ---
    df_so_sistema = (
        df_b[df_b['nf'].isin(nfs_so_b)]
        .copy()
        .reset_index(drop=True)
    )

    # --- NFs em ambos: comparação campo a campo ---
    registros_conciliadas  = []
    registros_divergentes  = []

    for nf in sorted(nfs_ambos, key=lambda x: x.zfill(10)):
        row_a = idx_a.loc[nf]
        row_b = idx_b.loc[nf]

        # campos individuais
        valor_a   = float(row_a['valor'])   if pd.notna(row_a['valor'])   else 0.0
        valor_b   = float(row_b['valor'])   if pd.notna(row_b['valor'])   else 0.0
        data_a    = row_a['data']            if pd.notna(row_a['data'])    else None
        data_b    = row_b['data']            if pd.notna(row_b['data'])    else None
        cpf_a     = str(row_a['cpf_cnpj']).strip()
        cpf_b     = str(row_b['cpf_cnpj']).strip()
        tomador_a = str(row_a['tomador']).strip()
        tomador_b = str(row_b['tomador']).strip()

        # aplicar regras
        st_valor, diff_valor = _comparar_valor(valor_a, valor_b)
        st_data,  diff_dias  = _comparar_data(data_a, data_b)
        st_doc               = _comparar_cpf_cnpj(cpf_a, cpf_b)

        classificacao = _classificar_nf(st_valor, st_data, st_doc)

        registro = {
            'nf':              nf,
            # Fonte A
            'valor_a':         valor_a,
            'data_a':          data_a,
            'cpf_cnpj_a':      cpf_a,
            'tomador_a':       tomador_a,
            # Fonte B
            'valor_b':         valor_b,
            'data_b':          data_b,
            'cpf_cnpj_b':      cpf_b,
            'tomador_b':       tomador_b,
            # resultado dos campos
            'status_valor':    st_valor,
            'diff_valor':      diff_valor,
            'status_data':     st_data,
            'diff_dias':       diff_dias,
            'status_doc':      st_doc,
            # classificação geral
            'classificacao':   classificacao,
        }

        if classificacao == STATUS_CONCILIADA:
            registros_conciliadas.append(registro)
        else:
            registros_divergentes.append(registro)

    df_conciliadas = pd.DataFrame(registros_conciliadas)
    df_divergentes = pd.DataFrame(registros_divergentes)

    # --- resumo ---
    total_a          = len(nfs_a)
    total_b          = len(nfs_b)
    total_conciliadas = len(df_conciliadas)
    total_divergentes = len(df_divergentes)
    total_so_a       = len(nfs_so_a)
    total_so_b       = len(nfs_so_b)
    total_comuns     = len(nfs_ambos)

    pct = lambda n, d: round(100 * n / d, 1) if d else 0.0

    resumo = {
        'total_fonte_a':           total_a,
        'total_fonte_b':           total_b,
        'total_comuns':            total_comuns,
        'total_conciliadas':       total_conciliadas,
        'total_divergentes':       total_divergentes,
        'total_so_prefeitura':     total_so_a,
        'total_so_sistema':        total_so_b,
        'pct_conciliadas':         pct(total_conciliadas, total_comuns),
        'pct_divergentes':         pct(total_divergentes, total_comuns),
        'valor_total_a':           round(df_a['valor'].sum(), 2),
        'valor_total_b':           round(df_b['valor'].sum(), 2),
        'valor_conciliadas_a':     round(df_conciliadas['valor_a'].sum(), 2) if not df_conciliadas.empty else 0.0,
        'valor_divergentes_a':     round(df_divergentes['valor_a'].sum(), 2) if not df_divergentes.empty else 0.0,
        'valor_so_prefeitura':     round(df_so_prefeitura['valor'].sum(), 2),
        'valor_so_sistema':        round(df_so_sistema['valor'].sum(), 2),
    }

    # divergentes por criticidade
    if not df_divergentes.empty:
        criticas = (df_divergentes['classificacao'] == STATUS_DIVERGENCIA_CRITICA).sum()
        leves    = (df_divergentes['classificacao'] == STATUS_DIVERGENCIA_LEVE).sum()
    else:
        criticas = leves = 0

    resumo['total_divergencias_criticas'] = int(criticas)
    resumo['total_divergencias_leves']    = int(leves)

    return ResultadoComparacao(
        df_conciliadas=df_conciliadas,
        df_divergentes=df_divergentes,
        df_so_prefeitura=df_so_prefeitura,
        df_so_sistema=df_so_sistema,
        resumo=resumo,
    )


# ---------------------------------------------------------------------------
# Relatório resumido no terminal
# ---------------------------------------------------------------------------

def imprimir_resumo(resultado: ResultadoComparacao) -> None:
    """Imprime o resumo da comparação no terminal."""
    r = resultado.resumo

    print(f'\n{"="*60}')
    print(f'  RESULTADO DA CONCILIAÇÃO')
    print(f'{"="*60}')
    print(f'  Fonte A (Prefeitura) : {r["total_fonte_a"]:>5} NFs   R$ {r["valor_total_a"]:>12,.2f}')
    print(f'  Fonte B (Sistema)    : {r["total_fonte_b"]:>5} NFs   R$ {r["valor_total_b"]:>12,.2f}')
    print(f'  {"─"*54}')
    print(f'  ✅ Conciliadas       : {r["total_conciliadas"]:>5} NFs   '
          f'({r["pct_conciliadas"]}% das comuns)   '
          f'R$ {r["valor_conciliadas_a"]:>12,.2f}')
    print(f'  ⚠️  Divergentes       : {r["total_divergentes"]:>5} NFs   '
          f'({r["pct_divergentes"]}% das comuns)')
    print(f'     └─ Críticas       : {r["total_divergencias_criticas"]:>5}')
    print(f'     └─ Leves          : {r["total_divergencias_leves"]:>5}')
    print(f'  🔴 Só Prefeitura     : {r["total_so_prefeitura"]:>5} NFs   R$ {r["valor_so_prefeitura"]:>12,.2f}')
    print(f'  🔵 Só Sistema        : {r["total_so_sistema"]:>5} NFs   R$ {r["valor_so_sistema"]:>12,.2f}')
    print(f'{"="*60}\n')

    if not resultado.df_divergentes.empty:
        print('  Detalhes das divergências:')
        print(f'  {"NF":>6}  {"STATUS":<20}  {"VALOR":>10}  {"DATA":>6}  {"DOC":>8}')
        print(f'  {"─"*58}')
        for _, row in resultado.df_divergentes.iterrows():
            diff_v = f'Δ R${row["diff_valor"]:,.2f}' if row['status_valor'] != OK else ''
            diff_d = f'Δ {row["diff_dias"]}d' if row['status_data'] != OK and row['diff_dias'] is not None else ''
            print(
                f'  {row["nf"]:>6}  '
                f'{row["classificacao"]:<22}  '
                f'V:{row["status_valor"]:<8} {diff_v:<12}  '
                f'D:{row["status_data"]:<8} {diff_d:<6}  '
                f'C:{row["status_doc"]}'
            )
        print()


# ---------------------------------------------------------------------------
# CLI para teste rápido
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    from reader import ler_arquivo
    from normalizer import normalizar

    if len(sys.argv) < 3:
        print('Uso: python comparator.py <arquivo_A> <arquivo_B>')
        sys.exit(1)

    arquivo_a = sys.argv[1]
    arquivo_b = sys.argv[2]

    df_raw_a, _ = ler_arquivo(arquivo_a, 'A')
    df_raw_b, _ = ler_arquivo(arquivo_b, 'B')

    res_a = normalizar(df_raw_a, 'A')
    res_b = normalizar(df_raw_b, 'B')

    resultado = comparar(res_a.df, res_b.df)
    imprimir_resumo(resultado)

    print('Amostra — Divergentes:')
    if not resultado.df_divergentes.empty:
        print(resultado.df_divergentes.head(5).to_string(index=False))
    else:
        print('  Nenhuma divergência encontrada.')
