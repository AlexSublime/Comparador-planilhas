# 📋 PLANO — SISTEMA DE CONCILIAÇÃO DE NOTAS FISCAIS
> Versão 6 — atualizada em 22/04/2026
> Cole este arquivo inteiro no início de uma nova conversa.

---

## 🎯 Objetivo do Projeto

Desenvolver um sistema que **compara duas fontes de notas fiscais**, identifica divergências e gera relatórios de conciliação.

---

## 📥 Fontes de Dados

| Fonte | Origem | Formato atual | Formatos futuros |
|-------|--------|---------------|-----------------|
| **Fonte A** | Portal da Prefeitura (exportação) | **XLS** ✅ | TXT, PDF (fase futura) |
| **Fonte B** | Sistema de atendimento do usuário | **CSV/XLS** ✅ | — |

**Campo identificador principal:** Número da Nota Fiscal (NF)

> **Escopo atual:** apenas XLS (Fonte A) e CSV/XLS (Fonte B). Suporte a PDF da Prefeitura será adicionado em fase futura.

---

## ✅ Decisões Tomadas

### Objetivos da comparação (todos os 4 selecionados):
- Identificar notas que estão em um lado e não no outro
- Comparar valores/campos entre as duas fontes
- Detectar divergências (ex: valor diferente para a mesma NF)
- Gerar relatório de conciliação completo

### Campos a comparar:
- Número da NF
- Valor total
- Data de emissão
- CPF / CNPJ do Tomador (prioritariamente CPF, mas suporta CNPJ também)

### Volume esperado:
- Médio: **500 a 5.000 NFs** por comparação

### Formato do relatório de saída:
- **Excel (.xlsx)** — para análise
- **PDF** — para impressão/arquivo
- **Visualização na tela** (via Streamlit)

### Tecnologia escolhida:
- **Python** (usuário já tem instalado)
- **Interface:** Streamlit (roda no navegador, sem instalação adicional)

---

## 📦 Instalação das Dependências

> ⚠️ **Passo obrigatório antes de rodar qualquer módulo.**
> Execute este comando uma única vez no terminal, dentro da pasta do projeto:

```bash
pip install pandas openpyxl xlrd lxml streamlit reportlab
```

> **Por que o `lxml`?** O arquivo da Prefeitura (`ExtratoNotasPrestador_*.xls`) é na verdade um HTML disfarçado de XLS. O pandas usa o `lxml` internamente para conseguir lê-lo com `pd.read_html()`.

Verificação rápida após instalar:

```bash
python -c "import pandas, openpyxl, xlrd, lxml, streamlit, reportlab; print('OK')"
```

Se imprimir `OK`, está tudo pronto.

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────┐     ┌─────────────────────┐
│  FONTE A: Prefeitura │     │  FONTE B: Seu Sistema│
│  (XLS)              │     │  (CSV / XLS)         │
└────────┬────────────┘     └──────────┬───────────┘
         │                             │
         ▼                             ▼
┌─────────────────────────────────────────────────┐
│             MÓDULO DE LEITURA  ✅               │
│  reader.py                                      │
│  Normaliza todos os formatos → DataFrame padrão │
└─────────────────────────┬───────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────┐
│           MÓDULO DE NORMALIZAÇÃO  ✅            │
│  normalizer.py                                  │
│  Valida CPF/CNPJ, detecta anomalias             │
└─────────────────────────┬───────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────┐
│            ENGINE DE COMPARAÇÃO  ✅             │
│  comparator.py                                  │
│  ✅ NFs em ambos, sem divergência               │
│  ⚠️  NFs em ambos, COM divergência             │
│  🔴 NFs só na Prefeitura                        │
│  🔵 NFs só no Sistema                           │
└─────────────────────────┬───────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────┐
│           GERADOR DE RELATÓRIOS                 │
│  report_excel.py ✅  +  report_pdf.py (próximo) │
│  📊 Excel (.xlsx) com 5 abas                    │
│  📄 PDF formatado para impressão                │
└─────────────────────────────────────────────────┘
```

---

## 🗂️ Estrutura de Módulos

| Arquivo | Responsabilidade | Status |
|---------|-----------------|--------|
| `reader.py` | Lê XLS (Fonte A) e CSV/XLS (Fonte B) → DataFrame pandas | ✅ Concluído |
| `normalizer.py` | Valida CPF/CNPJ (dígito verificador), detecta anomalias | ✅ Concluído |
| `comparator.py` | Engine de comparação e categorização | ✅ Concluído |
| `report_excel.py` | Gera .xlsx com formatação e 5 abas | ✅ Concluído |
| `report_pdf.py` | Gera .pdf formatado para impressão | 🔜 Próximo |
| `app.py` | Interface Streamlit (frontend) | ⏳ Pendente |

---

## 🖥️ Interface Streamlit (esboço)

```
[ Upload Fonte A: Prefeitura ]   [ Upload Fonte B: Sistema ]
       XLS                              CSV / XLS

[ Mapeamento de colunas ]  ← usuário indica qual coluna é NF, valor, data, CPF/CNPJ

