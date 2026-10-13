import os
import io
import csv
import re
import sqlite3
import secrets
import traceback
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import mercadopago

from backend.modules.gerar_laudo import emitir_laudo_husai_completo

load_dotenv()

app = FastAPI(title="Husai Carbon API")
security = HTTPBasic()

ADMIN_USER = "admin"
ADMIN_PASS = "husai2026"

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()

def verificar_admin(credentials: HTTPBasicCredentials = Depends(security)):
    user_correto = secrets.compare_digest(credentials.username, ADMIN_USER)
    pass_correta = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (user_correto and pass_correta):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso não autorizado",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

DB_PATH = "leads_husai.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Tabela de Leads e Auditorias
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT,
            whatsapp TEXT,
            codigo_car TEXT,
            metodo TEXT,
            status TEXT DEFAULT 'APTO',
            consultor_id INTEGER,
            criado_em TEXT
        )
    """)
    # Tabela de Consultores Parceiros
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consultores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            registro_classe TEXT,
            email TEXT UNIQUE,
            whatsapp TEXT,
            creditos_saldo INTEGER DEFAULT 10,
            criado_em TEXT
        )
    """)
    # Criar consultor demonstrativo caso não exista
    cursor.execute("SELECT id FROM consultores WHERE email = 'parceiro@agroconsult.com.br'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO consultores (nome, registro_classe, email, whatsapp, creditos_saldo, criado_em)
            VALUES ('AgroConsult Engenharia Florestal', 'CREA-MT 18942/D', 'parceiro@agroconsult.com.br', '(66) 99654-3210', 10, ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))

    conn.commit()
    conn.close()

init_db()

class LeadModel(BaseModel):
    nome: str
    email: str
    whatsapp: str
    codigo_car: str
    metodo: str
    status: str = "APTO"
    consultor_id: int = None

class PixRequestModel(BaseModel):
    nome: str
    documento: str = ""
    email: str
    codigo_car: str

