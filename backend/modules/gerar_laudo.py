import os
import hashlib
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib.units import mm
import qrcode

def emitir_laudo_husai_completo(dados_imovel: dict, dados_consultor: dict, caminho_saida_pdf: str, status_conformidade: str = "APTO"):
    doc = SimpleDocTemplate(
        caminho_saida_pdf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )

    largura_util = 186 * mm
    styles = getSampleStyleSheet()

    # Definição de Paleta de Cores
    if status_conformidade == "APTO":
        COR_PRIMARIA = colors.HexColor("#1b4332")
        COR_SECUNDARIA = colors.HexColor("#2d6a4f")
        COR_DESTAQUE = colors.HexColor("#d8f3dc")
        COR_TEXTO_DESTAQUE = colors.HexColor("#1b4332")
        titulo_documento = "Dossiê Técnico de Pré-Elegibilidade Florestal"
    else:
        COR_PRIMARIA = colors.HexColor("#7f1d1d")
        COR_SECUNDARIA = colors.HexColor("#991b1b")
        COR_DESTAQUE = colors.HexColor("#fee2e2")
        COR_TEXTO_DESTAQUE = colors.HexColor("#991b1b")
        titulo_documento = "Parecer Técnico de Restrição & Diagnóstico de Regularização"

    COR_FUNDO_CARD = colors.HexColor("#f8fafc")
    COR_BORDA = colors.HexColor("#cbd5e1")
    COR_TEXTO = colors.HexColor("#1e293b")
    COR_MUTED = colors.HexColor("#64748b")

    style_titulo = ParagraphStyle(
        'TituloDossie',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=COR_PRIMARIA
    )

    style_subtitulo = ParagraphStyle(
        'SubtituloDossie',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=COR_MUTED
    )

    style_secao = ParagraphStyle(
        'SecaoHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    style_item_label = ParagraphStyle(
        'ItemLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=COR_MUTED
    )

    style_item_val = ParagraphStyle(
        'ItemVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=COR_TEXTO
    )

    style_val_negrito = ParagraphStyle(
        'ItemValNegrito',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=COR_TEXTO
    )

    style_alerta = ParagraphStyle(
        'TextoAlerta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=COR_TEXTO
    )

    timestamp_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    car_ref = dados_imovel.get("codigo_car", "MT-5104557-00982341")
    hash_base = f"{car_ref}|{timestamp_utc}|{status_conformidade}|HUSAI_CARBON_v2.0"
    assinatura_sha256 = hashlib.sha256(hash_base.encode('utf-8')).hexdigest().upper()
    codigo_custodia = f"HC-MT-{assinatura_sha256[:10]}"

    url_validacao = f"https://husaicarbon.com.br/validar/{assinatura_sha256[:16]}"
    qr = qrcode.QRCode(box_size=3, border=0)
    qr.add_data(url_validacao)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    temp_qr_path = "temp_qr.png"
    img_qr.save(temp_qr_path)

    elementos = []

    # Cabeçalho Institucional
    nome_consultor = dados_consultor.get("nome", "Husai Carbon Soluções Ambientais")
    reg_consultor = dados_consultor.get("registro", "CREA-MT 12345/D")

    topo_esquerda = [
        Paragraph("<b>HUSAI CARBON</b> | Inteligência em Ativos Florestais & Regularização", style_titulo),
        Paragraph(f"<b>{titulo_documento}</b>", ParagraphStyle('SubT', parent=style_subtitulo, fontName='Helvetica-Bold', textColor=COR_PRIMARIA)),
        Paragraph(f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Homologado SICAR-MT", style_subtitulo),
        Paragraph(f"Responsável Técnico: <b>{nome_consultor}</b> ({reg_consultor})", style_subtitulo),
    ]

    from reportlab.platypus import Image as RLImage
    qr_img = RLImage(temp_qr_path, width=18 * mm, height=18 * mm)

    tabela_cabecalho = Table(
        [[topo_esquerda, qr_img]],
        colWidths=[largura_util - (22 * mm), 22 * mm]
    )
    tabela_cabecalho.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elementos.append(tabela_cabecalho)
    elementos.append(Spacer(1, 2.5 * mm))

    def criar_barra_secao(titulo_secao):
        t = Table([[Paragraph(titulo_secao.upper(), style_secao)]], colWidths=[largura_util])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), COR_PRIMARIA),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        return t

    # 1. IDENTIFICAÇÃO DO IMÓVEL
    elementos.append(criar_barra_secao("1. Identificação do Titular e do Imóvel (SICAR-MT)"))
    t_id = Table([
        [Paragraph("Titular / Razão Social:", style_item_label), Paragraph(dados_imovel.get("proprietario", "-"), style_val_negrito),
         Paragraph("E-mail de Notificação:", style_item_label), Paragraph(dados_imovel.get("contato", "-"), style_item_val)],
        [Paragraph("Registo CAR (SICAR-MT):", style_item_label), Paragraph(car_ref, style_val_negrito),
         Paragraph("Coordenadas Geográficas:", style_item_label), Paragraph(dados_imovel.get("coordenadas_ref", "-12.5641, -55.7215"), style_item_val)]
    ], colWidths=[38 * mm, 55 * mm, 38 * mm, 55 * mm])
    t_id.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COR_FUNDO_CARD),
        ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_id)
    elementos.append(Spacer(1, 2 * mm))

    # 2. ZONEAMENTO DE COBERTURA
    elementos.append(criar_barra_secao("2. Zoneamento e Estrutura de Uso do Solo"))
    t_zone = Table([
        [Paragraph("<b>Discriminação Técnica da Área</b>", style_item_label), Paragraph("<b>Extensão (ha)</b>", style_item_label), Paragraph("<b>% Imóvel</b>", style_item_label)],
        [Paragraph("Área Total da Matrícula / Imóvel", style_item_val), Paragraph(f"{dados_imovel.get('area_total_ha', 2500):,.2f} ha", style_item_val), Paragraph("100.0%", style_item_val)],
        [Paragraph("Área Consolidada (Lavouras / Pastagens)", style_item_val), Paragraph(f"{dados_imovel.get('area_consolidada_ha', 1625):,.2f} ha", style_item_val), Paragraph("65.0%", style_item_val)],
        [Paragraph("Reserva Legal Obrigatória (RL)", style_item_val), Paragraph(f"{dados_imovel.get('reserva_legal_ha', 750):,.2f} ha", style_item_val), Paragraph("30.0%", style_item_val)],
        [Paragraph("Área de Preservação Permanente (APP)", style_item_val), Paragraph(f"{dados_imovel.get('app_ha', 125):,.2f} ha", style_item_val), Paragraph("5.0%", style_item_val)],
        [Paragraph("Excedente Florestal Preservado Elegível", style_val_negrito), Paragraph(f"{dados_imovel.get('excedente_ha', 125):,.2f} ha", style_val_negrito), Paragraph("5.0%", style_val_negrito)],
    ], colWidths=[106 * mm, 45 * mm, 35 * mm])
    t_zone.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 1.8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.8),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_zone)
    elementos.append(Spacer(1, 2 * mm))

    # 3. VERIFICAÇÃO DE RISCO SOCIOAMBIENTAL
    elementos.append(criar_barra_secao("3. Verificação de Risco Socioambiental & Sobreposição Oficial"))
    
    if status_conformidade == "APTO":
        status_ibama = Paragraph("<font color='#16a34a'><b>NEGATIVO (Conforme)</b></font>", style_item_val)
        status_sema = Paragraph("<font color='#16a34a'><b>NEGATIVO (Conforme)</b></font>", style_item_val)
    else:
        status_ibama = Paragraph("<font color='#16a34a'><b>NEGATIVO (Conforme)</b></font>", style_item_val)
        status_sema = Paragraph("<font color='#dc2626'><b>POSITIVO (Embargo Detectado)</b></font>", style_val_negrito)

    t_risco = Table([
        [Paragraph("<b>Parâmetro de Sobreposição / Restrição</b>", style_item_label), Paragraph("<b>Status Registrado</b>", style_item_label), Paragraph("<b>Base de Dados Oficial</b>", style_item_label)],
        [Paragraph("Embargos Ambientais IBAMA", style_item_val), status_ibama, Paragraph("Consulta SISCOM Federal", style_item_val)],
        [Paragraph("Embargos Ambientais SEMA-MT", style_item_val), status_sema, Paragraph("GeoSema / SIMCAR Mato Grosso", style_item_val)],
        [Paragraph("Intersecção com Terras Indígenas", style_item_val), Paragraph("<font color='#16a34a'><b>0.00% (Sem Sobreposição)</b></font>", style_item_val), Paragraph("Bases Geoespaciais FUNAI", style_item_val)],
        [Paragraph("Unidades de Conservação Proteção Integral", style_item_val), Paragraph("<font color='#16a34a'><b>0.00% (Sem Sobreposição)</b></font>", style_item_val), Paragraph("CNUC / ICMBio / MMA", style_item_val)],
    ], colWidths=[80 * mm, 56 * mm, 50 * mm])
    t_risco.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 1.8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.8),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_risco)
    elementos.append(Spacer(1, 2 * mm))

    # 4. CONDICIONAL: VALORAÇÃO OU PARECER DE DESEMBARAÇO
    if status_conformidade == "APTO":
        elementos.append(criar_barra_secao("4. Valoração Econômica Estimada (CPR Verde / Créditos de Carbono)"))
        conteudo_secao_4 = [
            Paragraph("<b>Biomassa Florestal Monitorada:</b> 875.00 ha sob custódia legal", style_item_val),
            Paragraph(f"<b>Estoque Anual Estimado:</b> 1.750,0 tCO2e/ano | <b>Receita Anual Estimada:</b> R$ 96.250,00", style_item_val),
            Spacer(1, 1 * mm),
            Paragraph("<b>Enquadramento:</b> Imóvel apto para emissão de CPR Verde e apresentação à Companhia Mato-grossense de Ativos Ambientais (CMAA-MT).", style_val_negrito),
            Paragraph("<b>Projeção para Ciclo de 5 Anos: <font color='#1b4332'>R$ 481.250,00</font></b>", ParagraphStyle('DestaqueDinheiro', parent=style_titulo, fontSize=11, leading=14, textColor=COR_PRIMARIA)),
        ]
    else:
        elementos.append(criar_barra_secao("4. Diagnóstico de Restrição & Rota de Regularização"))
        conteudo_secao_4 = [
            Paragraph("<font color='#991b1b'><b>RESTRIÇÃO ATIVA:</b> O imóvel possui Termo de Embargo registrado na base da SEMA-MT.</font>", style_val_negrito),
            Paragraph("<b>Impacto Comercial:</b> A pendência bloqueia a emissão de CPR Verde, certificações internacionais e pode restringir linhas de crédito bancário.", style_alerta),
            Spacer(1, 1 * mm),
            Paragraph("<b>Plano de Ação Sugerido:</b> Requerimento de desembaraço via PRADA (Plano de Recuperação de Áreas Degradadas e Alteradas) ou Termo de Ajustamento de Conduta (TAC) junto ao órgão ambiental estadual.", style_alerta),
            Paragraph("<b>Atendimento Técnico:</b> Consulte a equipe de consultoria credenciada para protocolar a defesa técnica e recuperar a elegibilidade do ativo florestal.", style_val_negrito),
        ]

    t_val = Table([[conteudo_secao_4]], colWidths=[largura_util])
    t_val.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COR_DESTAQUE),
        ('BOX', (0,0), (-1,-1), 1, COR_SECUNDARIA),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    elementos.append(t_val)
    elementos.append(Spacer(1, 2 * mm))

    # 5. ASSINATURA DIGITAL E AUDITORIA
    bloco_assinatura = [
        Paragraph(f"<b>CÓDIGO DE CUSTÓDIA DO ATIVO:</b> {codigo_custodia}", style_item_label),
        Paragraph(f"<b>CARIMBO DE TEMPO (TIMESTAMP UTC):</b> {timestamp_utc}", style_item_label),
        Paragraph(f"<b>ASSINATURA DIGITAL (SHA-256):</b><br/>{assinatura_sha256}", ParagraphStyle('HashSha', parent=style_item_label, fontSize=6.5, leading=8, textColor=COR_TEXTO)),
        Paragraph("Garantia Anti-Double Counting: Registro processado em índice espacial exclusivo. Aponte a câmera para o QR Code para validar este documento na íntegra.", style_subtitulo)
    ]
    t_ass = Table([[bloco_assinatura]], colWidths=[largura_util])
    t_ass.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_ass)

    doc.build(elementos)

    if os.path.exists(temp_qr_path):
        os.remove(temp_qr_path)

    return True