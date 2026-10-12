import os
import io
import csv
import sqlite3
import secrets
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from backend.modules.gerar_laudo import emitir_laudo_husai_completo

app = FastAPI(title="Husai Carbon API")
security = HTTPBasic()

# Credenciais de acesso ao Painel Admin
ADMIN_USER = "admin"
ADMIN_PASS = "husai2026"

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

# Inicialização da base de dados local SQLite
DB_PATH = "leads_husai.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT,
            whatsapp TEXT,
            codigo_car TEXT,
            metodo TEXT,
            criado_em TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

class LeadModel(BaseModel):
    nome: str
    email: str
    whatsapp: str
    codigo_car: str
    metodo: str

@app.get("/", response_class=HTMLResponse)
def index():
    caminho_html = os.path.join("frontend", "index.html")
    with open(caminho_html, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/salvar-lead")
def salvar_lead(lead: LeadModel):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO leads (nome, email, whatsapp, codigo_car, metodo, criado_em)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (lead.nome, lead.email, lead.whatsapp, lead.codigo_car, lead.metodo, data_hora))
    conn.commit()
    conn.close()
    return {"status": "sucesso", "mensagem": "Lead registada com sucesso"}

@app.get("/api/download-laudo")
def download_laudo(
    car: str = Query("MT-5104557-00982341"),
    nome: str = Query("Produtor Rural"),
    email: str = Query("contato@fazenda.com.br")
):
    nome_limpo_car = car.replace("/", "_").replace("-", "_").replace(" ", "_")
    nome_arquivo_pdf = f"laudo_{nome_limpo_car}.pdf"
    caminho_pdf = os.path.join(".", nome_arquivo_pdf)

    dados_imovel = {
        "codigo_car": car,
        "proprietario": nome,
        "contato": email,
        "coordenadas_ref": "-12.5641,-55.7215;-12.5890,-55.7001",
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

    emitir_laudo_husai_completo(dados_imovel, dados_consultor, caminho_pdf)

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

@app.get("/admin", response_class=HTMLResponse)
def painel_admin(username: str = Depends(verificar_admin)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email, whatsapp, codigo_car, metodo, criado_em FROM leads ORDER BY id DESC")
    linhas = cursor.fetchall()
    conn.close()

    tabela_html = ""
    for r in linhas:
        tabela_html += f"""
        <tr>
            <td style="padding:10px; border-bottom:1px solid #ddd;">{r[0]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-weight:600;">{r[1]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd;">{r[2]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd;">{r[3]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-family:monospace;">{r[4]}</td>
            <td style="padding:10px; border-bottom:1px solid #ddd;"><span style="background:#e8f5e9; color:#2e7d32; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:bold;">{r[5]}</span></td>
            <td style="padding:10px; border-bottom:1px solid #ddd; font-size:12px; color:#666;">{r[6]}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>HUSAI CARBON | Painel de Leads</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #f8f9fa; padding: 2rem; color: #333; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }}
            .topo {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }}
            h1 {{ color: #1b4332; font-size: 1.5rem; margin-bottom: 0.3rem; }}
            p {{ color: #666; font-size: 0.9rem; margin: 0; }}
            .btn-csv {{ background: #2d6a4f; color: white; text-decoration: none; padding: 0.7rem 1.2rem; border-radius: 8px; font-size: 0.85rem; font-weight: 700; }}
            .btn-csv:hover {{ background: #1b4332; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; margin-top: 1rem; }}
            th {{ background: #1b4332; color: white; padding: 10px; font-size: 13px; text-transform: uppercase; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="topo">
                <div>
                    <h1>HUSAI CARBON — Relatório de Clientes & Leads</h1>
                    <p>Registos capturados via formulário e validações em tempo real.</p>
                </div>
                <a href="/admin/exportar-csv" class="btn-csv">📥 Baixar Planilha (.CSV)</a>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Nome / Razão</th>
                        <th>E-mail</th>
                        <th>WhatsApp</th>
                        <th>CAR</th>
                        <th>Método</th>
                        <th>Data/Hora</th>
                    </tr>
                </thead>
                <tbody>
                    {tabela_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

@app.get("/admin/exportar-csv")
def exportar_csv(username: str = Depends(verificar_admin)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email, whatsapp, codigo_car, metodo, criado_em FROM leads ORDER BY id DESC")
    linhas = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Nome / Razao", "E-mail", "WhatsApp", "Codigo CAR", "Metodo", "Data Cadastro"])

    for r in linhas:
        writer.writerow(r)

    conteudo_csv = output.getvalue().encode("utf-8-sig")
    return Response(
        content=conteudo_csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_husai_carbon.csv"}
    )