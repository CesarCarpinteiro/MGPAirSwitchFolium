from db import db
from flask_login import UserMixin
from datetime import datetime

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(30), unique=True)
    senha = db.Column(db.String())
    is_admin = db.Column(db.Boolean, default=False)

class Registo(db.Model):
    __tablename__ = 'registos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    contacto = db.Column(db.String(20), nullable=True)
    num_maquinas = db.Column(db.Integer, nullable=True)
    marca = db.Column(db.String(100), nullable=True)
    data_instalacao = db.Column(db.String(20), nullable=True)
    proxima_manutencao = db.Column(db.String(20), nullable=True)
    morada = db.Column(db.String(300), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

class Fatura(db.Model):
    __tablename__ = 'faturas'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    local = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(20), nullable=False)
    nota = db.Column(db.String(500), nullable=True)
    ficheiro = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.String(20), default=lambda: datetime.now().strftime('%d/%m/%Y'))

class Ferias(db.Model):
    __tablename__ = 'ferias'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_inicio = db.Column(db.String(20), nullable=False)
    data_fim = db.Column(db.String(20), nullable=False)
    nota = db.Column(db.String(500), nullable=True)
    estado = db.Column(db.String(20), default='pendente')  # pendente, aprovado, rejeitado
    comentario_admin = db.Column(db.String(500), nullable=True)
    aprovado_por = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.String(20), default=lambda: datetime.now().strftime('%d/%m/%Y'))