import os
import secrets
import datetime

from dateutil.parser import parse
import pytz

from db import get_db_connection
from gapi import get_calendar_api

PACIFIC_TIME = pytz.timezone('US/Pacific')

def globalize_time_str(timestr) -> datetime.datetime:
    local = PACIFIC_TIME.localize(parse(timestr))
    return local.astimezone(pytz.utc)

def _normalize_limit(limit):
    if limit == '' or int(limit) == 0:
        return None
    return int(limit)

def new_event(payload):
    calendar_api = get_calendar_api()
    event = {
        'title': payload['eventTitle'],
        'start': globalize_time_str(payload['date'] + ' ' + payload['startTime']),
        'end': globalize_time_str(payload['date'] + ' ' + payload['endTime']),
        'limit': _normalize_limit(payload['limit']),
        'reserved': _normalize_limit(payload['reserved']),
        'id': ''
    }
    conn = get_db_connection()
    with conn.cursor() as cur:
        eventId = None
        while not eventId:
            eventId = secrets.token_hex(4)
            cur.execute('SELECT * FROM public.events WHERE id = %s', (eventId, ))
            row = cur.fetchone()
            if row:
                eventId = None
            else:
                event['id'] = eventId
        cur.execute(
            'INSERT INTO public.events (id, title, start, "end", "limit", "reserved") VALUES (%s, %s, %s, %s, %s, %s)',
            (event['id'], event['title'], event['start'], event['end'], event['limit'], event['reserved'])
        )
        conn.commit()
    conn.close()

    google_event = {
        'summary': event['title'],
        'start': {
            'dateTime': event['start'].isoformat()
        },
        'end' : {
            'dateTime': event['end'].isoformat()
        },
        'id': eventId
    }

    calendar_api.events().insert(calendarId=os.environ['G_CAL_ID'], body=google_event).execute()

    return {
        'success': True,
        'id': eventId
    }