@app.get("/", response_class=HTMLResponse)
def index():
    caminho_html = os.path.join("frontend", "index.html")
    with open(caminho_html, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/criar-pix")
def criar_pix(dados: PixRequestModel):
    valor_dossie = 350.00
    
    if not MP_ACCESS_TOKEN or MP_ACCESS_TOKEN == "SEU_ACCESS_TOKEN_DO_MERCADO_PAGO":
        print("[PIX AVISO] MP_ACCESS_TOKEN não configurado. Retornando fallback.")
        return {
            "status": "sucesso",
            "simulado": True,
            "id_pagamento": "simulado_123456",
            "pix_copia_cola": "00020126580014br.gov.bcb.pix0136husaicarbon-ficticio-teste520400005303986540350.005802BR5920HUSAI TECNOLOGIA6009IPIRANGA62070503***6304ABCD",
            "qr_code_base64": ""
        }

    try:
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        partes_nome = dados.nome.strip().split(" ", 1)
        primeiro_nome = partes_nome[0]
        sobrenome = partes_nome[1] if len(partes_nome) > 1 else "Rural"

        doc_limpo = re.sub(r"\D", "", dados.documento)
        if len(doc_limpo) == 14:
            tipo_doc, numero_doc = "CNPJ", doc_limpo
        elif len(doc_limpo) == 11:
            tipo_doc, numero_doc = "CPF", doc_limpo
        else:
            tipo_doc, numero_doc = "CPF", "19119119100"

        payment_data = {
            "transaction_amount": float(valor_dossie),
            "description": f"Dossie Tecnico Husai Carbon - CAR {dados.codigo_car}",
            "payment_method_id": "pix",
            "payer": {
                "email": dados.email.strip(),
                "first_name": primeiro_nome,
                "last_name": sobrenome,
                "identification": { "type": tipo_doc, "number": numero_doc }
            }
        }

        payment_response = sdk.payment().create(payment_data)
        payment = payment_response.get("response", {})
        
        pix_info = payment.get("point_of_interaction", {}).get("transaction_data", {})
        copia_cola = pix_info.get("qr_code")
        qr_base64 = pix_info.get("qr_code_base64")

        if copia_cola:
            return {
                "status": "sucesso",
                "simulado": False,
                "id_pagamento": payment.get("id"),
                "pix_copia_cola": copia_cola,
                "qr_code_base64": qr_base64
            }
        else:
            return {
                "status": "sucesso",
                "simulado": True,
                "id_pagamento": f"fallback_{payment.get('id', '0')}",
                "pix_copia_cola": "00020126580014br.gov.bcb.pix0136husaicarbon-ficticio-teste520400005303986540350.005802BR5920HUSAI TECNOLOGIA6009IPIRANGA62070503***6304ABCD",
                "qr_code_base64": ""
            }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PIX: {str(e)}")

@app.post("/api/salvar-lead")
def salvar_lead(lead: LeadModel):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO leads (nome, email, whatsapp, codigo_car, metodo, status, consultor_id, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (lead.nome, lead.email, lead.whatsapp, lead.codigo_car, lead.metodo, lead.status, lead.consultor_id, data_hora))
    conn.commit()
    conn.close()
    return {"status": "sucesso", "mensagem": "Lead registrada com sucesso"}

@app.get("/api/download-laudo")
def download_laudo(
    car: str = Query("MT-5104557-00982341"),
    nome: str = Query("Produtor Rural"),
    email: str = Query("contato@fazenda.com.br"),
    status_laudo: str = Query("APTO")
):
    nome_limpo_car = car.replace("/", "_").replace("-", "_").replace(" ", "_")
    nome_arquivo_pdf = f"laudo_{nome_limpo_car}.pdf"
    caminho_pdf = os.path.join(".", nome_arquivo_pdf)

    dados_imovel = {
        "codigo_car": car,
        "proprietario": nome,
        "contato": email,
        "coordenadas_ref": "-12.5641, -55.7215 (Médio-Norte MT)",
        "area_total_ha": 2500.0,
        "area_consolidada_ha": 1625.0,
        "reserva_legal_ha": 750.0,
        "app_ha": 125.0,
        "excedente_ha": 125.0,
        "area_preservada_ha": 875.0,
        "tco2_ano": 1750.0,
        "valor_anual_brl": 96250.00,
        "valor_ciclo_5_anos_brl": 481250.00
    }
    dados_consultor = {
        "nome": "Husai Carbon Soluções Ambientais",
        "registro": "CREA-MT 12345/D"
    }

    emitir_laudo_husai_completo(dados_imovel, dados_consultor, caminho_pdf, status_conformidade=status_laudo)

    return FileResponse(
        path=caminho_pdf,
        filename=f"Dossie_Husai_{car}.pdf",
        media_type="application/pdf"
    )

@app.get("/validar/{codigo}", response_class=HTMLResponse)
def validar_dossie(codigo: str):
    caminho_html = os.path.join("frontend", "validar.html")
    with open(caminho_html, "r", encoding="utf-8") as f:
        conteudo = f.read()
    return conteudo.replace("{{CODIGO}}", codigo)

# PAINEL GERAL ADMINISTRATIVO HUSAI
@app.get("/admin", response_class=HTMLResponse)
def painel_admin(username: str = Depends(verificar_admin)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email, whatsapp, codigo_car, metodo, status, criado_em FROM leads ORDER BY id DESC")
    linhas = cursor.fetchall()
    conn.close()

    tabela_html = ""
    for r in linhas:
        badge_cor = "#2e7d32" if r[6] == "APTO" else "#b91c1c"
        badge_bg = "#e8f5e9" if r[6] == "APTO" else "#fee2e2"
        tabela_html += f"""
        <tr>
            <td style="padding:10px; border-bottom:1px solid #ddd;">{r[0]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-weight:600;">{r[1]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd;">{r[2]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd;">{r[3]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-family:monospace;">{r[4]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd;"><b>{r[5]}</b></td>
            <td style="padding:10px; border-bottom:1px solid #ddd;"><span style="background:{badge_bg}; color:{badge_cor}; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:bold;">{r[6]}</span></td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-size:12px; color:#666;">{r[7]}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>HUSAI CARBON | Painel Central</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #f8f9fa; padding: 2rem; color: #333; }}
            .container {{ max-width: 1100px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }}
            .topo {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }}
            h1 {{ color: #1b4332; font-size: 1.5rem; margin-bottom: 0.3rem; }}
            .btn-csv {{ background: #2d6a4f; color: white; text-decoration: none; padding: 0.7rem 1.2rem; border-radius: 8px; font-size: 0.85rem; font-weight: 700; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; margin-top: 1rem; }}
            th {{ background: #1b4332; color: white; padding: 10px; font-size: 13px; text-transform: uppercase; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="topo">
                <div>
                    <h1>HUSAI CARBON — Painel Geral de Auditorias & Leads</h1>
                    <p>Controle de Dossiês Emitidos e Demandas de Regularização.</p>
                </div>
                <div>
                    <a href="/consultor/dashboard" style="margin-right: 10px; color: #1b4332; font-weight:bold; font-size:0.85rem;">Portal do Consultor &rarr;</a>
                    <a href="/admin/exportar-csv" class="btn-csv">📥 Baixar Planilha (.CSV)</a>
                </div>
            </div>
            <table>
                <thead>
                    <tr><th>ID</th><th>Nome / Razão</th><th>E-mail</th><th>WhatsApp</th><th>CAR</th><th>Método</th><th>Status</th><th>Data/Hora</th></tr>
                </thead>
                <tbody>{tabela_html}</tbody>
            </table>
        </div>
    </body>
    </html>
    """

# PORTAL EXCLUSIVO DO CONSULTOR PARCEIRO
@app.get("/consultor/dashboard", response_class=HTMLResponse)
def portal_consultor():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, registro_classe, creditos_saldo FROM consultores LIMIT 1")
    consultor = cursor.fetchone()
    
    cursor.execute("SELECT nome, codigo_car, status, criado_em FROM leads WHERE consultor_id = ? ORDER BY id DESC", (consultor[0],))
    clientes = cursor.fetchall()
    conn.close()

    linhas_clientes = ""
    for c in clientes:
        cor_badge = "#2e7d32" if c[2] == "APTO" else "#b91c1c"
        bg_badge = "#e8f5e9" if c[2] == "APTO" else "#fee2e2"
        linhas_clientes += f"""
        <tr>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-weight:600;">{c[0]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-family:monospace;">{c[1]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd;"><span style="background:{bg_badge}; color:{cor_badge}; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:bold;">{c[2]}</span></td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-size:12px; color:#666;">{c[3]}</td>
        </tr>
        """
    if not clientes:
        linhas_clientes = "<tr><td colspan='4' style='padding:15px; text-align:center; color:#888;'>Nenhum cliente auditado por este escritório ainda.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>HUSAI CARBON | Portal do Consultor Parceiro</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #f1f5f9; padding: 2rem; color: #1e293b; }}
            .container {{ max-width: 950px; margin: 0 auto; }}
            .header-parceiro {{ background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-left: 5px solid #2d6a4f; }}
            .card-saldo {{ background: #1b4332; color: white; padding: 1rem 1.5rem; border-radius: 10px; text-align: right; }}
            .card-saldo h2 {{ font-size: 1.8rem; margin: 0; color: #52b788; }}
            .card-saldo p {{ margin: 0; font-size: 0.8rem; opacity: 0.9; }}
            .bloco-conteudo {{ background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; margin-top: 1rem; }}
            th {{ background: #f8fafc; padding: 10px; font-size: 12px; text-transform: uppercase; color: #64748b; border-bottom: 2px solid #e2e8f0; }}
            .btn-recarga {{ background: #0284c7; color: white; padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none; font-size: 0.8rem; font-weight: 700; display: inline-block; margin-top: 0.5rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-parceiro">
                <div>
                    <h1 style="color: #1b4332; font-size: 1.4rem; margin-bottom: 0.2rem;">{consultor[1]}</h1>
                    <p style="color: #64748b; font-size: 0.85rem; margin: 0;">Registro Profissional: <b>{consultor[2]}</b> | Escritório Homologado Husai Carbon</p>
                </div>
                <div class="card-saldo">
                    <p>SALDO DE CRÉDITOS</p>
                    <h2>{consultor[3]} Laudos</h2>
                    <a href="#" class="btn-recarga" onclick="alert('Recarga de pacotes via PIX: R$ 200,00 por laudo no pacote de 10 unidades.')">+ Comprar Créditos</a>
                </div>
            </div>

            <div class="bloco-conteudo">
                <h3 style="color: #1b4332; font-size: 1.1rem; margin-bottom: 0.4rem;">Carteira de Fazendas Auditadas</h3>
                <p style="color: #64748b; font-size: 0.85rem; margin: 0;">Todas as emissões geradas através deste escritório saem com co-branding e registro do seu conselho de classe.</p>
                
                <table>
                    <thead>
                        <tr><th>Cliente / Propriedade</th><th>Código CAR</th><th>Status Conformidade</th><th>Data</th></tr>
                    </thead>
                    <tbody>
                        {linhas_clientes}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/admin/exportar-csv")
def exportar_csv(username: str = Depends(verificar_admin)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email, whatsapp, codigo_car, metodo, status, criado_em FROM leads ORDER BY id DESC")
    linhas = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Nome / Razao", "E-mail", "WhatsApp", "Codigo CAR", "Metodo", "Status", "Data Cadastro"])
    for r in linhas:
        writer.writerow(r)

    conteudo_csv = output.getvalue().encode("utf-8-sig")
    return Response(
        content=conteudo_csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_husai_carbon.csv"}
    )