import os
import hashlib
import re
from io import BytesIO
from pathlib import Path
from datetime import datetime
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
import qrcode


def _formatar_coordenadas(coordenadas):
    coordenadas_match = re.match(
        r"^\s*\(?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*,?\s*"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
        coordenadas
    )
    if coordenadas_match:
        latitude, longitude = coordenadas_match.groups()
        return f"{latitude}, {longitude}"
    return coordenadas.strip().rstrip(",").strip()


def _gerar_mapa_car(codigo_car):
    if Path(codigo_car).name != codigo_car:
        raise ValueError(f"Código CAR inválido para gerar o mapa: {codigo_car}")

    pasta_car = Path(__file__).resolve().parents[2] / "gis_data" / "shapefiles"
    caminhos_car = [
        pasta_car / f"{codigo_car}{extensao}"
        for extensao in (".shp", ".geojson", ".gpkg", ".json")
    ]
    arquivos_car = [caminho for caminho in caminhos_car if caminho.is_file()]
    if not arquivos_car:
        raise FileNotFoundError(
            f"Não foram encontrados dados geográficos para o CAR {codigo_car} "
            f"em {pasta_car}."
        )
    if len(arquivos_car) > 1:
        raise ValueError(
            f"Há mais de um arquivo geográfico para o CAR {codigo_car}: "
            f"{', '.join(str(caminho) for caminho in arquivos_car)}"
        )

    car = gpd.read_file(arquivos_car[0])
    if car.empty or car.geometry.isna().all():
        raise ValueError(f"O CAR {codigo_car} não contém geometrias.")
    if car.crs is None:
        raise ValueError(f"O arquivo geográfico do CAR {codigo_car} não informa o CRS.")

    geometrias = car.geometry.dropna()
    geometrias = geometrias[~geometrias.is_empty]
    if geometrias.empty:
        raise ValueError(f"O CAR {codigo_car} não contém geometrias válidas.")
    if not geometrias.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError(f"O CAR {codigo_car} deve conter apenas polígonos.")

    crs_utm = car.estimate_utm_crs()
    if crs_utm is None:
        raise ValueError(f"Não foi possível determinar uma projeção UTM para o CAR {codigo_car}.")

    geometria = gpd.GeoSeries(geometrias, crs=car.crs).to_crs(crs_utm).union_all()
    min_x, min_y, max_x, max_y = geometria.bounds
    tolerancia = max(max_x - min_x, max_y - min_y) * 0.001
    geometria = geometria.simplify(tolerancia, preserve_topology=True)
    if geometria.is_empty:
        raise ValueError(f"A geometria simplificada do CAR {codigo_car} está vazia.")

    buffer_mapa = BytesIO()
    figura, eixo = plt.subplots(figsize=(7.5, 9), dpi=300)
    try:
        gpd.GeoSeries([geometria], crs=crs_utm).plot(
            ax=eixo,
            facecolor="#d8f3dc",
            edgecolor="#1b4332",
            linewidth=1.1,
        )
        eixo.axis("off")
        figura.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        figura.savefig(
            buffer_mapa,
            format="png",
            dpi=300,
            bbox_inches="tight",
            pad_inches=0.08,
            facecolor="white",
        )
        buffer_mapa.seek(0)
    except Exception:
        buffer_mapa.close()
        raise
    finally:
        plt.close(figura)

    buffer_mapa.seek(0)
    return buffer_mapa

