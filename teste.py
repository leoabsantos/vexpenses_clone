import smtplib
from email.mime.text import MIMEText

# Configurações
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 587
SMTP_USERNAME = "ti.astands@yahoo.com.br"  # Substitua pelo seu e-mail
SMTP_PASSWORD = "wevmcekpysqeqqxi"     # Substitua pela senha de aplicativo
TO_EMAIL = "leonardo.santos@astands.com.br"         # Substitua por um e-mail de teste

# Criar mensagem
msg = MIMEText("Este é um e-mail de teste.")
msg['Subject'] = "Teste SMTP Yahoo"
msg['From'] = SMTP_USERNAME
msg['To'] = TO_EMAIL

try:
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.set_debuglevel(1)  # Ativar logs detalhados
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, TO_EMAIL, msg.as_string())
    print("E-mail enviado com sucesso!")
except Exception as e:
    print(f"Erro: {e}")