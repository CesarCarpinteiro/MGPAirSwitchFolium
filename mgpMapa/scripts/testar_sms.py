"""Envia um SMS de teste com as credenciais Twilio do .env.

Uso (dentro do contentor):
    docker compose exec flask-app python scripts/testar_sms.py 912345678 "Mensagem de teste" [--servico MG...]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

parser = argparse.ArgumentParser(description='Envia um SMS de teste pela Twilio.')
parser.add_argument('numero', help='telemóvel de destino (ex: 912345678 ou +351912345678)')
parser.add_argument('mensagem', help='texto do SMS')
parser.add_argument('--servico', help='Messaging Service SID (MG...); por omissão usa o do .env')
parser.add_argument('--remetente', help='remetente alfanumérico, se não usar Messaging Service')
args = parser.parse_args()

if args.servico:
    os.environ['TWILIO_MESSAGING_SERVICE_SID'] = args.servico

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
import utils  # noqa: E402

print(f'Para: {utils.normalizar_telemovel(args.numero) or args.numero}')
print(f'Via: {"Messaging Service " + utils.TWILIO_MESSAGING_SERVICE_SID if utils.TWILIO_MESSAGING_SERVICE_SID else "remetente " + (args.remetente or utils.TWILIO_SENDER or "GestaoPro")}')
ok, erro = utils.send_sms(args.numero, args.mensagem, remetente=args.remetente)
print('Enviado!' if ok else f'Falhou: {erro}')
sys.exit(0 if ok else 1)
