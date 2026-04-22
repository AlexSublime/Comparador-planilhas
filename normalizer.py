"""
normalizer.py — Validação e normalização dos DataFrames pós-leitura
====================================================================
Recebe os DataFrames no schema padrão (saída do reader.py) e aplica:

  1. Validação de CPF (dígito verificador)
  2. Validação de CNPJ (dígito verificador)
  3. Classificação do documento: CPF / CNPJ / ESTRANGEIRO / AUSENTE / INVALIDO
  4. Sinalização de NFs com valor zero ou negativo
  5. Remoção de duplicatas de NF dentro da mesma fonte (mantém primeira ocorrência)
  6. Relatório de anomalias encontradas

Schema de entrada (saída do reader.py):
    nf          str
    valor       float
    data        date
    cpf_cnpj    str
    tomador     str

Schema de saída (acrescenta colunas):
    nf          str
    valor       float
    data        date
    cpf_cnpj    str
    tomador     str
    tipo_doc    str   — 'CPF' | 'CNPJ' | 'ESTRANGEIRO' | 'AUSENTE' | 'INVALIDO'
    doc_valido  bool  — True se CPF/CNPJ passou no dígito verificador
    anomalia    str   — descrição de anomalia, ou '' se ok
"""

import pandas as pd
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Validação de CPF
# ---------------------------------------------------------------------------

def _validar_cpf(cpf: str) -> bool:
    """
    Valida CPF pelo dígito verificador.
    Entrada: string com 11 dígitos numéricos.
    """
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    if len(set(cpf)) == 1:          # ex: 00000000000, 11111111111
        return False

    def digito(cpf, n):
        s = sum(int(cpf[i]) * (n - i) for i in range(n - 1))
        r = (s * 10) % 11
        return 0 if r == 10 else r

    return digito(cpf, 10) == int(cpf[9]) and digito(cpf, 11) == int(cpf[10])


# ---------------------------------------------------------------------------
# Validação de CNPJ
# ---------------------------------------------------------------------------

