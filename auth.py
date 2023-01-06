import os
import datetime
import jwt

from db import get_db_connection

from google.oauth2 import id_token
from google.auth.transport import requests

def get_exp_ts():
    return int((datetime.datetime.now() + datetime.timedelta(seconds=60040)).timestamp() * 1000)

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
        token = jwt.encode(payload, os.getenv('JWT_SIGNING_KEY'))
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
        

if __name__ == '__main__':
    print(create_auth_token('dfllanagan'))