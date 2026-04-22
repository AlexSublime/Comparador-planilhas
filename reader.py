"""
reader.py — Leitura das fontes de dados para conciliação de NFs
================================================================
Fonte A: ExtratoNotasPrestador_*.xls  (HTML disfarçado de XLS, portal NFS-e Peruíbe)
Fonte B: Atendimento_x_Financeiro_*.csv  (CSV sep=';' encoding='latin-1')
         Atendimento_x_Financeiro_*.xls  (XLS padrão)

Ambas as funções retornam um DataFrame com o schema padrão:
    nf          str   — número da NF (sem zeros à esquerda)
    valor       float — valor total da NF (2 casas decimais)
    data        date  — data de emissão
    cpf_cnpj    str   — CPF (11 dígitos) ou CNPJ (14 dígitos), só números
    tomador     str   — nome do tomador (informativo)
"""

import re
import os
import pandas as pd
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema padrão de saída
# ---------------------------------------------------------------------------

COLUNAS_PADRAO = ['nf', 'valor', 'data', 'cpf_cnpj', 'tomador']


# ---------------------------------------------------------------------------
# Helpers de normalização (usados internamente pelo reader)
# ---------------------------------------------------------------------------

def _normalizar_nf(serie: pd.Series) -> pd.Series:
    """Remove zeros à esquerda e espaços. Retorna str."""
    return serie.astype(str).str.strip().str.lstrip('0')


def _normalizar_valor(serie: pd.Series) -> pd.Series:
    """
    Converte para float com 2 casas decimais.
    Aceita: '350,00' | '350.00' | 30000 (inteiro sem formatação)
    Regra: remove separador de milhar (.) antes de trocar vírgula por ponto.
    """
    return (
        serie.astype(str)
        .str.strip()
        .str.replace(r'\.(?=\d{3})', '', regex=True)   # remove ponto de milhar
        .str.replace(',', '.', regex=False)
        .apply(pd.to_numeric, errors='coerce')
        .round(2)
    )


def _normalizar_cpf_cnpj(serie: pd.Series) -> pd.Series:
    """Remove pontuação (. - /) e espaços. Retorna str com só dígitos."""
    return (
        serie.astype(str)
        .str.strip()
        .str.replace(r'[.\-/\s]', '', regex=True)
    )


# ---------------------------------------------------------------------------
# Fonte A — Prefeitura (XLS = HTML disfarçado)
# ---------------------------------------------------------------------------