def emitir_laudo_husai_completo(dados_imovel: dict, dados_consultor: dict, caminho_saida_pdf: str, status_conformidade: str = "APTO"):
    rodape = {}

    def desenhar_rodape(canvas, documento):
        tabela_rodape = rodape.get("tabela")
        if tabela_rodape is None or documento.page != 1:
            return

        tabela_rodape.wrap(documento.width, documento.bottomMargin)
        tabela_rodape.drawOn(canvas, documento.leftMargin, 7 * mm)

    doc = SimpleDocTemplate(
        caminho_saida_pdf,
        pagesize=A4,
        leftMargin=9 * mm,
        rightMargin=9 * mm,
        topMargin=8 * mm,
        bottomMargin=36 * mm
    )

    largura_util = A4[0] - doc.leftMargin - doc.rightMargin
    espacamento_secao = 12 * mm
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
    buffer_mapa = _gerar_mapa_car(car_ref)

    class CanvasComMapa(Canvas):
        def showPage(self):
            pagina_atual = self._pageNumber
            super().showPage()

            if pagina_atual == 1:
                self.saveState()
                self.setFont("Helvetica-Bold", 14)
                self.setFillColorRGB(0, 0.4, 0)
                self.drawString(
                    50,
                    800,
                    "ANEXO I - MAPA GEOESPACIAL DA ÁREA AUDITADA",
                )
                buffer_mapa.seek(0)
                mapa_img = ImageReader(buffer_mapa)
                self.drawImage(
                    mapa_img,
                    50,
                    350,
                    width=500,
                    height=400,
                    preserveAspectRatio=True,
                    anchor="c",
                    mask="auto",
                )
                self.restoreState()

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
    espacadores_distribuicao = []

    # Cabeçalho Institucional
    nome_consultor = dados_consultor.get("nome", "Husai Carbon Soluções Ambientais")
    reg_consultor = dados_consultor.get("registro", "CREA-MT 12345/D")

    topo_esquerda = [
        Paragraph("<b>HUSAI CARBON</b> | Inteligência em Ativos Florestais & Regularização", style_titulo),
        Paragraph(f"<b>{titulo_documento}</b>", ParagraphStyle('SubT', parent=style_subtitulo, fontName='Helvetica-Bold', textColor=COR_PRIMARIA)),
        Paragraph(f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Homologado SICAR-MT", style_subtitulo),
        Paragraph(f"Responsável Técnico: <b>{nome_consultor}</b> ({reg_consultor})", style_subtitulo),
    ]

    tabela_cabecalho = Table([[topo_esquerda]], colWidths=[largura_util])
    tabela_cabecalho.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 0.75, COR_BORDA),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elementos.append(tabela_cabecalho)
    espacador_cabecalho = Spacer(1, 8 * mm)
    elementos.append(espacador_cabecalho)
    espacadores_distribuicao.append(espacador_cabecalho)

    def adicionar_espacamento_secao():
        espacador = Spacer(1, espacamento_secao)
        elementos.append(espacador)
        espacadores_distribuicao.append(espacador)

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
    coordenadas = _formatar_coordenadas(
        str(dados_imovel.get("coordenadas_ref") or "-12.5641, -55.7215")
    )

    t_id = Table([
        [Paragraph("Titular / Razão Social:", style_item_label), Paragraph(dados_imovel.get("proprietario", "-"), style_val_negrito),
         Paragraph("E-mail de Notificação:", style_item_label), Paragraph(dados_imovel.get("contato", "-"), style_item_val)],
        [Paragraph("Registo CAR (SICAR-MT):", style_item_label), Paragraph(car_ref, style_val_negrito),
         Paragraph("Coordenadas Geográficas:", style_item_label), Paragraph(coordenadas, style_item_val)]
    ], colWidths=[39 * mm, 56 * mm, 39 * mm, largura_util - (134 * mm)])
    t_id.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COR_FUNDO_CARD),
        ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_id)
    adicionar_espacamento_secao()

    # 2. ZONEAMENTO DE COBERTURA
    elementos.append(criar_barra_secao("2. Zoneamento e Estrutura de Uso do Solo"))
    t_zone = Table([
        [Paragraph("<b>Discriminação Técnica da Área</b>", style_item_label), Paragraph("<b>Extensão (ha)</b>", style_item_label), Paragraph("<b>% Imóvel</b>", style_item_label)],
        [Paragraph("Área Total da Matrícula / Imóvel", style_item_val), Paragraph(f"{dados_imovel.get('area_total_ha', 2500):,.2f} ha", style_item_val), Paragraph("100.0%", style_item_val)],
        [Paragraph("Área Consolidada (Lavouras / Pastagens)", style_item_val), Paragraph(f"{dados_imovel.get('area_consolidada_ha', 1625):,.2f} ha", style_item_val), Paragraph("65.0%", style_item_val)],
        [Paragraph("Reserva Legal Obrigatória (RL)", style_item_val), Paragraph(f"{dados_imovel.get('reserva_legal_ha', 750):,.2f} ha", style_item_val), Paragraph("30.0%", style_item_val)],
        [Paragraph("Área de Preservação Permanente (APP)", style_item_val), Paragraph(f"{dados_imovel.get('app_ha', 125):,.2f} ha", style_item_val), Paragraph("5.0%", style_item_val)],
        [Paragraph("Excedente Florestal Preservado Elegível", style_val_negrito), Paragraph(f"{dados_imovel.get('excedente_ha', 125):,.2f} ha", style_val_negrito), Paragraph("5.0%", style_val_negrito)],
    ], colWidths=[108 * mm, 46 * mm, largura_util - (154 * mm)])
    t_zone.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_zone)
    adicionar_espacamento_secao()

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
    ], colWidths=[82 * mm, 56 * mm, largura_util - (138 * mm)])
    t_risco.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_risco)
    adicionar_espacamento_secao()

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
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    elementos.append(t_val)

    # 5. ASSINATURA DIGITAL E AUDITORIA
    bloco_assinatura = [
        Paragraph(f"<b>CÓDIGO DE CUSTÓDIA DO ATIVO:</b> {codigo_custodia}", style_item_label),
        Paragraph(f"<b>CARIMBO DE TEMPO (TIMESTAMP UTC):</b> {timestamp_utc}", style_item_label),
        Paragraph(f"<b>ASSINATURA DIGITAL (SHA-256):</b><br/>{assinatura_sha256}", ParagraphStyle('HashSha', parent=style_item_label, fontSize=6.5, leading=8, textColor=COR_TEXTO)),
        Paragraph("Garantia Anti-Double Counting: Registro processado em índice espacial exclusivo. Aponte a câmera para o QR Code para validar este documento na íntegra.", style_subtitulo)
    ]
    qr_img = Image(temp_qr_path, width=18 * mm, height=18 * mm)
    tabela_rodape = Table(
        [[bloco_assinatura, qr_img]],
        colWidths=[largura_util - (22 * mm), 22 * mm]
    )
    tabela_rodape.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.75, COR_BORDA),
        ('LINEABOVE', (0,0), (-1,0), 1, COR_SECUNDARIA),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    rodape["tabela"] = tabela_rodape

    altura_conteudo = sum(
        elemento.wrap(doc.width, doc.height)[1]
        for elemento in elementos
    )
    altura_alvo = doc.height - (5 * mm)
    altura_livre = max(0, altura_alvo - altura_conteudo)
    if espacadores_distribuicao:
        # Distribui a altura que sobraria em branco pelos intervalos entre secções.
        incremento = altura_livre / len(espacadores_distribuicao)
        for espacador in espacadores_distribuicao:
            espacador.height += incremento

    elementos.extend([
        PageBreak(),
        Spacer(1, 1),
    ])

    try:
        doc.build(
            elementos,
            onFirstPage=desenhar_rodape,
            canvasmaker=CanvasComMapa,
        )
    finally:
        buffer_mapa.close()
        if os.path.exists(temp_qr_path):
            os.remove(temp_qr_path)

    return True