from flask import Flask, request, g
from flask_cors import CORS

from auth import gauth_login, authorization_required, admin_only
from events import new_event

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.post('/auth/google')
def google_login():
    body = request.json
    return gauth_login(body['token'])

@app.post('/create')
@authorization_required
@admin_only
def create_event():
    payload = request.json
    try:
        return new_event(payload)
    except Exception:
        return {
            'success': False,
            'error': 'Unknown Error',
            'friendly': 'No idea what went wrong, might be a Google OAuth Delegation token issue...'
        }