import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

# Coloca aqui o teu email e a password de app (não uses a password normal)
def send_welcome_email():
    try:
        msg = MIMEMultipart('alternative')
        msg["Subject"] = f"Bem-vindo à plataforma"
        msg["From"] = formataddr((str(Header("GestãoPro", "utf-8")), "geral.servicos.info@gmail.com"))
        msg["To"] = "<cesarcarpinteiro1998@gmail.com"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
            <div style="background:#2e7d32;padding:28px 32px;text-align:center;">
                <p style="color:white;font-size:20px;font-weight:bold;margin:0 0 4px;">Bem-vindo à plataforma</p>
                <p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;"></p>
            </div>
            <div style="background:white;padding:28px 32px;">
                <p style="font-size:15px;color:#1a1a1a;margin:0 0 12px;">Olá <strong></strong>,</p>
                <p style="font-size:14px;color:#555;line-height:1.6;margin:0 0 20px;">A tua conta foi criada com sucesso na plataforma <strong></strong>. Aqui estão os teus dados de acesso:</p>
                <div style="background:#eaf3de;border:1px solid #c0dd97;border-radius:8px;padding:20px 24px;margin-bottom:20px;">
                    <p style="font-size:11px;color:#639922;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;">Utilizador</p>
                    <p style="font-size:20px;font-weight:bold;color:#2e7d32;margin:0 0 16px;"></p>
                    <p style="font-size:11px;color:#639922;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;">Password temporária</p>
                    <p style="font-size:20px;font-weight:bold;color:#2e7d32;margin:0;"></p>
                </div>
                {f'<div style="background:#e8f0fe;border:1px solid #b3c6f7;border-radius:8px;padding:20px 24px;margin-bottom:20px;"><p style="font-size:11px;color:#3c5a99;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;">Código de verificação</p><p style="font-size:32px;font-weight:bold;color:#1a3a8f;margin:0;letter-spacing:8px;">'  '</p></div>' }
                <div style="background:#faeeda;border:1px solid #fac775;border-radius:8px;padding:10px 14px;margin-bottom:20px;">
                    <p style="font-size:13px;color:#854f0b;margin:0;">Por segurança, altera a tua password no primeiro login.</p>
                </div>
                <p style="font-size:14px;color:#555;line-height:1.6;margin:0;">Se tiveres alguma questão, responde a este email.<br>Bem-vindo à equipa!</p>
            </div>
            <div style="background:#f8f8f8;border-top:1px solid #eee;padding:16px 32px;text-align:center;">
                <p style="font-size:12px;color:#aaa;margin:0;">©  — Plataforma de Gestão</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(user="geral.servicos.info@gmail.com", password="kwth gssy aqla sahz")
            connection.send_message(msg)
        print(f"Email enviado para ")
    except Exception as e:
        print(f"Erro email: {e}")

send_welcome_email()