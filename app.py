"""
Microserviço Flask para extração de dados de PDFs de multas
Deploy: Render.com, Railway.app, ou qualquer servidor Python

Requisitos (requirements.txt):
flask==3.0.0
pdfplumber==0.10.3
gunicorn==21.2.0
"""

from flask import Flask, request, jsonify
import pdfplumber
import re
import io
import os

app = Flask(__name__)


def extrair_dados_completos(pdf_path_or_bytes):
    """
    Extrai dados estruturados usando pdfplumber
    Aceita caminho de arquivo ou bytes
    """

    # Abre o PDF
    if isinstance(pdf_path_or_bytes, bytes):
        pdf_file = io.BytesIO(pdf_path_or_bytes)
        pdf = pdfplumber.open(pdf_file)
    else:
        pdf = pdfplumber.open(pdf_path_or_bytes)

    # Lê apenas a primeira página (onde estão as informações)
    primeira_pagina = pdf.pages[0]
    texto = primeira_pagina.extract_text()

    # Também extrai tabelas se houver
    tabelas = primeira_pagina.extract_tables()

    dados = {}

    # Extração usando regex otimizado

    # 1. Número do Auto
    auto_patterns = [
        r'Empresa\s*[\n\r]\s*([A-Z0-9]+)',
        r'Nº Auto:\s*([A-Z0-9]+)',
        r'Identificação do Auto de Infração\s*[\n\r]\s*([A-Z0-9]+)'
    ]
    for pattern in auto_patterns:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            dados['numero_auto'] = match.group(1).strip()
            break

    # 2. Empresa
    empresa_match = re.search(r'Código\s*/\s*Nome\s+da\s+Empresa\s*[\n\r]\s*(.+?)[\n\r]\s*SPE', texto, re.IGNORECASE)
    if empresa_match:
        dados['empresa'] = empresa_match.group(1).strip()

    # 3. SPE
    spe_match = re.search(r'SPE\s*[\n\r]?\s*(\d+)', texto)
    if spe_match:
        dados['spe'] = f"SPE{spe_match.group(1)}"

    # 4. Data da Infração
    data_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
    if data_match:
        dados['data_infracao'] = data_match.group(1)

    # 5. Hora da Infração
    hora_match = re.search(r'(\d{2}:\d{2})[\n\r]\s*SPE', texto)
    if hora_match:
        dados['hora_infracao'] = hora_match.group(1)

    # 6. Veículo (Prefixo)
    veiculo_match = re.search(r'Veículo[\n\r]\s*(\d+)', texto, re.IGNORECASE)
    if veiculo_match:
        dados['veiculo_prefixo'] = veiculo_match.group(1).strip()

    # 7. UF
    uf_match = re.search(r'UF[\n\r]\s*([A-Z]{2})', texto)
    if uf_match:
        dados['uf'] = uf_match.group(1)

    # 8. Linha
    linha_match = re.search(r'Linha[\n\r]\s*(\d+)', texto, re.IGNORECASE)
    if linha_match:
        dados['linha'] = linha_match.group(1)

    # 9. Descrição da Linha
    linha_desc_patterns = [
        r'Linha[\n\r]\s*\d+[\n\r]\s*(.+?)[\n\r]',
        r'BA\s+\d+[\n\r]\s*(.+?)[\n\r]'
    ]
    for pattern in linha_desc_patterns:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            dados['linha_descricao'] = match.group(1).strip()
            break

    # 10. Valor
    valor_match = re.search(r'(\d{1,}\.\d{3},\d{2})', texto)
    if valor_match:
        valor_str = valor_match.group(1).replace('.', '').replace(',', '.')
        dados['valor_multa'] = float(valor_str)
        dados['valor_multa_formatado'] = f"R$ {valor_match.group(1)}"

    # 11. Vencimento
    vencimento_match = re.search(r'Vencimento[\n\r]\s*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
    if vencimento_match:
        dados['data_vencimento'] = vencimento_match.group(1)

    # 12. Número do DAM
    dam_match = re.search(r'(\d{5}/\d{4}-\d)', texto)
    if dam_match:
        dados['numero_dam'] = dam_match.group(1)

    # 13. Artigo
    artigo_match = re.search(r'(\d+)\s+([\d.]+)\s+([IVX]+)', texto)
    if artigo_match:
        dados['artigo'] = artigo_match.group(2)
        dados['artigo_item'] = artigo_match.group(3)

    # 14. Grupo
    grupo_match = re.search(r'Grupo[\n\r]\s*([A-Z](?:-\d+)?)', texto, re.IGNORECASE)
    if grupo_match:
        dados['grupo'] = grupo_match.group(1)

    # 15. Descrição da Infração
    infracao_match = re.search(r'Deixar de cumprir os horários estabelecidos na OSO', texto, re.IGNORECASE)
    if infracao_match:
        dados['descricao_infracao'] = "Deixar de cumprir os horários estabelecidos na OSO."

    # 16. Logradouro
    logradouro_match = re.search(r'Logradouro[\n\r]\s*(.+)', texto, re.IGNORECASE)
    if logradouro_match:
        dados['logradouro'] = logradouro_match.group(1).strip()

    # 17. Bairro
    bairro_match = re.search(r'Bairro[\n\r]\s*(.+)', texto, re.IGNORECASE)
    if bairro_match:
        dados['bairro'] = bairro_match.group(1).strip()

    # 18. Observação
    obs_match = re.search(r'Observação:\s*[\n\r](.+?)(?:[\n\r]\d{4}|ILUSTRÍSSIMO)', texto, re.IGNORECASE | re.DOTALL)
    if obs_match:
        dados['observacao'] = obs_match.group(1).strip()

    # 19. Data de Emissão
    emissao_match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', texto)
    if emissao_match:
        dados['data_emissao'] = emissao_match.group(1)

    # 20. Matrícula do Agente
    matricula_match = re.search(r'Matrícula\s+Agente[\n\r]\s*(\d+)', texto, re.IGNORECASE)
    if matricula_match:
        dados['matricula_agente'] = matricula_match.group(1)

    # Fecha o PDF
    pdf.close()

    # Adiciona metadados
    dados['campos_extraidos'] = len(dados)
    dados['status_extracao'] = 'sucesso'

    return dados


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se o serviço está rodando"""
    return jsonify({
        "status": "online",
        "service": "PDF Multas Extractor",
        "version": "1.0.0"
    })


@app.route('/extrair-multa', methods=['POST'])
def extrair_multa():
    """
    Endpoint principal para extração de dados
    Aceita PDF como arquivo ou base64
    """
    try:
        # Verifica se foi enviado um arquivo
        if 'file' in request.files:
            arquivo = request.files['file']

            if arquivo.filename == '':
                return jsonify({"erro": "Nenhum arquivo selecionado"}), 400

            if not arquivo.filename.endswith('.pdf'):
                return jsonify({"erro": "Arquivo deve ser PDF"}), 400

            # Lê o conteúdo do arquivo
            pdf_bytes = arquivo.read()

        # Ou se foi enviado base64
        elif request.is_json and 'pdf_base64' in request.json:
            import base64
            pdf_base64 = request.json['pdf_base64']
            pdf_bytes = base64.b64decode(pdf_base64)

        else:
            return jsonify({
                "erro": "Envie um arquivo PDF via 'file' ou base64 via 'pdf_base64'"
            }), 400

        # Extrai os dados
        dados = extrair_dados_completos(pdf_bytes)

        return jsonify(dados), 200

    except Exception as e:
        return jsonify({
            "erro": str(e),
            "status_extracao": "falha"
        }), 500


@app.route('/extrair-lote', methods=['POST'])
def extrair_lote():
    """
    Processa múltiplos PDFs de uma vez
    """
    try:
        if 'files' not in request.files:
            return jsonify({"erro": "Nenhum arquivo enviado"}), 400

        arquivos = request.files.getlist('files')
        resultados = []

        for arquivo in arquivos:
            if arquivo.filename.endswith('.pdf'):
                pdf_bytes = arquivo.read()
                dados = extrair_dados_completos(pdf_bytes)
                dados['nome_arquivo'] = arquivo.filename
                resultados.append(dados)

        return jsonify({
            "total_processado": len(resultados),
            "resultados": resultados
        }), 200

    except Exception as e:
        return jsonify({
            "erro": str(e),
            "status": "falha"
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)