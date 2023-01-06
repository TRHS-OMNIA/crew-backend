from flask import Flask, request, make_response
from flask_cors import CORS

from auth import gauth_login

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.post('/auth/google')
def google_login():
    body = request.json
    return gauth_login(body['token'])