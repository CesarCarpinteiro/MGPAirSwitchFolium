from db import db
from flask_login import UserMixin

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    
    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(30), unique=True)
    senha = db.Column(db.String())