def _validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ pelo dígito verificador.
    Entrada: string com 14 dígitos numéricos.
    """
    if len(cnpj) != 14 or not cnpj.isdigit():
        return False
    if len(set(cnpj)) == 1:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def digito(cnpj, pesos):
        s = sum(int(cnpj[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r

    return (digito(cnpj, pesos1) == int(cnpj[12]) and
            digito(cnpj, pesos2) == int(cnpj[13]))


# ---------------------------------------------------------------------------
# Classificação do documento
# ---------------------------------------------------------------------------

def _classificar_doc(cpf_cnpj: str) -> tuple[str, bool]:
    """
    Classifica e valida o documento.

    Retorna
    -------
    (tipo_doc, doc_valido)
        tipo_doc  : 'CPF' | 'CNPJ' | 'ESTRANGEIRO' | 'AUSENTE' | 'INVALIDO'
        doc_valido: True se passou no dígito verificador
    """
    v = str(cpf_cnpj).strip()

    if not v or v in ('', 'nan', 'None'):
        return 'AUSENTE', False

    digitos = ''.join(c for c in v if c.isdigit())

    if len(digitos) == 11:
        valido = _validar_cpf(digitos)
        return 'CPF', valido

    if len(digitos) == 14:
        valido = _validar_cnpj(digitos)
        return 'CNPJ', valido

    # Comprimento diferente de 11 ou 14 → documento estrangeiro ou formato incomum
    if len(digitos) > 0:
        return 'ESTRANGEIRO', False

    return 'INVALIDO', False


# ---------------------------------------------------------------------------
# Resultado do normalize
# ---------------------------------------------------------------------------

class ResultadoNormalizacao(NamedTuple):
    df:        pd.DataFrame   # DataFrame normalizado com colunas extras
    anomalias: pd.DataFrame   # Subconjunto das linhas com anomalia != ''


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def normalizar(df: pd.DataFrame, nome_fonte: str = '') -> ResultadoNormalizacao:
    """
    Aplica validações e normalização ao DataFrame retornado pelo reader.

    Parâmetros
    ----------
    df          : DataFrame no schema padrão (saída de reader.py)
    nome_fonte  : 'A' ou 'B' — usado nas mensagens de anomalia

    Retorna
    -------
    ResultadoNormalizacao(df_normalizado, df_anomalias)
    """
    df = df.copy()

    # --- validar schema de entrada ---
    colunas_esperadas = {'nf', 'valor', 'data', 'cpf_cnpj', 'tomador'}
    faltando = colunas_esperadas - set(df.columns)
    if faltando:
        raise ValueError(f'normalizar(): colunas ausentes no DataFrame: {faltando}')

    # --- classificação e validação de CPF/CNPJ ---
    resultado_doc = df['cpf_cnpj'].apply(_classificar_doc)
    df['tipo_doc']   = resultado_doc.apply(lambda x: x[0])
    df['doc_valido'] = resultado_doc.apply(lambda x: x[1])

    # --- duplicatas de NF dentro da mesma fonte ---
    duplicatas_mask = df.duplicated(subset=['nf'], keep='first')

    # --- anomalias ---
    def _anomalia(row, eh_duplicata: bool) -> str:
        partes = []

        if eh_duplicata:
            partes.append('NF duplicada na fonte (removida)')

        if row['tipo_doc'] == 'AUSENTE':
            partes.append('CPF/CNPJ ausente')
        elif row['tipo_doc'] == 'ESTRANGEIRO':
            partes.append('documento estrangeiro ou formato não-padrão')
        elif row['tipo_doc'] == 'INVALIDO':
            partes.append('documento inválido (não numérico)')
        elif not row['doc_valido']:
            partes.append(f'{row["tipo_doc"]} com dígito verificador inválido')

        if pd.notna(row['valor']) and row['valor'] <= 0:
            partes.append(f'valor inválido ({row["valor"]})')

        return '; '.join(partes)

    df['anomalia'] = [
        _anomalia(row, duplicatas_mask.iloc[i])
        for i, (_, row) in enumerate(df.iterrows())
    ]

    # --- remover duplicatas (mantém primeira ocorrência) ---
    df = df[~duplicatas_mask].reset_index(drop=True)

    # --- DataFrame de anomalias (apenas linhas com problema) ---
    df_anomalias = df[df['anomalia'] != ''][
        ['nf', 'valor', 'data', 'cpf_cnpj', 'tipo_doc', 'doc_valido', 'tomador', 'anomalia']
    ].copy()

    return ResultadoNormalizacao(df=df, anomalias=df_anomalias)


# ---------------------------------------------------------------------------
# Relatório resumido no terminal
# ---------------------------------------------------------------------------

def imprimir_resumo(resultado: ResultadoNormalizacao, nome_fonte: str = '') -> None:
    """Imprime um resumo da normalização no terminal."""
    df = resultado.df
    label = f'Fonte {nome_fonte}' if nome_fonte else 'DataFrame'

    print(f'\n{"="*55}')
    print(f'  Resumo normalização — {label}')
    print(f'{"="*55}')
    print(f'  Total NFs          : {len(df)}')
    print(f'  Tipo de documento  :')
    for tipo, count in df['tipo_doc'].value_counts().items():
        validos = df[df['tipo_doc'] == tipo]['doc_valido'].sum()
        print(f'    {tipo:<12} {count:>4}  ({validos} válidos)')
    print(f'  Valor zero/negativo: {(df["valor"] <= 0).sum()}')
    print(f'  Com anomalia       : {(df["anomalia"] != "").sum()}')

    if len(resultado.anomalias) > 0:
        print(f'\n  Anomalias:')
        for _, row in resultado.anomalias.iterrows():
            print(f'    NF {row["nf"]:>6}  {row["tomador"][:30]:<30}  {row["anomalia"]}')
    print()


# ---------------------------------------------------------------------------
# CLI para teste rápido
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    from reader import ler_arquivo

    if len(sys.argv) < 2:
        print('Uso: python normalizer.py <arquivo> [A|B]')
        sys.exit(1)

    arquivo  = sys.argv[1]
    fonte    = sys.argv[2] if len(sys.argv) > 2 else None

    df_raw, fonte_detectada = ler_arquivo(arquivo, fonte)
    resultado = normalizar(df_raw, nome_fonte=fonte_detectada)
    imprimir_resumo(resultado, nome_fonte=fonte_detectada)

    print(resultado.df.head(10).to_string(index=False))
