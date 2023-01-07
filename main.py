from flask import Flask, request, g
from flask_cors import CORS

from auth import gauth_login, authorization_required, admin_only

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
    return {'success': True}