import secrets
import datetime

from db import get_db_connection
from events import PACIFIC_TIME

def _generate_qrid():
    return secrets.token_hex(8)

def create_qr(event_id, user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT check_in, check_out FROM public.entries WHERE eid = %s AND uid = %s',
                (event_id, user_id)
            )
            row = cur.fetchone()
            if not row:
                ret = {
                    'success': False,
                    'friendly': "You aren't listed as a participant of this event and thus cannot be issued a check in/out code.",
                    'error': 'Unlisted User'
                }
                raise Exception
            if row['check_in'] and row['check_out']:
                ret = {
                    'success': False,
                    'error': 'User Event Complete',
                    'friendly': "You've already been checked in and out of this event, a check in/out code is useless."
                }
                raise Exception
            
            qrid = None
            while not qrid:
                qrid = _generate_qrid()
                cur.execute('SELECT * FROM public.qr WHERE qrid = %s', (qrid, ))
                row = cur.fetchone()
                if row:
                    qrid = None
            cur.execute(
                'INSERT INTO public.qr (qrid, eid, uid, exp) VALUES (%s, %s, %s, %s)',
                (qrid, event_id, user_id, datetime.datetime.now().astimezone(PACIFIC_TIME) + datetime.timedelta(seconds=150))
            )
            conn.commit()
        conn.close()
        return {
            'success': True,
            'qrid': qrid
        }
    except Exception:
        conn.close()
        return ret

