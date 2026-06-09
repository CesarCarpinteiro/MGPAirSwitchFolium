from app import create_app
from db import db

app = create_app()


def init_db():
    with app.app_context():
        db.create_all()

        # Idempotent schema patches for existing DBs
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE organizacao ADD COLUMN tipo_negocio VARCHAR(20) DEFAULT 'cliente'"))
                conn.commit()
        except Exception:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE servicos ADD COLUMN duracao_horas FLOAT'))
                conn.commit()
        except Exception:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('CREATE TABLE IF NOT EXISTS config_ferias_ano (id INTEGER PRIMARY KEY, org_id INTEGER, ano INTEGER, dias INTEGER DEFAULT 22)'))
                conn.commit()
        except Exception:
            pass

        # Migrate registos without service records
        try:
            from models import Registo, Servico
            registos_sem_servico = db.session.query(Registo).filter(~Registo.servicos.any()).all()
            for r in registos_sem_servico:
                if r.data_instalacao or r.tipo_servico:
                    s = Servico(
                        registo_id=r.id, org_id=r.org_id,
                        tipo_servico=r.tipo_servico or 'Instalação AC',
                        data_servico=r.data_instalacao,
                        proxima_manutencao=r.proxima_manutencao,
                        num_maquinas=r.num_maquinas, marca=r.marca, valor_pago=r.valor_pago
                    )
                    db.session.add(s)
            db.session.commit()
        except Exception as e:
            print(f'Migração: {e}')
            db.session.rollback()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=3000, debug=True)