[ ▶ RODAR CONCILIAÇÃO ]

┌─────────────────── RESULTADO NA TELA ──────────────────┐
│  Total Prefeitura: 1.200   Total Sistema: 1.185        │
│  ✅ Conciliadas:  1.150    ⚠️  Divergentes: 25        │
│  🔴 Só Prefeitura: 10     🔵 Só Sistema: 35            │
└────────────────────────────────────────────────────────┘

[ ⬇ Baixar Excel ]   [ ⬇ Baixar PDF ]
```

---

## 📊 Estrutura do Relatório Excel (5 abas)

| Aba | Cor | Conteúdo |
|-----|-----|----------|
| **Resumo** | Cinza escuro | KPIs visuais + tabela de valores e percentuais |
| **Conciliadas** | Verde | NFs que batem perfeitamente em todos os campos |
| **Divergentes** | Amarelo/Vermelho | Side-by-side dos campos com destaque por criticidade |
| **Só Prefeitura** | Vermelho | NFs que existem na prefeitura mas não estão no sistema |
| **Só Sistema** | Azul | NFs que estão no sistema mas não aparecem na prefeitura |

---

## 📂 Estrutura Real dos Arquivos

---

### Fonte A — Prefeitura (arquivo: `ExtratoNotasPrestador_*.xls`)

**Formato real:** HTML disfarçado de XLS (padrão do portal NFS-e de Peruíbe)
**Leitura correta:** `pd.read_html(path, encoding='utf-8', header=[0,1])` — tabela de índice 2
**Atenção especial:** A primeira linha de dados fica embutida no cabeçalho multi-index e precisa ser reconstruída manualmente.

```python
tables = pd.read_html(path, encoding='utf-8', header=[0,1])
df = tables[2]
first_row = {c[0]: c[1] for c in df.columns}
df.columns = [c[0] for c in df.columns]
df = pd.concat([pd.DataFrame([first_row]), df], ignore_index=True)
```

**Colunas usadas na conciliação:**

| Coluna | Exemplo | Observação |
|--------|---------|------------|
| `NOTA` | `2930` | Inteiro nas linhas normais; primeira linha pode vir como string com zeros — normalizar com `lstrip('0')` |
| `VL. NOTA` | `350,00` / `30000` | String com vírgula OU inteiro — normalizar para float |
| `DT. INCLUSÃO` | `10/04/2026 11:23:47` | String datetime — converter para date |
| `CNPJ/CPF` | `104.153.588-09` | CPF ou CNPJ — remover pontuação |
| `TOMADOR` | `VANIA DOS SANTOS SILVA PIRES` | Nome em maiúsculas |

**Totais do arquivo de exemplo:** 199 NFs — R$ 303.093,96 — ISS R$ 6.061,87

**Resultado da normalização no arquivo de exemplo:**
- 186 CPF (185 válidos, 1 com dígito verificador inválido — NF 2834 "PESSOA FÍSICA - DOCUMENTO NÃO INFORMADO")
- 13 CNPJ (todos válidos)
- 0 valores zero/negativos

---

### Fonte B — Sistema de Atendimento (arquivo: `Atendimento_x_Financeiro_*.csv`)

**Formato real:** CSV separado por ponto e vírgula (`;`)
**Encoding:** `latin-1`
**⚠️ Bug conhecido:** o CSV tem 41 colunas nos dados e 40 no header — pandas interpreta a coluna `Protocolo` como índice por padrão, deslocando todo o mapeamento. **Solução:** `index_col=False` na leitura.

```python
df = pd.read_csv(path, sep=';', encoding='latin-1', dtype=str, index_col=False)
```

**Por que uma NF aparece múltiplas vezes?**
Cada linha representa uma parcela de pagamento (cartão de crédito). Deduplicar por `N. Fiscal`, mantendo a primeira ocorrência.

**Colunas relevantes:**

| Coluna CSV | Papel |
|------------|-------|
| `N. Fiscal` | Chave de comparação |
| `NF Bruto` | Valor a comparar |
| `D. Emissão` | Data a comparar |
| `CPF Paciente` | CPF a comparar |
| `Paciente` | Nome (informativo) |

**Resultado da normalização no arquivo de exemplo:**
- 228 NFs após deduplicação
- 228 CPF, todos válidos
- 0 anomalias

---

### Mapeamento final entre as duas fontes

| Campo comparado | Fonte A (Prefeitura XLS) | Fonte B (Sistema CSV/XLS) | Tipo normalizado |
|-----------------|--------------------------|---------------------------|-----------------|
| Número da NF | `NOTA` | `N. Fiscal` | `str` |
| Valor total | `VL. NOTA` | `NF Bruto` | `float` (2 casas) |
| Data de emissão | `DT. INCLUSÃO` | `D. Emissão` | `date` |
| CPF / CNPJ | `CNPJ/CPF` | `CPF Paciente` | `str` (só números) |

---

### Schema padrão (saída do reader, entrada do normalizer)

```
nf          str   — número da NF (sem zeros à esquerda)
valor       float — valor total da NF (2 casas decimais)
data        date  — data de emissão
cpf_cnpj    str   — CPF (11 dígitos) ou CNPJ (14 dígitos), só números
tomador     str   — nome do tomador (informativo)
```

### Schema pós-normalização (saída do normalizer, entrada do comparator)

```
nf          str
valor       float
data        date
cpf_cnpj    str
tomador     str
tipo_doc    str   — 'CPF' | 'CNPJ' | 'ESTRANGEIRO' | 'AUSENTE' | 'INVALIDO'
doc_valido  bool  — True se passou no dígito verificador
anomalia    str   — descrição de anomalia, ou '' se ok
```

### Schema pós-comparação (saída do comparator — NFs em ambas as fontes)

```
nf                str
valor_a / valor_b float
data_a  / data_b  date
cpf_cnpj_a/b      str
tomador_a / b     str
status_valor      str    — 'OK' | 'CRITICO'
diff_valor        float  — diferença absoluta em R$
status_data       str    — 'OK' | 'LEVE' | 'CRITICO'
diff_dias         int    — diferença em dias (None se data ausente)
status_doc        str    — 'OK' | 'LEVE' | 'CRITICO'
classificacao     str    — 'CONCILIADA' | 'DIVERGENCIA_LEVE' | 'DIVERGENCIA_CRITICA'
```

---

## 🔮 Fonte A — PDF (fase futura)

> Documentado para implementação futura. **Fora do escopo atual.**

**Arquivo:** `LivroFiscal_MM_AAAA.pdf` — Livro Fiscal mensal da Prefeitura de Peruíbe
**Tipo:** PDF com texto selecionável (não requer OCR)
**Dependência adicional:** `pdfplumber`

**Cabeçalho completo:**
`Dia | Série | NF Ini. | NF Fim | Serv. | %Alíq. | Situação | Tipo | Nome | (R$)Faturado | (R$)Base Cálc. | (R$)Imposto | Local.Prest`

**Mapeamento para conciliação:**

| Campo | Coluna PDF | Observação |
|-------|------------|------------|
| Número da NF | `NF Ini.` | `NF Ini. == NF Fim` em todos os casos observados |
| Valor | `(R$)Faturado` | Equivalente ao `VL. NOTA` do XLS |
| Data | `Dia` | Apenas o dia — mês e ano inferidos do nome do arquivo |
| CPF/CNPJ | Parte direita da coluna `Nome` | Formato: `NOME - 000.000.000-00` → `split(' - ')[-1]` |

---

## ⚖️ Regras de Divergência ✅ VALIDADAS

### Campo: Valor

| Regra | Critério | Classificação |
|-------|----------|---------------|
| **R-V1** | `abs(valor_A - valor_B) <= 0.01` | ✅ Conciliado |
| **R-V2** | `abs(valor_A - valor_B) > 0.01` | 🔴 Divergência crítica |

### Campo: Data de Emissão

| Regra | Critério | Classificação |
|-------|----------|---------------|
| **R-D1** | Datas idênticas | ✅ Conciliado |
| **R-D2** | Diferença de 1 a 7 dias | ⚠️ Divergência leve |
| **R-D3** | Diferença > 7 dias | 🔴 Divergência crítica |

### Campo: CPF / CNPJ

| Regra | Critério | Classificação |
|-------|----------|---------------|
| **R-C1** | CPF/CNPJ idênticos | ✅ Conciliado |
| **R-C2** | Ambos preenchidos e diferentes | 🔴 Divergência crítica |
| **R-C3** | Um dos lados vazio ou formato não-padrão | ⚠️ Divergência leve |

### Classificação geral da NF

| Resultado | Critério |
|-----------|----------|
| ✅ **Conciliada** | Todos os campos `OK` |
| ⚠️ **Divergência leve** | Pelo menos 1 campo `LEVE`, nenhum `CRITICO` |
| 🔴 **Divergência crítica** | Pelo menos 1 campo `CRITICO` |

---

## 🔄 Próximos Passos

1. ~~Validar regras de divergência~~ ✅
2. ~~Esclarecer tipo do PDF~~ ✅ (fase futura documentada)
3. ~~Desenvolver `reader.py`~~ ✅ (testado com arquivos reais)
4. ~~Desenvolver `normalizer.py`~~ ✅ (testado com arquivos reais)
5. ~~Desenvolver `comparator.py`~~ ✅
6. ~~Desenvolver `report_excel.py`~~ ✅
7. **Desenvolver `report_pdf.py`** ← estamos aqui
8. Montar `app.py` com interface Streamlit
9. Testes com arquivos reais
10. *(fase futura)* Adicionar suporte a PDF da Prefeitura

---

## 💬 Instrução para o próximo chat

Cole esta documentação no início de uma nova conversa com o seguinte prompt:

> "Olá Claude. Estou desenvolvendo um sistema de conciliação de notas fiscais em Python. Segue a documentação completa do planejamento já feito. Quero continuar o desenvolvimento a partir dos próximos passos. [COLE ESTE DOCUMENTO AQUI]"

---
*Documento atualizado em: 22/04/2026*
