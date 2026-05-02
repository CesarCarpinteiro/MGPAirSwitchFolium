from db import db
from flask_login import UserMixin
from datetime import datetime

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(30), unique=True)
    senha = db.Column(db.String())
    is_admin = db.Column(db.Boolean, default=False)
    email = db.Column(db.String(120))
    telefone = db.Column(db.String(30))
    nome_completo = db.Column(db.String(200))
    cargo = db.Column(db.String(100))
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)

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
    tipo_servico = db.Column(db.String(100), nullable=True)
    morada = db.Column(db.String(300), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    valor_pago = db.Column(db.Float, nullable=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)
    servicos = db.relationship('Servico', backref='registo', lazy=True, cascade='all, delete-orphan')

class Servico(db.Model):
    __tablename__ = 'servicos'
    id = db.Column(db.Integer, primary_key=True)
    registo_id = db.Column(db.Integer, db.ForeignKey('registos.id'), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)
    tipo_servico = db.Column(db.String(100), nullable=True)
    data_servico = db.Column(db.String(20), nullable=True)
    proxima_manutencao = db.Column(db.String(20), nullable=True)
    num_maquinas = db.Column(db.Integer, nullable=True)
    marca = db.Column(db.String(100), nullable=True)
    valor_pago = db.Column(db.Float, nullable=True)
    notas = db.Column(db.String(500), nullable=True)
    duracao_horas = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.String(20), default=lambda: datetime.now().strftime('%d/%m/%Y'))

class TipoServico(db.Model):
    __tablename__ = 'tipos_servico'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)

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
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)

class Ferias(db.Model):
    __tablename__ = 'ferias'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_inicio = db.Column(db.String(20), nullable=False)
    data_fim = db.Column(db.String(20), nullable=False)
    nota = db.Column(db.String(300), default='')
    estado = db.Column(db.String(20), default='pendente')
    comentario_admin = db.Column(db.String(300), default='')
    aprovado_por = db.Column(db.String(100), default='')
    num_dias = db.Column(db.Integer, default=0)
    created_at = db.Column(db.String(20), default=lambda: datetime.now().strftime('%d/%m/%Y'))
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)

class Mensagem(db.Model):
    __tablename__ = 'mensagens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    destinatario = db.Column(db.String(50), nullable=False)
    contacto = db.Column(db.String(20), nullable=False)
    mensagem = db.Column(db.String(1000), nullable=False)
    estado = db.Column(db.String(20), default='enviado')
    created_at = db.Column(db.String(30), default=lambda: datetime.now().strftime('%d/%m/%Y %H:%M'))
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)

class HorasTrabalhadas(db.Model):
    __tablename__ = 'horastrabalhadas'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    user_nome = db.Column(db.String(100), nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    dia = db.Column(db.Integer, nullable=False)
    manha = db.Column(db.Float, default=0)
    tarde = db.Column(db.Float, default=0)
    extra = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    observacoes = db.Column(db.String(300), default='')
    local = db.Column(db.String(200), default='')
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)

class Orcamento(db.Model):
    __tablename__ = 'orcamentos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    cliente = db.Column(db.String(200))
    descricao = db.Column(db.String(500))
    num_maquinas = db.Column(db.Integer)
    valor = db.Column(db.Float)
    estado = db.Column(db.String(50), default='Pendente')
    created_at = db.Column(db.String(20))
    org_id = db.Column(db.Integer, db.ForeignKey('organizacao.id'), nullable=True)

class Organizacao(db.Model):
    __tablename__ = 'organizacao'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200))
    pais = db.Column(db.String(10))
    telefone = db.Column(db.String(30))
    created_at = db.Column(db.String(20), default=lambda: datetime.now().strftime('%d/%m/%Y'))