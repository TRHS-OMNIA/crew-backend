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

def get_data_from_qrid(qrid):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT * FROM public.qr JOIN public.entries ON public.qr.eid = public.entries.eid AND public.qr.uid = public.entries.uid JOIN public.users ON public.qr.uid = id JOIN public.events ON public.entries.eid = public.events.id WHERE qrid = %s',
            (qrid, )
        )
        data = cur.fetchone()
        if data:
            cur.execute(
                'UPDATE public.qr SET scanned = %s WHERE qrid = %s',
                (True, qrid)
            )
            conn.commit()
    conn.close()
    if data:
        if data['exp'].astimezone(PACIFIC_TIME) < datetime.datetime.now().astimezone(PACIFIC_TIME):
            return {
                'success': False,
                'error': 'Expired QR Code',
                'friendly': 'The check in/out code is invalid because it has expired.'
            }
        if data['scanned']:
            return {
                'success': False,
                'error': 'Duplicate QR Code',
                'friendly': 'The check in/out code is invalid because it has already been scanned.'
            }
        return {
            'success': True,
            'data': data
        }
    else:
        return {
            'success': False,
            'error': 'Invalid QR',
            'friendly': 'The check in/out code is invalid.'
        }

def is_qrid_scanned(qrid, user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT scanned FROM public.qr WHERE qrid = %s AND uid = %s',
            (qrid, user_id)
        )
        data = cur.fetchone()
    conn.close()
    if data:
        return {
            'success': True,
            'scanned': data['scanned']
        }
    return {
        'success': True,
        'scanned': False
    }