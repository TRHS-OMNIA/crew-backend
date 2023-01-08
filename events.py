import os
import secrets
import datetime

from dateutil.parser import parse
import pytz

from db import get_db_connection
from gapi import get_calendar_api

RESERVED_PERIODS = [1]

PACIFIC_TIME = pytz.timezone('US/Pacific')
CALENDAR_ID = os.environ['G_CAL_ID']

def globalize_time_str(timestr) -> datetime.datetime:
    local = PACIFIC_TIME.localize(parse(timestr))
    return local.astimezone(pytz.utc)

def localize_time(time_obj: datetime.datetime) -> datetime.datetime:
    return time_obj.astimezone(PACIFIC_TIME)

def get_str_time(time_obj: datetime.datetime) -> str:
    ts = time_obj.strftime('%I:%M %p')
    if ts[0] == '0':
        return ts[1:]
    return ts

def get_str_day(time_obj: datetime.datetime) -> str:
    ts = time_obj.strftime('%d')
    if ts[0] == '0':
        return ts[1:]
    return ts

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

def get_event_row(event_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM public.events WHERE id = %s', (event_id, ))
        row = cur.fetchone()
    conn.close()
    if row:
        return row
    return None

def get_event_data(row):
    start = localize_time(row['start'])
    end = localize_time(row['end'])
    return {
        'title': row['title'],
        'time': f'{get_str_time(start)} - {get_str_time(end)}',
        'month': start.strftime('%b'),
        'day': get_str_day(start),
        'weekday': start.strftime('%A')
    }

def get_limit_entries(event_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT uid, period FROM public.entries JOIN public.users ON uid = id WHERE eid = %s', (event_id, ))
        entries = cur.fetchall()
    conn.close()
    return entries

def get_event_limits(row, entries):
    if row['limit'] is None:
        row['limit'] = -1
    if row['reserved'] is None:
        row['reserved'] = 0
    filled = 0
    reserve_filled = 0
    for entry in entries:
        filled += 1
        if entry['period'] in RESERVED_PERIODS:
            reserve_filled += 1
    event_limits = {
        'max': row['limit'],
        'reserved': row['reserved'],
        'available': row['limit'] - filled,
        'reserved_available': max(row['reserved'] - reserve_filled, 0),
    }
    return event_limits

def get_user_event_limits(event_limits, entries, user):
    user_event_limits = {
        'user_available': True,
        'user_justification': 'Join Event'
    }
    for entry in entries:
        if user['id'] == entry['uid']:
            user_event_limits['user_available'] = False
            user_event_limits['user_justification'] = 'Already Joined Event'
            return user_event_limits
    if len(entries) >= event_limits['max']:
        user_event_limits['user_available'] = False
        user_event_limits['user_justification'] = 'Event is Full'
        return user_event_limits
    if event_limits['available'] <= event_limits['reserved_available']:
        if user['period'] not in RESERVED_PERIODS:
            user_event_limits['user_available'] = False
            user_event_limits['user_justification'] = 'Remaining Positions Reserved'
    
    return user_event_limits

def _add_email_to_gcal(event_id, email):
    calendar_api = get_calendar_api()
    event = calendar_api.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
    if 'attendees' not in event.keys():
        event['attendees'] = [{'email': email}]
    else:
        for guest in event['attendees']:
            if guest['email'] == email:
                return
        event['attendees'].append({'email': email})
    calendar_api.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event, sendUpdates='all').execute()

def _remove_email_from_gcal(event_id, email):
    calendar_api = get_calendar_api()
    event = calendar_api.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
    if 'attendees' not in event.keys():
        return
    else:
        replacement = []
        for guest in event['attendees']:
            if guest['email'] == email:
               continue
            else:
                replacement.append(guest)
        event['attendees'] = replacement
    calendar_api.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event, sendUpdates='all').execute()


def join_event(event_id, user):
    row = get_event_row(event_id)
    entries = get_limit_entries(event_id)
    event_limits = get_event_limits(row, entries)
    user_event_limits = get_user_event_limits(event_limits, entries, user)
    if user_event_limits['user_available']:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO public.entries (uid, eid) VALUES (%s, %s)',
                (user['id'], event_id, )
            )
            conn.commit()
        conn.close()
        
        _add_email_to_gcal(event_id, user['id']+'@fjuhsd.org')

        return {
            'success': True
        }
    else:
        return {
            'success': False,
            'error': 'Failed to Join Event',
            'friendly': 'Unable to verify your elgibility to join this event: ' + user_event_limits['user_justification']
        }

def get_event_dashboard(event_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM public.events WHERE id = %s', (event_id, ))
        event_data_row = cur.fetchone()
        event_data = get_event_data(event_data_row)
        cur.execute(
            'SELECT * FROM public.entries JOIN public.users ON uid = id WHERE eid = %s', 
            (event_id, ))
        entries = cur.fetchall()
    conn.close()
    return {
        'success': True,
        'eventData': event_data,
        'entries': entries,
    }

def instant_check_in(event_id, user_id):
    now = datetime.datetime.now(pytz.utc)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE public.entries SET check_in = %s WHERE eid = %s AND uid = %s',
            (now, event_id, user_id)
        )
        conn.commit()
    conn.close()
    return {
        'success': True,
        'check_in': now
    }

def instant_check_out(event_id, user_id):
    now = datetime.datetime.now(pytz.utc)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE public.entries SET check_out = %s WHERE eid = %s AND uid = %s',
            (now, event_id, user_id)
        )
        conn.commit()
    conn.close()
    return {
        'success': True,
        'check_out': now
    }