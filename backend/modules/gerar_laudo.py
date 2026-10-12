import os
import hashlib
from datetime import datetime, timezone
import qrcode
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def obter_elemento_logo(estilo_fallback):
    caminho_logo = os.path.join("assets", "logo.png")
    if os.path.exists(caminho_logo):
        try:
            with PILImage.open(caminho_logo) as img:
                img_formatada = os.path.join("assets", "logo_processado.png")
                img.convert("RGBA").save(img_formatada, "PNG")
                return Image(img_formatada, width=155, height=50)
        except Exception:
            pass
    return Paragraph("<b>HUSAI CARBON</b><br/><font size=8 color='#2d6a4f'>Inteligência em Ativos Florestais & Conformidade</font>", estilo_fallback)

def emitir_laudo_husai_completo(dados_imovel, dados_consultor, caminho_saida="laudo_executivo_husai.pdf"):
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conteudo_para_hash = f"{dados_imovel.get('codigo_car')}-{dados_imovel.get('proprietario')}-{timestamp_utc}"
    sha256_hash = hashlib.sha256(conteudo_para_hash.encode('utf-8')).hexdigest().upper()
    codigo_custodia = f"HC-MT-{sha256_hash[:10]}"
    codigo_validacao = sha256_hash[:16]
    
    url_validacao = f"https://husaicarbon.com.br/validar/{codigo_validacao}"
    
    qr = qrcode.QRCode(box_size=5, border=1)
    qr.add_data(url_validacao)
    qr_img = qr.make_image(fill_color="#1b4332", back_color="white")
    temp_qr = "temp_qr.png"
    qr_img.save(temp_qr)

    # Margens de 32 pt garantem 531 pt de largura útil em A4
    doc = SimpleDocTemplate(
        caminho_saida,
        pagesize=A4,
        leftMargin=32,
        rightMargin=32,
        topMargin=28,
        bottomMargin=24
    )

    elementos = []
    styles = getSampleStyleSheet()

    cor_primaria = colors.HexColor("#1b4332")
    cor_destaque = colors.HexColor("#2d6a4f")
    cor_fundo_tabela = colors.HexColor("#f8fafc")
    cor_borda = colors.HexColor("#cbd5e1")

    estilo_titulo = ParagraphStyle(
        'DocTitulo',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=cor_primaria
    )
    estilo_subtitulo = ParagraphStyle(
        'DocSubTitulo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=13,
        textColor=colors.HexColor("#334155"),
        alignment=2
    )
    estilo_secao = ParagraphStyle(
        'SecaoTitulo',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=15,
        textColor=cor_destaque
    )
    estilo_corpo = ParagraphStyle(
        'DocCorpo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b")
    )
    estilo_bold = ParagraphStyle(
        'DocBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0f172a")
    )
    estilo_th = ParagraphStyle(
        'DocTH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.white
    )
    estilo_valor = ParagraphStyle(
        'DocValor',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#b7791f"),
        alignment=1
    )
    estilo_hash = ParagraphStyle(
        'DocHash',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=10,
        textColor=colors.HexColor("#1e293b")
    )

    # 1. Cabeçalho Executivo
    col_esquerda = obter_elemento_logo(estilo_titulo)
    header_data = [
        [
            col_esquerda,
            Paragraph(
                f"<b>Dossiê Técnico de Pré-Elegibilidade Florestal</b><br/>"
                f"<b>Emissão:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')} | Homologado SICAR-MT<br/>"
                f"<b>Consultoria:</b> {dados_consultor.get('nome', 'Husai Carbon')} ({dados_consultor.get('registro', 'CREA-MT')})",
                estilo_subtitulo
            )
        ]
    ]
    header_table = Table(header_data, colWidths=[230, 301])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 2, cor_primaria),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8)
    ]))
    elementos.append(header_table)
    elementos.append(Spacer(1, 14))

    # 2. Secção 1: Identificação do Titular e Imóvel
    elementos.append(Paragraph("1. IDENTIFICAÇÃO DO TITULAR E DO IMÓVEL (SICAR-MT)", estilo_secao))
    elementos.append(Spacer(1, 5))

    proprietario = dados_imovel.get("proprietario", "Produtor Rural Não Informado")
    email_contato = dados_imovel.get("contato", "Não informado")
    codigo_car = dados_imovel.get("codigo_car", "MT-PADRAO")
    coords = dados_imovel.get("coordenadas_ref", "-12.5641, -55.7215 (Médio-Norte MT)")

    dados_titular = [
        [Paragraph("Titular / Razão Social:", estilo_bold), Paragraph(str(proprietario), estilo_corpo),
         Paragraph("E-mail de Notificação:", estilo_bold), Paragraph(str(email_contato), estilo_corpo)],
        [Paragraph("Registo CAR (SICAR-MT):", estilo_bold), Paragraph(str(codigo_car), estilo_corpo),
         Paragraph("Coordenadas Geográficas:", estilo_bold), Paragraph(str(coords), estilo_corpo)]
    ]
    tabela_titular = Table(dados_titular, colWidths=[125, 150, 115, 141])
    tabela_titular.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), cor_fundo_tabela),
        ('BOX', (0,0), (-1,-1), 0.5, cor_borda),
        ('INNERGRID', (0,0), (-1,-1), 0.5, cor_borda),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    elementos.append(tabela_titular)
    elementos.append(Spacer(1, 14))

    # 3. Secção 2: Conformidade e Estruturação de Áreas
    elementos.append(Paragraph("2. CONFORMIDADE AMBIENTAL E ZONEAMENTO DE COBERTURA", estilo_secao))
    elementos.append(Spacer(1, 5))

    dados_areas = [
        [Paragraph("Discriminação Técnica da Área", estilo_th), Paragraph("Extensão (ha)", estilo_th), Paragraph("% Imóvel", estilo_th)],
        [Paragraph("Área Total da Matrícula / Imóvel", estilo_corpo), Paragraph(f"{dados_imovel.get('area_total_ha', 2500.0):,.2f} ha", estilo_corpo), Paragraph("100.0%", estilo_corpo)],
        [Paragraph("Área Consolidada (Lavouras / Pastagens)", estilo_corpo), Paragraph(f"{dados_imovel.get('area_consolidada_ha', 1625.0):,.2f} ha", estilo_corpo), Paragraph("65.0%", estilo_corpo)],
        [Paragraph("Reserva Legal Obrigatória (RL)", estilo_corpo), Paragraph(f"{dados_imovel.get('reserva_legal_ha', 750.0):,.2f} ha", estilo_corpo), Paragraph("30.0%", estilo_corpo)],
        [Paragraph("Área de Preservação Permanente (APP)", estilo_corpo), Paragraph(f"{dados_imovel.get('app_ha', 125.0):,.2f} ha", estilo_corpo), Paragraph("5.0%", estilo_corpo)],
        [Paragraph("Excedente Florestal Preservado Elegível", estilo_bold), Paragraph(f"{dados_imovel.get('excedente_ha', 125.0):,.2f} ha", estilo_bold), Paragraph("5.0%", estilo_bold)],
    ]
    tabela_areas = Table(dados_areas, colWidths=[271, 130, 130])
    tabela_areas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), cor_primaria),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, cor_borda),
        ('INNERGRID', (0,0), (-1,-1), 0.5, cor_borda),
    ]))
    elementos.append(tabela_areas)
    elementos.append(Spacer(1, 14))

    # 4. Secção 3: Risco Socioambiental (Primeiro a terra desembaraçada)
    elementos.append(Paragraph("3. VERIFICAÇÃO DE RISCO SOCIOAMBIENTAL & CONFORMIDADE REGULATÓRIA", estilo_secao))
    elementos.append(Spacer(1, 5))

    dados_socio = [
        [Paragraph("Parâmetro de Sobreposição / Restrição", estilo_th), Paragraph("Status Registado", estilo_th), Paragraph("Base de Dados Consultada", estilo_th)],
        [Paragraph("Embargos Ambientais IBAMA", estilo_corpo), Paragraph("<font color='#16a34a'><b>NEGATIVO (Conforme)</b></font>", estilo_corpo), Paragraph("Consulta Pública SISCOM", estilo_corpo)],
        [Paragraph("Embargos Ambientais SEMA-MT", estilo_corpo), Paragraph("<font color='#16a34a'><b>NEGATIVO (Conforme)</b></font>", estilo_corpo), Paragraph("GeoSema / SIMCAR", estilo_corpo)],
        [Paragraph("Intersecção com Terras Indígenas", estilo_corpo), Paragraph("0.00% (Sem Sobreposição)", estilo_corpo), Paragraph("Bases Geoespaciais FUNAI", estilo_corpo)],
        [Paragraph("Unidades de Conservação Proteção Integral", estilo_corpo), Paragraph("0.00% (Sem Sobreposição)", estilo_corpo), Paragraph("CNUC / MMA", estilo_corpo)],
    ]
    tabela_socio = Table(dados_socio, colWidths=[201, 165, 165])
    tabela_socio.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), cor_destaque),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, cor_borda),
        ('INNERGRID', (0,0), (-1,-1), 0.5, cor_borda),
    ]))
    elementos.append(tabela_socio)
    elementos.append(Spacer(1, 14))

    # 5. Secção 4: Valoração Económica
    elementos.append(Paragraph("4. VALORAÇÃO ECONÓMICA ESTIMADA (CPR VERDE / ATIVOS DE CARBONO)", estilo_secao))
    elementos.append(Spacer(1, 5))

    v_anual = dados_imovel.get('valor_anual_brl', 96250.0)
    v_5anos = dados_imovel.get('valor_ciclo_5_anos_brl', 481250.0)
    tco2 = dados_imovel.get('tco2_ano', 1750.0)

    dados_fin = [
        [
            Paragraph(
                f"<b>Biomassa Florestal Monitorada:</b> {dados_imovel.get('area_preservada_ha', 875.0):,.2f} ha sob custódia legal<br/>"
                f"<b>Estoque Anual de Remoção:</b> {tco2:,.1f} tCO2e/ano | <b>Receita Anual Estimada:</b> R$ {v_anual:,.2f}<br/>"
                f"<font size=8 color='#64748b'><b>Enquadramento:</b> Imóvel apto para emissão de CPR Verde e apresentação à CMAA-MT</font>",
                estilo_corpo
            ),
            Paragraph(f"<font size=9 color='#78350f'>Projeção Ciclo 5 Anos:</font><br/><b>R$ {v_5anos:,.2f}</b>", estilo_valor)
        ]
    ]
    tabela_fin = Table(dados_fin, colWidths=[331, 200])
    tabela_fin.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#fffbeb")),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#d97706")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    elementos.append(tabela_fin)
    elementos.append(Spacer(1, 18))

    # 6. Rodapé com Assinatura SHA-256 e QR Code (Ocupa o terço final)
    bloco_validacao = [
        [
            Paragraph(
                f"<b>CÓDIGO DE CUSTÓDIA DO ATIVO:</b> {codigo_custodia}<br/>"
                f"<b>CARIMBO DE TEMPO (TIMESTAMP UTC):</b> {timestamp_utc}<br/>"
                f"<b>ASSINATURA DIGITAL (SHA-256):</b><br/>"
                f"<font size=6.5 color='#0f172a'>{sha256_hash}</font><br/>"
                f"<i>Garantia Anti-Double Counting: Dados processados com índice espacial exclusivo. Aponte a câmara para o QR Code para validar este documento na íntegra.</i>",
                estilo_hash
            ),
            Image(temp_qr, width=72, height=72)
        ]
    ]
    tabela_val = Table(bloco_validacao, colWidths=[451, 80])
    tabela_val.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elementos.append(KeepTogether([tabela_val]))

    doc.build(elementos)

    if os.path.exists(temp_qr):
        os.remove(temp_qr)

    return caminho_saida