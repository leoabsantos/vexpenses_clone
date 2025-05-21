# v0.4.4.4.5

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment
import time
import gspread
from google.oauth2.service_account import Credentials
import schedule
import threading
from threading import Lock
from dateutil import parser
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
# from models import User, Expense, Advance, Event  # Removido porque os modelos já estão definidos abaixo
from sqlalchemy import outerjoin  # Adicionado

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'Uploads')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
    'pool_pre_ping': True
}
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
db_lock = Lock()

# Carregar variáveis de ambiente
env_path = os.path.join(os.path.dirname(__file__), '..\.env')
load_dotenv(env_path)

SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

print(f"SMTP Config: Server={SMTP_SERVER}, Port={SMTP_PORT}, Username={SMTP_USERNAME}")

import asyncio
import threading

# Função para enviar e-mail
async def send_email_async(to_email, subject, body, retries=3, delay=5):
    loop = asyncio.get_event_loop()
    result = {'success': False, 'message': ''}
    for attempt in range(retries):
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = SMTP_USERNAME
            msg['To'] = to_email
            def send_sync():
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                    server.set_debuglevel(1)
                    server.starttls()
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    server.sendmail(SMTP_USERNAME, to_email, msg.as_string())
            await loop.run_in_executor(None, send_sync)
            result['success'] = True
            result['message'] = f"E-mail enviado com sucesso para {to_email}"
            print(result['message'])
            return result
        except Exception as e:
            result['message'] = f"Tentativa {attempt + 1} falhou: {e}"
            print(result['message'])
            if attempt < retries - 1:
                await asyncio.sleep(delay)
    result['message'] = f"Erro ao enviar e-mail para {to_email} após {retries} tentativas"
    return result

def send_email(to_email, subject, body, retries=3, delay=5):
    # Executa a função assíncrona em segundo plano
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(send_email_async(to_email, subject, body, retries, delay))
        loop.close()
        return result
    thread = threading.Thread(target=run_async)
    thread.start()
    return thread

# Configuração do Google Sheets
def get_google_sheets_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('..\credentials.json', scopes=scope)
    return gspread.authorize(creds)

# Sincronizar eventos do Google Sheets
def sync_events():
    with db_lock:
        try:
            client = get_google_sheets_client()
            sheet = client.open_by_key('1dru9w2z2El39rsFzJTsw24yd8uPAs3JcDN01Lvdd_LY').worksheet('ENTRADA')
            events = sheet.get('A2:V')
            db.session.execute(Event.__table__.delete())
            for row in events:
                row = row + [''] * (22 - len(row)) if len(row) < 22 else row[:22]
                event = Event(
                    cadastro=row[2],
                    mes_evento=row[3],
                    nome_evento=row[4],
                    local_evento=row[5],
                    responsavel=row[6],
                    data_evento=row[7],
                    termino_evento=row[8],
                    data_montagem_inicial=row[9],
                    data_desmontagem_final=row[10],
                    horario_montagem_inicial=row[11],
                    horario_montagem_final=row[12],
                    horario_desmontagem_inicial=row[13],
                    horario_desmontagem_final=row[14],
                    data_entrada_expositor=row[15],
                    horario_entrada_expositor=row[16],
                    manual_expositor=row[17],
                    planta_evento=row[18],
                    montagem_basica_inclusa=row[19],
                    observacao=row[20],
                    telefone_local_evento=row[21],
                    last_updated=datetime.now()
                )
                db.session.add(event)
            db.session.commit()
            print("Eventos sincronizados com sucesso")
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao sincronizar eventos: {str(e)}")
            raise

# Agendar sincronização diária às 6h
def run_scheduler():
    schedule.every().day.at("06:00").do(sync_events)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Iniciar sincronização em uma thread separada
threading.Thread(target=run_scheduler, daemon=True).start()

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_manager = db.Column(db.Boolean, default=False)
    approval_limit = db.Column(db.Float, default=0.0)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approval_level = db.Column(db.Integer, default=1)  # 1=Usuário, 2=Gestor, 3=Admin
    groups = db.relationship('GroupMembership', backref='user', lazy=True)
    expenses = db.relationship('Expense', backref='user', lazy=True)
    advances = db.relationship('Advance', backref='user', lazy=True)
    manager = db.relationship('User', remote_side=[id], back_populates='managed_users', foreign_keys=[manager_id])
    managed_users = db.relationship('User', back_populates='manager', foreign_keys=[manager_id])

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    members = db.relationship('GroupMembership', backref='group', lazy=True)
    expenses = db.relationship('Expense', backref='group', lazy=True)

class GroupMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    is_group_manager = db.Column(db.Boolean, default=False)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    advance_id = db.Column(db.Integer, db.ForeignKey('advance.id'))
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    receipt = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pendente')
    splits = db.relationship('ExpenseSplit', backref='expense', lazy=True)

class ExpenseSplit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expense.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)

class Advance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)  # Nova coluna
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pendente')
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    remaining_balance = db.Column(db.Float, nullable=False)
    expenses = db.relationship('Expense', backref='advance', lazy=True)
    history = db.relationship('AdvanceHistory', backref='advance', lazy=True)
    event = db.relationship('Event', backref='advances', lazy=True)  # Nova relação

class AdvanceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    advance_id = db.Column(db.Integer, db.ForeignKey('advance.id'), nullable=False)
    expense_id = db.Column(db.Integer, db.ForeignKey('expense.id'))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cadastro = db.Column(db.String(100))
    mes_evento = db.Column(db.String(50))
    nome_evento = db.Column(db.String(100))
    local_evento = db.Column(db.String(100))
    responsavel = db.Column(db.String(100))
    data_evento = db.Column(db.String(50))
    termino_evento = db.Column(db.String(50))
    data_montagem_inicial = db.Column(db.String(50))
    data_desmontagem_final = db.Column(db.String(50))
    horario_montagem_inicial = db.Column(db.String(50))
    horario_montagem_final = db.Column(db.String(50))
    horario_desmontagem_inicial = db.Column(db.String(50))
    horario_desmontagem_final = db.Column(db.String(50))
    data_entrada_expositor = db.Column(db.String(50))
    horario_entrada_expositor = db.Column(db.String(50))
    manual_expositor = db.Column(db.String(200))
    planta_evento = db.Column(db.String(200))
    montagem_basica_inclusa = db.Column(db.String(50))
    observacao = db.Column(db.Text)
    telefone_local_evento = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    expenses = db.relationship('Expense', backref='event', lazy=True)

class FinancialSettlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    advance_id = db.Column(db.Integer, db.ForeignKey('advance.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    used_amount = db.Column(db.Float, nullable=False, default=0.0)
    balance = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='OPEN')  # OPEN, CLOSED
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    advance = db.relationship('Advance', backref='settlements', lazy=True)
    user = db.relationship('User', backref='settlements', lazy=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rotas
@app.route('/')
@login_required
def index():
    if current_user.approval_level == 3:  # Admin
        expenses_query = db.session.query(Expense, User.username, Event.nome_evento)\
            .join(User, Expense.user_id == User.id)\
            .outerjoin(Advance, Expense.advance_id == Advance.id)\
            .outerjoin(Event, Advance.event_id == Event.id)
        advances_query = db.session.query(Advance, User.username, Event.nome_evento)\
            .join(User, Advance.user_id == User.id)\
            .outerjoin(Event, Advance.event_id == Event.id)
        pending_approvals = Expense.query.filter_by(status='pendente').all()
        pending_advance_approvals_query = db.session.query(Advance, User.username, Event.nome_evento)\
            .join(User, Advance.user_id == User.id)\
            .outerjoin(Event, Advance.event_id == Event.id)\
            .filter(Advance.status == 'pendente')
    elif current_user.approval_level == 2:  # Gerente
        managed_user_ids = [u.id for u in current_user.managed_users]
        managed_user_ids.append(current_user.id)
        expenses_query = db.session.query(Expense, User.username, Event.nome_evento)\
            .join(User, Expense.user_id == User.id)\
            .outerjoin(Advance, Expense.advance_id == Advance.id)\
            .outerjoin(Event, Advance.event_id == Event.id)\
            .filter(Expense.user_id.in_(managed_user_ids))
        advances_query = db.session.query(Advance, User.username, Event.nome_evento)\
            .join(User, Advance.user_id == User.id)\
            .outerjoin(Event, Advance.event_id == Event.id)\
            .filter(Advance.user_id.in_(managed_user_ids))
        pending_approvals = Expense.query.filter_by(status='pendente').filter(Expense.user_id.in_(managed_user_ids)).all()
        pending_advance_approvals_query = db.session.query(Advance, User.username, Event.nome_evento)\
            .join(User, Advance.user_id == User.id)\
            .outerjoin(Event, Advance.event_id == Event.id)\
            .filter(Advance.status == 'pendente', Advance.user_id.in_(managed_user_ids))
    else:  # Usuário comum
        expenses_query = db.session.query(Expense, User.username, Event.nome_evento)\
            .join(User, Expense.user_id == User.id)\
            .outerjoin(Advance, Expense.advance_id == Advance.id)\
            .outerjoin(Event, Advance.event_id == Event.id)\
            .filter(Expense.user_id == current_user.id)
        advances_query = db.session.query(Advance, User.username, Event.nome_evento)\
            .join(User, Advance.user_id == User.id)\
            .outerjoin(Event, Advance.event_id == Event.id)\
            .filter(Advance.user_id == current_user.id)
        pending_approvals = []
        pending_advance_approvals_query = db.session.query(Advance, User.username, Event.nome_evento)\
            .join(User, Advance.user_id == User.id)\
            .outerjoin(Event, Advance.event_id == Event.id)\
            .filter(Advance.status == 'pendente', Advance.user_id == current_user.id)

    expenses = expenses_query.order_by(Expense.date.desc()).limit(10).all()
    advances = advances_query.order_by(Advance.date.desc()).limit(10).all()
    pending_advance_approvals = pending_advance_approvals_query.order_by(Advance.date.desc()).limit(10).all()
    groups = Group.query.join(GroupMembership).filter(GroupMembership.user_id == current_user.id).all()
    total_expenses = sum(expense[0].amount for expense in expenses)
    pending_count = len([e for e in pending_approvals if e.status == 'pendente'])
    total_advance_balance = sum(advance[0].remaining_balance for advance in advances if advance[0].status == 'aprovado')

    # Buscar último evento do usuário
    last_event = db.session.query(Event.nome_evento)\
        .join(Advance, Event.id == Advance.event_id)\
        .join(Expense, Advance.id == Expense.advance_id)\
        .filter(Expense.user_id == current_user.id)\
        .order_by(Expense.date.desc())\
        .first()
    last_event = last_event.nome_evento if last_event else ''

    return render_template('index.html', expenses=expenses, groups=groups, pending_approvals=pending_approvals,
                         total_expenses=total_expenses, pending_count=pending_count, advances=advances,
                         total_advance_balance=total_advance_balance, pending_advance_approvals=pending_advance_approvals,
                         last_event=last_event)

@app.route('/dashboard_new')
@login_required
def dashboard_new():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    groups = Group.query.join(GroupMembership).filter(GroupMembership.user_id == current_user.id).all()
    pending_approvals = Expense.query.filter_by(status='pendente').all() if current_user.is_manager else []
    advances = Advance.query.filter_by(user_id=current_user.id).all()
    pending_advance_approvals = Advance.query.filter_by(status='pendente').all() if current_user.is_manager else []
    total_expenses = sum(expense.amount for expense in expenses)
    pending_count = len([e for e in expenses if e.status == 'pendente'])
    total_advance_balance = sum(advance.remaining_balance for advance in advances if advance.status == 'aprovado')
    return render_template('index_new.html', expenses=expenses, groups=groups, pending_approvals=pending_approvals,
                         total_expenses=total_expenses, pending_count=pending_count, advances=advances,
                         total_advance_balance=total_advance_balance, pending_advance_approvals=pending_advance_approvals)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        is_manager = 'is_manager' in request.form
        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            flash('E-mail inválido')
            return render_template('signup.html')
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe')
        elif User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado')
        else:
            with db_lock:
                user = User(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password),
                    is_manager=is_manager,
                    approval_limit=0.0,
                    approval_level=2 if is_manager else 1
                )
                db.session.add(user)
                db.session.commit()
            flash('Cadastro realizado com sucesso!')
            return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.approval_level != 3:
        flash('Apenas administradores podem editar perfis de usuários')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        approval_limit = float(request.form.get('approval_limit', 0.0))
        with db_lock:
            user.approval_limit = approval_limit
            db.session.commit()
        flash(f'Limite de aprovação de {user.username} atualizado para R${approval_limit}')
        return redirect(url_for('index'))
    return render_template('edit_user.html', user=user)

@app.route('/manage_approvals', methods=['GET', 'POST'])
@login_required
def manage_approvals():
    if current_user.approval_level != 3:
        flash('Apenas administradores podem gerenciar aprovações')
        return redirect(url_for('index'))
    users = User.query.all()
    if request.method == 'POST':
        with db_lock:
            try:
                user_id = int(request.form.get('user_id'))
                user = User.query.get_or_404(user_id)
                manager_id = request.form.get('manager_id')
                approval_level = int(request.form.get('approval_level'))
                approval_limit = float(request.form.get('approval_limit', 0.0))
                user.manager_id = None if not manager_id or manager_id == 'None' else int(manager_id)
                user.approval_level = approval_level
                user.approval_limit = approval_limit
                user.is_manager = approval_level >= 2
                db.session.commit()
                flash(f'Configurações de aprovação de {user.username} atualizadas!')
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao atualizar configurações: {str(e)}')
        return redirect(url_for('manage_approvals'))
    return render_template('manage_approvals.html', users=users)

@app.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    if not current_user.is_manager:
        flash('Apenas gestores podem gerenciar Departamentos')
        return redirect(url_for('index'))
    groups = Group.query.all()
    print(f"Listando {len(groups)} Departamentos para o usuário {current_user.username}")
    if request.method == 'POST':
        name = request.form['name']
        with db_lock:
            try:
                group = Group(name=name, creator_id=current_user.id)
                db.session.add(group)
                db.session.commit()
                membership = GroupMembership(
                    user_id=current_user.id,
                    group_id=group.id,
                    is_group_manager=True
                )
                db.session.add(membership)
                db.session.commit()
                flash('Departamento criado com sucesso!')
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao criar Departamento: {str(e)}")
                flash(f'Erro ao criar Departamento: {str(e)}')
        return redirect(url_for('create_group'))
    return render_template('create_group.html', groups=groups)

@app.route('/manage_group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def manage_group(group_id):
    if not current_user.is_manager:
        flash('Apenas gestores podem gerenciar Departamentos')
        return redirect(url_for('index'))
    group = Group.query.get_or_404(group_id)
    members = GroupMembership.query.filter_by(group_id=group_id).all()
    users = User.query.all()
    print(f"Gerenciando Departamento {group.name} (ID: {group_id}) com {len(members)} membros")
    if request.method == 'POST':
        action = request.form.get('action')
        with db_lock:
            try:
                if action == 'add':
                    username = request.form.get('username')
                    user = User.query.filter_by(username=username).first()
                    if user:
                        if GroupMembership.query.filter_by(user_id=user.id, group_id=group_id).first():
                            flash('Usuário já é membro do Departamento')
                        else:
                            membership = GroupMembership(user_id=user.id, group_id=group_id, is_group_manager=False)
                            db.session.add(membership)
                            db.session.commit()
                            flash(f'Usuário {username} adicionado ao Departamento!')
                            group_managers = GroupMembership.query.filter_by(group_id=group_id, is_group_manager=True).all()
                            for manager in group_managers:
                                send_email(
                                    manager.user.email,
                                    f'1_Departamento_Novo membro no Departamento {group.name}',
                                    f'1_Departamento_O usuário {username} foi adicionado ao Departamento {group.name} por {current_user.username}.'
                                )
                    else:
                        flash('Usuário não encontrado')
                elif action == 'remove':
                    member_id = int(request.form.get('member_id'))
                    membership = GroupMembership.query.filter_by(user_id=member_id, group_id=group_id).first()
                    if membership:
                        if membership.user_id == current_user.id:
                            flash('Você não pode se remover do Departamento')
                        else:
                            db.session.delete(membership)
                            db.session.commit()
                            flash(f'Usuário {membership.user.username} removido do Departamento!')
                            group_managers = GroupMembership.query.filter_by(group_id=group_id, is_group_manager=True).all()
                            for manager in group_managers:
                                send_email(
                                    manager.user.email,
                                    f'2_Departamento_Membro removido do Departamento {group.name}',
                                    f'2_Departamento_O usuário {membership.user.username} foi removido do Departamento {group.name} por {current_user.username}.'
                                )
                    else:
                        flash('Membro não encontrado')
                elif action == 'toggle_manager':
                    member_id = int(request.form.get('member_id'))
                    membership = GroupMembership.query.filter_by(user_id=member_id, group_id=group_id).first()
                    if membership:
                        membership.is_group_manager = not membership.is_group_manager
                        db.session.commit()
                        status = 'gestor' if membership.is_group_manager else 'membro comum'
                        flash(f'Usuário {membership.user.username} agora é {status} do Departamento!')
                        send_email(
                            membership.user.email,
                            f'3_Departamento_Status atualizado no Departamento {group.name}',
                            f'3_Departamento_Você agora é {status} do Departamento {group.name}, atualizado por {current_user.username}.'
                        )
                        group_managers = GroupMembership.query.filter_by(group_id=group_id, is_group_manager=True).all()
                        for manager in group_managers:
                            if manager.user_id != membership.user_id:
                                send_email(
                                    manager.user.email,
                                    f'4_Departamento_Status de membro atualizado no Departamento {group.name}',
                                    f'4_Departamento_O usuário {membership.user.username} agora é {status} do Departamento {group.name}, atualizado por {current_user.username}.'
                                )
                    else:
                        flash('Membro não encontrado')
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao processar ação no Departamento {group_id}: {str(e)}")
                flash(f'Erro ao processar a ação: {str(e)}')
    return render_template('manage_group.html', group=group, members=members, users=users)

@app.route('/group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def group(group_id):
    group = Group.query.get_or_404(group_id)
    membership = GroupMembership.query.filter_by(user_id=current_user.id, group_id=group_id).first()
    if not membership:
        flash('Você não é membro deste Departamento')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        if user:
            if GroupMembership.query.filter_by(user_id=user.id, group_id=group_id).first():
                flash('Usuário já é membro')
            else:
                with db_lock:
                    membership = GroupMembership(user_id=user.id, group_id=group_id, is_group_manager=False)
                    db.session.add(membership)
                    db.session.commit()
                flash('Membro adicionado com sucesso!')
                group_managers = GroupMembership.query.filter_by(group_id=group_id, is_group_manager=True).all()
                for manager in group_managers:
                    send_email(
                        manager.user.email,
                        f'5_Departamento_Novo membro no Departamento {group.name}',
                        f'5_Departamento_O usuário {username} foi adicionado ao Departamento {group.name} por {current_user.username}.'
                    )
        else:
            flash('Usuário não encontrado')
    members = GroupMembership.query.filter_by(group_id=group_id).all()
    expenses = Expense.query.filter_by(group_id=group_id).all()
    return render_template('group.html', group=group, members=members, expenses=expenses)

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    categories = ["Alimentação", "Transporte", "Hospedagem", "Pedágio", "Compras Diversas", "Combustível", "Serviços Terceiros", "Outros"]
    groups = Group.query.join(GroupMembership).filter(GroupMembership.user_id == current_user.id).all()
    advances = Advance.query.filter_by(user_id=current_user.id, status='aprovado').all()
    events = Event.query.all()
    selected_event = request.args.get('event', '')
    total_advance_balance = sum(advance.remaining_balance for advance in advances)
    email_status = []

    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form['description']
        category = request.form['category']
        group_id = request.form.get('group_id')
        event_name = request.form.get('event')
        receipt = request.files.get('receipt')
        receipt_path = None
        if receipt:
            filename = secure_filename(receipt.filename)
            receipt_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            receipt.save(receipt_path)
            receipt_path = os.path.join('Uploads', filename).replace('\\', '/')
        advance_id = None
        if total_advance_balance >= amount:
            for advance in advances:
                if advance.remaining_balance >= amount:
                    advance_id = advance.id
                    advance.remaining_balance -= amount
                    history = AdvanceHistory(advance_id=advance.id, expense_id=None, amount=amount)
                    db.session.add(history)
                    break
        event_id = None
        if event_name:
            event = Event.query.filter_by(nome_evento=event_name).first()
            if event:
                advance = Advance.query.filter_by(event_id=event.id, user_id=current_user.id, status='aprovado').first()
                advance_id = advance.id if advance else advance_id
                event_id = event.id
        status = 'aprovado' if amount <= current_user.approval_limit else 'pendente'
        with db_lock:
            expense = Expense(
                user_id=current_user.id,
                group_id=group_id if group_id else None,
                advance_id=advance_id,
                event_id=event_id,
                amount=amount,
                description=description,
                category=category,
                receipt=receipt_path,
                status=status
            )
            db.session.add(expense)
            db.session.commit()
            if advance_id:
                history.expense_id = expense.id
                # Criar ou atualizar acerto financeiro
                settlement = FinancialSettlement.query.filter_by(advance_id=advance_id, status='OPEN').first()
                if not settlement:
                    settlement = FinancialSettlement(
                        advance_id=advance_id,
                        user_id=current_user.id,
                        total_amount=Advance.query.get(advance_id).amount,
                        used_amount=amount,
                        balance=Advance.query.get(advance_id).remaining_balance,
                        status='OPEN'
                    )
                    db.session.add(settlement)
                else:
                    settlement.used_amount += amount
                    settlement.balance = Advance.query.get(advance_id).remaining_balance
                db.session.commit()
                # Enviar e-mail para o RH
                rh_email = os.getenv('RH_EMAIL', 'ti@astands.com.br')
                email_result = send_email(
                    rh_email,
                    '6_Add_expense_Despesa abatida de antecipação',
                    f'6_Add_expense_Uma despesa de R${amount} ({description}) foi abatida da antecipação de {current_user.username}. Saldo restante: R${advance.remaining_balance}'
                )
                email_status.append({'recipient': rh_email, 'status': 'queued', 'message': 'E-mail para o RH enviado em segundo plano'})
            if group_id:
                members = GroupMembership.query.filter_by(group_id=group_id).all()
                split_amount = amount / len(members)
                for member in members:
                    split = ExpenseSplit(expense_id=expense.id, user_id=member.user_id, amount=split_amount)
                    db.session.add(split)
                db.session.commit()
            if status == 'pendente' and current_user.manager:
                # Enviar e-mail para o gestor
                group_name = Group.query.get(group_id).name if group_id else 'Nenhum'
                email_result = send_email(
                    current_user.manager.email,
                    '7_Add_expense_Nova despesa pendente de aprovação',
                    f'7_Add_expense_Uma despesa de R${amount} foi submetida por {current_user.username} no Departamento {group_name}: {description}'
                )
                email_status.append({'recipient': current_user.manager.email, 'status': 'queued', 'message': 'E-mail para o gestor enviado em segundo plano'})
            db.session.commit()
        flash(f'Despesa adicionada com sucesso! Status: {status}')
        # return jsonify({'message': 'Despesa adicionada com sucesso!', 'email_status': email_status})
    return render_template('add_expense.html', groups=groups, categories=categories, events=events, total_advance_balance=total_advance_balance, selected_event=selected_event)

@app.route('/advance_request', methods=['GET', 'POST'])
@login_required
def advance_request():
    # Carregar eventos recentes (último mês)
    current_date = datetime.now()
    min_date = current_date - relativedelta(months=1)
    events = Event.query.filter(
        Event.nome_evento.isnot(None),
        Event.mes_evento.isnot(None)
    ).all()
    filtered_events = []
    for event in events:
        try:
            event_date = parser.parse(event.mes_evento, fuzzy=True)
            if event_date >= min_date:
                filtered_events.append(event)
        except ValueError:
            continue

    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form['description']
        event_id = request.form.get('event_id')  # Novo campo
        with db_lock:
            advance = Advance(
                user_id=current_user.id,
                event_id=event_id if event_id else None,
                amount=amount,
                description=description,
                remaining_balance=0
            )
            db.session.add(advance)
            db.session.commit()
        # Enviar e-mails com nome do evento, se selecionado
        event_name = Event.query.get(event_id).nome_evento if event_id else 'Nenhum evento'
        if current_user.manager:
            send_email(
                current_user.manager.email,
                f'8_Advance_request_Nova solicitação de antecipação',
                f'8_Advance_request_ {current_user.username} solicitou uma antecipação de R${amount} para o evento "{event_name}": {description}'
            )
        admins = User.query.filter_by(approval_level=3).all()
        for admin in admins:
            send_email(
                admin.email,
                f'9_Advance_request_Nova solicitação de antecipação',
                f'9_Advance_request_{current_user.username} solicitou uma antecipação de R${amount} para o evento "{event_name}": {description}'
            )
        flash('Solicitação de antecipação enviada com sucesso!')
        return redirect(url_for('index'))
    return render_template('advance_request.html', events=filtered_events)

@app.route('/approve_advance/<int:advance_id>/<action>', methods=['POST'])
@login_required
def approve_advance(advance_id, action):
    if current_user.approval_level < 2:
        flash('Apenas gestores podem aprovar antecipações')
        return redirect(url_for('index'))
    advance = Advance.query.get_or_404(advance_id)
    with db_lock:
        if action == 'approve':
            advance.status = 'aprovado'
            advance.remaining_balance = advance.amount
            # Enviar e-mail para o RH
            rh_email = os.getenv('RH_EMAIL', 'rh@empresa.com')  # Configurar no .env
            send_email(
                rh_email,
                f'10_Aproved_Antecipação autorizada',
                f'10_Aproved_A antecipação de R${advance.amount} para {advance.user.username} ({advance.description}) foi aprovada por {current_user.username}.'
            )
            flash('E-mail para o RH enviado em segundo plano')
            flash('Antecipação aprovada com sucesso!')
        elif action == 'reject':
            advance.status = 'rejeitado'
            flash('Antecipação rejeitada')
        db.session.commit()
    send_email(
        advance.user.email,
        f'11_Aproved_Solicitação de antecipação {advance.status}',
        f'11_Aproved_Sua solicitação de antecipação de R${advance.amount} ({advance.description}) foi {advance.status} por {current_user.username}.'
    )
    flash('E-mail para o usuário enviado em segundo plano')
    return redirect(url_for('index'))

@app.route('/approve_expense/<int:expense_id>/<action>', methods=['POST'])
@login_required
def approve_expense(expense_id, action):
    expense = Expense.query.get_or_404(expense_id)
    if current_user.approval_level < 2 or (current_user.approval_limit < expense.amount and current_user.approval_level != 3):
        flash('Você não tem permissão para aprovar esta despesa')
        return redirect(url_for('index'))
    with db_lock:
        if action == 'approve':
            expense.status = 'aprovado'
            flash('Despesa aprovada com sucesso!')
        elif action == 'reject':
            expense.status = 'rejeitado'
            flash('Despesa rejeitada')
        db.session.commit()
    send_email(
        expense.user.email,
        f'12_Aproved_Ex_Despesa {expense.status}',
        f'12_Aproved_Ex_Sua despesa "{expense.description}" de R${expense.amount} foi {expense.status} por {current_user.username}.'
    )
    return redirect(url_for('index'))

@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    categories = ["Alimentação", "Transporte", "Hospedagem", "Pedágio", "Compras Diversas", "Combustível", "Serviços Terceiros", "Outros"]
    groups = Group.query.join(GroupMembership).filter(GroupMembership.user_id == current_user.id).all()
    if current_user.approval_level == 3:
        expenses = Expense.query.all()
    elif current_user.approval_level == 2:
        managed_user_ids = [u.id for u in current_user.managed_users]
        managed_user_ids.append(current_user.id)
        expenses = Expense.query.filter(Expense.user_id.in_(managed_user_ids)).all()
    else:
        expenses = Expense.query.filter_by(user_id=current_user.id).all()
    filtered_expenses = expenses
    chart_data = {'labels': [], 'data': []}
    if request.method == 'POST':
        category = request.form.get('category')
        group_id = request.form.get('group_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        export_excel = 'export_excel' in request.form
        query = Expense.query
        if current_user.approval_level == 2:
            managed_user_ids = [u.id for u in current_user.managed_users]
            managed_user_ids.append(current_user.id)
            query = query.filter(Expense.user_id.in_(managed_user_ids))
        elif current_user.approval_level == 1:
            query = query.filter_by(user_id=current_user.id)
        if category:
            query = query.filter_by(category=category)
        if group_id:
            query = query.filter_by(group_id=group_id)
        if start_date:
            query = query.filter(Expense.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(Expense.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        filtered_expenses = query.all()
        category_totals = {}
        for expense in filtered_expenses:
            category_totals[expense.category] = category_totals.get(expense.category, 0) + expense.amount
        chart_data['labels'] = list(category_totals.keys())
        chart_data['data'] = list(category_totals.values())
        if export_excel:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Relatório de Despesas"
            headers = ['Data', 'Descrição', 'Categoria', 'Departamento', 'Evento', 'Valor', 'Status', 'Antecipação', 'Comprovante']
            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')
            for expense in filtered_expenses:
                event_name = expense.event.nome_evento if expense.event else 'Nenhum'
                ws.append([
                    expense.date.strftime('%Y-%m-%d'),
                    expense.description,
                    expense.category,
                    expense.group.name if expense.group else 'Nenhum',
                    event_name,
                    expense.amount,
                    expense.status,
                    expense.advance.description if expense.advance else 'Nenhuma',
                    expense.receipt if expense.receipt else 'Nenhum'
                ])
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                ws.column_dimensions[column].width = adjusted_width
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            return send_file(
                output,
                download_name='relatorio_despesas.xlsx',
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
    return render_template('report.html', expenses=filtered_expenses, categories=categories, groups=groups, chart_data=chart_data)

@app.route('/financial_settlement', methods=['GET'])
@login_required
def financial_settlement():
    user_email = request.args.get('user_email')
    date = request.args.get('date')
    event_name = request.args.get('event_name')
    
    query = FinancialSettlement.query.join(Advance).join(User)
    if current_user.approval_level != 3:
        query = query.filter(FinancialSettlement.user_id == current_user.id)
    if user_email:
        query = query.filter(User.email.ilike(f'%{user_email}%'))
    if date:
        query = query.filter(FinancialSettlement.created_at >= datetime.strptime(date, '%Y-%m-%d'))
    if event_name:
        query = query.join(Event, Advance.event_id == Event.id).filter(Event.nome_evento.ilike(f'%{event_name}%'))
    
    settlements = query.all()
    return render_template('financial_settlement.html', settlements=settlements)

@app.route('/financial_settlement/<int:settlement_id>/close', methods=['POST'])
@login_required
def close_settlement(settlement_id):
    if current_user.approval_level != 3:
        flash('Apenas administradores podem fechar acertos')
        return jsonify({'error': 'Acesso negado'}), 403
    settlement = FinancialSettlement.query.get_or_404(settlement_id)
    if settlement.status != 'OPEN':
        flash('Acerto já fechado')
        return jsonify({'error': 'Acerto já fechado'}), 400
    with db_lock:
        settlement.status = 'CLOSED'
        settlement.balance = 0.0
        advance = Advance.query.get(settlement.advance_id)
        advance.remaining_balance = 0.0
        db.session.commit()
    rh_email = os.getenv('RH_EMAIL', 'ti@astands.com.br')
    email_result = send_email(
        rh_email,
        f'13_Close_settlement_Acerto financeiro fechado',
        f'13_Close_settlement_O acerto financeiro para a antecipação de R${settlement.total_amount} de {settlement.user.username} foi fechado por {current_user.username}.'
    )
    flash('Acerto fechado com sucesso!')
    return jsonify({
        'message': 'Acerto fechado com sucesso!',
        'email_status': [{'recipient': rh_email, 'status': 'queued', 'message': 'E-mail para o RH enviado em segundo plano'}]
    })

@app.route('/financial_settlement/<int:settlement_id>/refund', methods=['POST'])
@login_required
def refund_settlement(settlement_id):
    if current_user.approval_level != 3:
        flash('Apenas administradores podem registrar devoluções')
        return jsonify({'error': 'Acesso negado'}), 403
    settlement = FinancialSettlement.query.get_or_404(settlement_id)
    if settlement.status != 'OPEN':
        flash('Acerto já fechado')
        return jsonify({'error': 'Acerto já fechado'}), 400
    refund_amount = float(request.form.get('refund_amount'))
    if refund_amount <= 0 or refund_amount > settlement.balance:
        flash('Valor de devolução inválido')
        return jsonify({'error': 'Valor de devolução inválido'}), 400
    with db_lock:
        settlement.balance -= refund_amount
        settlement.used_amount += refund_amount
        advance = Advance.query.get(settlement.advance_id)
        advance.remaining_balance -= refund_amount
        db.session.commit()
    rh_email = os.getenv('RH_EMAIL', 'ti@astands.com.br')
    email_result = send_email(
        rh_email,
        f'14_Refund_settlement_Devolução registrada',
        f'14_Refund_settlement_Uma devolução de R${refund_amount} foi registrada no acerto financeiro de {settlement.user.username} por {current_user.username}. Saldo restante: R${settlement.balance}.'
    )
    flash('Devolução registrada com sucesso!')
    return jsonify({
        'message': 'Devolução registrada com sucesso!',
        'email_status': [{'recipient': rh_email, 'status': 'queued', 'message': 'E-mail para o RH enviado em segundo plano'}]
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        db.metadata.create_all(bind=db.engine, tables=[FinancialSettlement.__table__])
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('Astands@Adm'),
                is_manager=True,
                approval_limit=1000.0,
                approval_level=3
            )
            db.session.add(admin)
            db.session.commit()
            print("Administrador padrão criado: login=admin, senha=Astands@Adm")
        sync_events()
    app.run(debug=False, host='0.0.0.0', port=5000)
    #admin:Astands@Adm user:user user1:user1 user2:user2