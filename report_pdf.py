"""
report_pdf.py — Gerador de relatório PDF da conciliação
=======================================================
Gera um arquivo .pdf formatado para impressão com:

  - Capa com resumo executivo e KPIs
  - Seção de divergentes (detalhamento crítico)
  - Seção de NFs só na Prefeitura
  - Seção de NFs só no Sistema
  - Rodapé com número de página e data de geração

Dependências: reportlab
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

from comparator import ResultadoComparacao


# ---------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------

VERDE       = colors.HexColor('#1A6B3C')
VERDE_CLARO = colors.HexColor('#D6F0E0')
VERMELHO    = colors.HexColor('#C0392B')
VERM_CLARO  = colors.HexColor('#FADBD8')
AMARELO     = colors.HexColor('#F39C12')
AMAR_CLARO  = colors.HexColor('#FEF9E7')
AZUL        = colors.HexColor('#1A5276')
AZUL_CLARO  = colors.HexColor('#D6EAF8')
CINZA_ESC   = colors.HexColor('#2C3E50')
CINZA_MED   = colors.HexColor('#7F8C8D')
CINZA_CLARO = colors.HexColor('#F2F3F4')
BRANCO      = colors.white
PRETO       = colors.black


# ---------------------------------------------------------------------------
# Estilos de parágrafo
# ---------------------------------------------------------------------------

def _estilos():
    base = getSampleStyleSheet()

    titulo = ParagraphStyle(
        'Titulo',
        parent=base['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=BRANCO,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    subtitulo = ParagraphStyle(
        'Subtitulo',
        parent=base['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#AAAAAA'),
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    secao = ParagraphStyle(
        'Secao',
        parent=base['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=BRANCO,
        alignment=TA_LEFT,
        spaceAfter=6,
        spaceBefore=12,
    )
    label_kpi = ParagraphStyle(
        'LabelKPI',
        parent=base['Normal'],
        fontName='Helvetica',
        fontSize=8,
        textColor=CINZA_MED,
        alignment=TA_CENTER,
    )
    valor_kpi = ParagraphStyle(
        'ValorKPI',
        parent=base['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=CINZA_ESC,
        alignment=TA_CENTER,
    )
    nota = ParagraphStyle(
        'Nota',
        parent=base['Normal'],
        fontName='Helvetica',
        fontSize=8,
        textColor=CINZA_MED,
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    normal = ParagraphStyle(
        'NormalPDF',
        parent=base['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=PRETO,
    )
    return {
        'titulo': titulo, 'subtitulo': subtitulo, 'secao': secao,
        'label_kpi': label_kpi, 'valor_kpi': valor_kpi,
        'nota': nota, 'normal': normal,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _moeda(v: float) -> str:
    return f'R$ {v:,.2f}'

def _pct(v: float) -> str:
    return f'{v:.1f}%'

def _linha_alt(n: int, cor_par, cor_impar=BRANCO):
    return cor_par if n % 2 == 0 else cor_impar

def _estilo_tabela_base(cor_header):
    return TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  cor_header),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  BRANCO),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  8),
        ('ALIGN',       (0, 0), (-1, 0),  'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING',  (0, 0), (-1, 0),  6),
        ('FONTNAME',    (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 1), (-1, -1), 8),
        ('ALIGN',       (0, 1), (-1, -1), 'LEFT'),
        ('TOPPADDING',  (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
    ])


# ---------------------------------------------------------------------------
# Rodapé e cabeçalho de página
# ---------------------------------------------------------------------------

def _rodape(canvas, doc):
    gerado_em = doc.gerado_em
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(CINZA_MED)
    canvas.drawString(2 * cm, 1.2 * cm, f'Gerado em: {gerado_em}')
    canvas.drawRightString(
        A4[0] - 2 * cm, 1.2 * cm,
        f'Página {doc.page}'
    )
    canvas.setStrokeColor(CINZA_MED)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Capa / Resumo
# ---------------------------------------------------------------------------

def _bloco_capa(r: dict, estilos: dict) -> list:
    story = []

    # banner de título
    banner = Table(
        [[Paragraph('CONCILIACAO DE NOTAS FISCAIS', estilos['titulo'])],
         [Paragraph(f'Gerado em: {estilos["_gerado_em"]}', estilos['subtitulo'])]],
        colWidths=[17 * cm],
        style=TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), CINZA_ESC),
            ('TOPPADDING',    (0, 0), (-1, -1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
            ('LEFTPADDING',   (0, 0), (-1, -1), 16),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 16),
        ]),
    )
    story.append(banner)
    story.append(Spacer(1, 0.6 * cm))

    # KPIs — linha 1
    def _kpi_cell(label, valor, cor=CINZA_ESC):
        return [
            Paragraph(label, estilos['label_kpi']),
            Paragraph(str(valor), ParagraphStyle(
                '_kv', parent=estilos['valor_kpi'], textColor=cor)),
        ]

    kpi1 = Table(
        [
            [
                Table([_kpi_cell('TOTAL PREFEITURA (A)', r['total_fonte_a'], AZUL)],
                      style=TableStyle([('BACKGROUND', (0,0),(-1,-1), AZUL_CLARO),
                                        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)])),
                Table([_kpi_cell('TOTAL SISTEMA (B)', r['total_fonte_b'], AZUL)],
                      style=TableStyle([('BACKGROUND', (0,0),(-1,-1), AZUL_CLARO),
                                        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)])),
                Table([_kpi_cell('CONCILIADAS', r['total_conciliadas'], VERDE)],
                      style=TableStyle([('BACKGROUND', (0,0),(-1,-1), VERDE_CLARO),
                                        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)])),
            ]
        ],
        colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm],
        style=TableStyle([('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]),
    )
    story.append(kpi1)
    story.append(Spacer(1, 0.3 * cm))

    kpi2 = Table(
        [
            [
                Table([_kpi_cell('DIVERGENTES', r['total_divergentes'], AMARELO)],
                      style=TableStyle([('BACKGROUND', (0,0),(-1,-1), AMAR_CLARO),
                                        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)])),
                Table([_kpi_cell('SO PREFEITURA', r['total_so_prefeitura'], VERMELHO)],
                      style=TableStyle([('BACKGROUND', (0,0),(-1,-1), VERM_CLARO),
                                        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)])),
                Table([_kpi_cell('SO SISTEMA', r['total_so_sistema'], AZUL)],
                      style=TableStyle([('BACKGROUND', (0,0),(-1,-1), AZUL_CLARO),
                                        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)])),
            ]
        ],
        colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm],
        style=TableStyle([('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]),
    )
    story.append(kpi2)
    story.append(Spacer(1, 0.6 * cm))

    # tabela de valores
    header_val = ['Categoria', 'Qtd. NFs', 'Valor Total', 'Percentual']
    linhas_val = [
        header_val,
        ['Total Prefeitura (A)', str(r['total_fonte_a']),  _moeda(r['valor_total_a']),  '-'],
        ['Total Sistema (B)',    str(r['total_fonte_b']),  _moeda(r['valor_total_b']),  '-'],
        ['Conciliadas',         str(r['total_conciliadas']), _moeda(r['valor_conciliadas_a']), _pct(r['pct_conciliadas'])],
        ['Divergentes',         str(r['total_divergentes']),_moeda(r['valor_divergentes_a']), _pct(r['pct_divergentes'])],
        ['So Prefeitura',       str(r['total_so_prefeitura']), _moeda(r['valor_so_prefeitura']), '-'],
        ['So Sistema',          str(r['total_so_sistema']),    _moeda(r['valor_so_sistema']),    '-'],
    ]

    tab_vals = Table(
        linhas_val,
        colWidths=[6 * cm, 3 * cm, 5 * cm, 3 * cm],
        style=_estilo_tabela_base(CINZA_ESC),
    )
    # highlight por linha
    tab_vals.setStyle(TableStyle([
        ('BACKGROUND', (0, 3), (-1, 3), VERDE_CLARO),
        ('BACKGROUND', (0, 4), (-1, 4), AMAR_CLARO),
        ('BACKGROUND', (0, 5), (-1, 5), VERM_CLARO),
        ('BACKGROUND', (0, 6), (-1, 6), AZUL_CLARO),
    ]))
    story.append(tab_vals)

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f'Divergencias criticas: {r["total_divergencias_criticas"]}   |   '
        f'Divergencias leves: {r["total_divergencias_leves"]}',
        estilos['nota'],
    ))

    return story


# ---------------------------------------------------------------------------
# Seção de divergentes
# ---------------------------------------------------------------------------

def _bloco_divergentes(df: pd.DataFrame, estilos: dict) -> list:
    story = []

    banner = Table(
        [[Paragraph('DIVERGENTES — Detalhamento', estilos['secao'])]],
        colWidths=[17 * cm],
        style=TableStyle([
            ('BACKGROUND', (0,0),(-1,-1), AMARELO),
            ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('LEFTPADDING',(0,0),(-1,-1),10),
        ]),
    )
    story.append(banner)
    story.append(Spacer(1, 0.3 * cm))

    if df.empty:
        story.append(Paragraph('Nenhuma NF divergente encontrada.', estilos['normal']))
        return story

    header = ['NF', 'Classificacao', 'Valor A', 'Valor B', 'Delta R$', 'St.Valor', 'Delta Dias', 'St.Data', 'St.Doc']
    dados = [header]

    for _, row in df.iterrows():
        dados.append([
            row['nf'],
            row['classificacao'].replace('DIVERGENCIA_', ''),
            _moeda(row['valor_a']),
            _moeda(row['valor_b']),
            _moeda(row['diff_valor']),
            row['status_valor'],
            str(row['diff_dias']) if row['diff_dias'] is not None else '-',
            row['status_data'],
            row['status_doc'],
        ])

    tab = Table(
        dados,
        colWidths=[1.5*cm, 3.5*cm, 2.5*cm, 2.5*cm, 2*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.6*cm],
        repeatRows=1,
        style=_estilo_tabela_base(CINZA_ESC),
    )

    # colorir linhas por criticidade
    cmds = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        cor = VERM_CLARO if 'CRITICA' in row['classificacao'] else AMAR_CLARO
        cmds.append(('BACKGROUND', (0, i), (-1, i), cor))
    tab.setStyle(TableStyle(cmds))

    story.append(tab)
    return story


# ---------------------------------------------------------------------------
# Seção genérica: só A ou só B
# ---------------------------------------------------------------------------

def _bloco_exclusivos(df: pd.DataFrame, titulo: str, cor_banner, cor_linha,
                      estilos: dict) -> list:
    story = []

    banner = Table(
        [[Paragraph(titulo, estilos['secao'])]],
        colWidths=[17 * cm],
        style=TableStyle([
            ('BACKGROUND', (0,0),(-1,-1), cor_banner),
            ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('LEFTPADDING',(0,0),(-1,-1),10),
        ]),
    )
    story.append(banner)
    story.append(Spacer(1, 0.3 * cm))

    if df.empty:
        story.append(Paragraph('Nenhuma NF encontrada nesta categoria.', estilos['normal']))
        return story

    header = ['NF', 'Valor', 'Data', 'CPF/CNPJ', 'Tomador']
    dados = [header]

    for _, row in df.iterrows():
        dados.append([
            row['nf'],
            _moeda(row['valor']),
            str(row['data']),
            row['cpf_cnpj'],
            row['tomador'][:40],
        ])

    tab = Table(
        dados,
        colWidths=[2*cm, 3*cm, 2.5*cm, 3.5*cm, 6*cm],
        repeatRows=1,
        style=_estilo_tabela_base(cor_banner),
    )
    tab.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cor_linha, BRANCO]),
    ]))

    story.append(tab)
    return story


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_pdf(
    resultado: ResultadoComparacao,
    caminho_saida: str | Path | None = None,
) -> Path:
    """
    Gera o relatório PDF da conciliação.

    Parâmetros
    ----------
    resultado     : ResultadoComparacao (saída de comparator.comparar())
    caminho_saida : caminho do arquivo de saída (opcional).
                    Padrão: 'conciliacao_YYYYMMDD_HHMMSS.pdf' na pasta atual.

    Retorna
    -------
    Path do arquivo gerado.
    """
    gerado_em = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if caminho_saida is None:
        caminho_saida = Path(f'conciliacao_{timestamp}.pdf')
    caminho_saida = Path(caminho_saida)

    estilos = _estilos()
    estilos['_gerado_em'] = gerado_em

    doc = SimpleDocTemplate(
        str(caminho_saida),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.5 * cm,
        title='Conciliacao de Notas Fiscais',
    )
    doc.gerado_em = gerado_em

    story = []

    # --- capa / resumo ---
    story += _bloco_capa(resultado.resumo, estilos)

    # --- divergentes ---
    if not resultado.df_divergentes.empty:
        story.append(PageBreak())
        story += _bloco_divergentes(resultado.df_divergentes, estilos)

    # --- só prefeitura ---
    if not resultado.df_so_prefeitura.empty:
        story.append(PageBreak())
        story += _bloco_exclusivos(
            resultado.df_so_prefeitura,
            'SO NA PREFEITURA',
            VERMELHO, VERM_CLARO, estilos,
        )

    # --- só sistema ---
    if not resultado.df_so_sistema.empty:
        story.append(PageBreak())
        story += _bloco_exclusivos(
            resultado.df_so_sistema,
            'SO NO SISTEMA',
            AZUL, AZUL_CLARO, estilos,
        )

    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return caminho_saida


# ---------------------------------------------------------------------------
# CLI para teste rápido
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    from reader import ler_arquivo
    from normalizer import normalizar
    from comparator import comparar

    if len(sys.argv) < 3:
        print('Uso: python report_pdf.py <arquivo_A> <arquivo_B> [saida.pdf]')
        sys.exit(1)

    df_a, _ = ler_arquivo(sys.argv[1], 'A')
    df_b, _ = ler_arquivo(sys.argv[2], 'B')

    res_a = normalizar(df_a, 'A')
    res_b = normalizar(df_b, 'B')

    resultado = comparar(res_a.df, res_b.df)

    saida = sys.argv[3] if len(sys.argv) > 3 else None
    arquivo = gerar_pdf(resultado, saida)
    print(f'\n OK Relatorio PDF gerado: {arquivo}')
