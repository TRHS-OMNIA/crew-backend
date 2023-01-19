import os
import datetime
import jwt

from functools import wraps
from flask import g, request

from db import get_db_connection

from google.oauth2 import id_token
from google.auth.transport import requests

def get_exp_ts():
    return int((datetime.datetime.now() + datetime.timedelta(seconds=302400)).timestamp() * 1000)

def gauth_login(token):
    try:
        user_info = id_token.verify_oauth2_token(token, requests.Request(), os.getenv('G_OAUTH_WEB_CLIENT_ID'))
        uid = user_info['email'].split('@')[0]
        return create_auth_token(uid)
    except Exception as e:
        print(e)
        return {
            'success': False,
            'error': 'Authentication Failure',
            'friendly': 'Google failed to verify your identity.  Try again in a few moments.'
        }

def create_auth_token(uid):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM public.users WHERE id = %s', (uid, ))
        row = cur.fetchone()
    conn.close()
    if row:
        payload = row
        if payload['grade'] == 0:
            payload['admin'] = True
        else:
            payload['admin'] = False
        if payload['nickname']:
            payload['display_name'] = payload['nickname'] + ' ' + payload['last_name']
        else:
            payload['display_name'] = payload['first_name'] + ' ' + payload['last_name']
        payload['exp'] = get_exp_ts()
        token = jwt.encode(payload, os.getenv('JWT_SIGNING_KEY'), 'HS256')
        return {
            'success': True,
            'payload': payload,
            'token': token
        }
    else:
        return {
            'success': False,
            'error': 'Unauthroized User',
            'friendly': 'The credentials used to login are not authorized to use this application.  If you should be able to access this application, ask your teacher to grant permission.'
        }

def validate_auth_token(token):
    return jwt.decode(token, os.getenv('JWT_SIGNING_KEY'), 'HS256')

def authorization_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not request.headers["authorization"]:
            return {
                'success': False,
                'error': 'Identity Unknown',
                'friendly': 'The server could not identify who you are and whether this action is authorized, try refreshing the page and signing in if required.'
            }
        
        try:
            g.user = validate_auth_token(request.headers["authorization"])
        except jwt.ExpiredSignatureError:
            return{
                'success': False,
                'error': 'Expired Session',
                'friendly': 'The credentials used to authroize this request have expired, refresh the page, sign in, and try again.'
            }
        except jwt.InvalidSignatureError:
            return {
                'success': False,
                'error': 'Tampered Token',
                'friendly': 'The credentials used to authorize this request have been tampered with and are no longer valid. Do not try to hack the matrix, it will not be tolerated.'
            }
        except Exception:
            return {
                'success': False,
                'error': 'Unknown Error',
                'friendly': 'The server failed to identify who you are and whether this action is authorized, try refreshing the page and signing in if required.'
            }
        return f(*args, **kwargs)
    return wrap

def admin_only(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not g.user['admin']:
            return {
                'success': False,
                'error': 'Admin Only',
                'friendly': 'You are not authorized to take this action.'
            }
        return f(*args, **kwargs)
    return wrap

def inject_user(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        try:
            g.user = validate_auth_token(request.headers["authorization"])
        except Exception:
            g.user = None
        return f(*args, **kwargs)
    return wrap

if __name__ == '__main__':
    print(create_auth_token('dfllanagan'))