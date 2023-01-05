import os
import psycopg
import csv

def add_user(cursor: psycopg.Cursor, uid, last_name, first_name, nickname, grade, period, classs):
    cursor.execute(
            "INSERT INTO public.users (id, last_name, first_name, nickname, grade, period, class) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (uid, last_name, first_name, nickname, grade, period, classs)
        )

with open('users.csv', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            for row in reader:
                nickname = None
                if row['nickname']:
                    nickname = row['nickname']
                add_user(cur, row['u_id'], row['last_name'], row['first_name'], nickname, row['grade'], row['period'], row['class'])
            conn.commit()