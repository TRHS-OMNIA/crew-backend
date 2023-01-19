from db import get_db_connection

def get_all_users():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM public.users')
        users = cur.fetchall()
    conn.close()
    return {
        'success': True,
        'users': users
    }