def ler_fonte_a_xls(path: str | Path) -> pd.DataFrame:
    """
    Lê o arquivo ExtratoNotasPrestador_*.xls exportado pelo portal NFS-e de Peruíbe.

    O arquivo é HTML disfarçado de XLS. A tabela relevante está no índice 2
    e usa header multi-index [0, 1]. A primeira linha de dados fica embutida
    no cabeçalho e precisa ser reconstruída manualmente.

    Parâmetros
    ----------
    path : str ou Path
        Caminho para o arquivo .xls

    Retorna
    -------
    pd.DataFrame com colunas: nf, valor, data, cpf_cnpj, tomador
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'Arquivo não encontrado: {path}')

    # --- leitura ---
    try:
        tables = pd.read_html(str(path), encoding='utf-8', header=[0, 1])
    except Exception as e:
        raise ValueError(f'Erro ao ler Fonte A ({path.name}): {e}')

    if len(tables) < 3:
        raise ValueError(
            f'Fonte A ({path.name}): esperado ao menos 3 tabelas, '
            f'encontrado {len(tables)}.'
        )

    df = tables[2].copy()

    # --- reconstrução da primeira linha perdida no multi-index ---
    first_row = {col[0]: col[1] for col in df.columns}
    df.columns = [col[0] for col in df.columns]
    df = pd.concat([pd.DataFrame([first_row]), df], ignore_index=True)

    # --- verificação de colunas obrigatórias ---
    colunas_necessarias = {'NOTA', 'VL. NOTA', 'DT. INCLUSÃO', 'CNPJ/CPF', 'TOMADOR'}
    faltando = colunas_necessarias - set(df.columns)
    if faltando:
        raise ValueError(
            f'Fonte A ({path.name}): colunas não encontradas: {faltando}\n'
            f'Colunas disponíveis: {list(df.columns)}'
        )

    # --- seleção e cópia ---
    df = df[['NOTA', 'VL. NOTA', 'DT. INCLUSÃO', 'CNPJ/CPF', 'TOMADOR']].copy()

    # --- remover linhas de totais/rodapé (NOTA não numérica) ---
    df = df[df['NOTA'].astype(str).str.strip().str.replace(r'\D', '', regex=True).str.len() > 0]
    df = df[~df['NOTA'].astype(str).str.upper().str.contains('TOTAL|NF|NOTA', na=False)]

    # --- normalização ---
    df['nf']       = _normalizar_nf(df['NOTA'])
    df['valor']    = _normalizar_valor(df['VL. NOTA'])
    df['cpf_cnpj'] = _normalizar_cpf_cnpj(df['CNPJ/CPF'])
    df['tomador']  = df['TOMADOR'].astype(str).str.strip()

    # data: 'dd/mm/aaaa hh:mm:ss'
    df['data'] = pd.to_datetime(
        df['DT. INCLUSÃO'].astype(str).str.strip(),
        format='%d/%m/%Y %H:%M:%S',
        errors='coerce'
    ).dt.date

    # --- remover linhas sem NF válida ou sem data ---
    df = df[df['nf'].str.len() > 0]
    df = df[df['data'].notna()]
    df = df[df['valor'].notna()]

    return df[COLUNAS_PADRAO].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Fonte B — Sistema de Atendimento (CSV ou XLS)
# ---------------------------------------------------------------------------

def ler_fonte_b(path: str | Path) -> pd.DataFrame:
    """
    Lê o arquivo Atendimento_x_Financeiro_*.csv ou *.xls exportado pelo
    sistema de atendimento.

    CSV: separador ';', encoding 'latin-1'.
    XLS: leitura padrão com openpyxl/xlrd.

    Uma NF pode aparecer em múltiplas linhas (parcelas de cartão).
    A deduplicação é feita por 'N. Fiscal', mantendo a primeira ocorrência
    (valor bruto é idêntico em todas as parcelas).

    Parâmetros
    ----------
    path : str ou Path
        Caminho para o arquivo .csv ou .xls/.xlsx

    Retorna
    -------
    pd.DataFrame com colunas: nf, valor, data, cpf_cnpj, tomador
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'Arquivo não encontrado: {path}')

    ext = path.suffix.lower()

    # --- leitura ---
    try:
        if ext == '.csv':
            # index_col=False necessário: o CSV tem 1 coluna a mais nos dados do que
            # no header (Protocolo), e pandas usaria a col 0 como índice por padrão,
            # deslocando todo o mapeamento de colunas.
            df = pd.read_csv(str(path), sep=';', encoding='latin-1', dtype=str, index_col=False)
        elif ext in ('.xls', '.xlsx'):
            df = pd.read_excel(str(path), dtype=str)
        else:
            raise ValueError(f'Formato não suportado para Fonte B: {ext}')
    except Exception as e:
        raise ValueError(f'Erro ao ler Fonte B ({path.name}): {e}')

    # --- verificação de colunas obrigatórias ---
    colunas_necessarias = {'N. Fiscal', 'NF Bruto', 'D. Emissão', 'CPF Paciente', 'Paciente'}
    faltando = colunas_necessarias - set(df.columns)
    if faltando:
        raise ValueError(
            f'Fonte B ({path.name}): colunas não encontradas: {faltando}\n'
            f'Colunas disponíveis: {list(df.columns)}'
        )

    # --- filtrar linhas sem NF (pagamentos internos, vacinas a cobrar, etc.) ---
    df = df[df['N. Fiscal'].notna()]
    df = df[df['N. Fiscal'].astype(str).str.strip() != '']
    df = df[df['N. Fiscal'].astype(str).str.strip() != 'nan']

    # --- deduplica por N. Fiscal (mantém primeira ocorrência) ---
    df = df.groupby('N. Fiscal', sort=False).first().reset_index()

    # --- normalização ---
    df['nf']       = _normalizar_nf(df['N. Fiscal'])
    df['valor']    = _normalizar_valor(df['NF Bruto'])
    df['cpf_cnpj'] = _normalizar_cpf_cnpj(df['CPF Paciente'])
    df['tomador']  = df['Paciente'].astype(str).str.strip()

    # data: 'dd/mm/aaaa'
    df['data'] = pd.to_datetime(
        df['D. Emissão'].astype(str).str.strip(),
        format='%d/%m/%Y',
        errors='coerce'
    ).dt.date

    # --- remover linhas sem NF válida ou sem data ---
    df = df[df['nf'].str.len() > 0]
    df = df[df['data'].notna()]
    df = df[df['valor'].notna()]

    return df[COLUNAS_PADRAO].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Detecção automática de fonte pelo nome do arquivo
# ---------------------------------------------------------------------------

def ler_arquivo(path: str | Path, fonte: str | None = None) -> tuple[pd.DataFrame, str]:
    """
    Detecta automaticamente a fonte pelo nome do arquivo e chama a função correta.

    Detecção automática:
      - 'ExtratoNotasPrestador' no nome → Fonte A
      - 'Atendimento' no nome           → Fonte B

    Parâmetros
    ----------
    path  : caminho do arquivo
    fonte : 'A' ou 'B' para forçar (opcional, sobrepõe detecção automática)

    Retorna
    -------
    (DataFrame, fonte_detectada)  onde fonte_detectada é 'A' ou 'B'
    """
    path = Path(path)
    nome = path.name

    if fonte is None:
        if 'Extrato' in nome or 'extrato' in nome or 'Prefeitura' in nome:
            fonte = 'A'
        elif 'Atendimento' in nome or 'atendimento' in nome:
            fonte = 'B'
        else:
            raise ValueError(
                f'Não foi possível detectar a fonte pelo nome "{nome}". '
                f'Passe fonte="A" ou fonte="B" explicitamente.'
            )

    if fonte == 'A':
        return ler_fonte_a_xls(path), 'A'
    elif fonte == 'B':
        return ler_fonte_b(path), 'B'
    else:
        raise ValueError(f'fonte deve ser "A" ou "B", recebido: {fonte!r}')


# ---------------------------------------------------------------------------
# CLI simples para teste rápido
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Uso: python reader.py <arquivo> [A|B]')
        sys.exit(1)

    arquivo = sys.argv[1]
    fonte_arg = sys.argv[2] if len(sys.argv) > 2 else None

    df, fonte_detectada = ler_arquivo(arquivo, fonte_arg)

    print(f'\n✅ Fonte {fonte_detectada} lida com sucesso: {len(df)} NFs\n')
    print(df.head(10).to_string(index=False))
    print(f'\nDtypes:\n{df.dtypes}')
    print(f'\nNulos:\n{df.isnull().sum()}')
