import os
import secrets
import datetime
from typing import Dict

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

def edit_event(event_id, payload):
    calendar_api = get_calendar_api()
    event = {
        'title': payload['eventTitle'],
        'start': globalize_time_str(payload['date'] + ' ' + payload['startTime']),
        'end': globalize_time_str(payload['date'] + ' ' + payload['endTime']),
        'limit': _normalize_limit(payload['limit']),
        'reserved': _normalize_limit(payload['reserved']),
        'id': event_id
    }
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE public.events SET title = %s, start = %s, "end" = %s, "limit" = %s, "reserved" = %s WHERE id = %s',
            (event['title'], event['start'], event['end'], event['limit'], event['reserved'], event['id'])
        )
        conn.commit()
    conn.close()

    google_event = calendar_api.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
    google_event['summary'] = event['title']
    google_event['start']['dateTime'] = event['start'].isoformat()
    google_event['end']['dateTime'] = event['end'].isoformat()
    calendar_api.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=google_event, sendUpdates='all').execute()

    return {
        'success': True
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

def join_event(event_id, user, admin=False):
    row = get_event_row(event_id)
    entries = get_limit_entries(event_id)
    event_limits = get_event_limits(row, entries)
    user_event_limits = get_user_event_limits(event_limits, entries, user)
    if user_event_limits['user_available'] or admin:
        if admin and not user_event_limits['user_available'] and user_event_limits['user_justification'] == 'Already Joined Event':
            return {
                'success': False,
                'error': 'Failed to Add to Event',
                'friendly': 'User is already a member of the event.'
            }
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
        'eventLimits': get_event_limits(event_data_row, entries)
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

def _unwrap_time_input(ts: str) -> Dict[str, int]:
    h, m = ts.split(':')
    return {
        'hour': int(h),
        'minute': int(m)
    }

def edit_entry(event_id, user_id, payload):
    cin = None
    cout = None
    if payload['check_in'] or payload['check_out']:
        row = get_event_row(event_id)
        base_date = localize_time(row['start'])
        if payload['check_in']:
            cin = base_date.replace(**_unwrap_time_input(payload['check_in'])).astimezone(pytz.utc)
        if payload['check_out']:
            cout = base_date.replace(**_unwrap_time_input(payload['check_out'])).astimezone(pytz.utc)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE public.entries SET check_in = %s, check_out = %s, position = %s, private_note = %s WHERE uid = %s AND eid = %s',
            (cin, cout, payload['role'], payload['private_note'], user_id, event_id)
        )
        conn.commit()
    conn.close()
    return {
        'success': True,
        'edits': {
            'check_in': cin,
            'check_out': cout,
            'position': payload['role'],
            'private_note': payload['private_note']
        }
    }

def remove_user(event_id, user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'DELETE FROM public.entries WHERE eid = %s AND uid = %s',
            (event_id, user_id)
        )
        conn.commit()
    conn.close()
    _remove_email_from_gcal(event_id, user_id + '@fjuhsd.org')
    return {
        'success': True
    }

def remove_event(event_id):
    calendar_api = get_calendar_api()
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'DELETE FROM public.entries WHERE eid = %s',
            (event_id,)
        )
        cur.execute(
            'DELETE FROM public.qr WHERE eid = %s',
            (event_id,)
        )
        cur.execute(
            'DELETE FROM public.events WHERE id = %s',
            (event_id,)
        )
        conn.commit()
    conn.close()

    calendar_api.events().delete(calendarId=CALENDAR_ID, eventId=event_id, sendUpdates='all').execute()
    
    return {
        'success': True
    }

def _get_today() -> datetime.datetime:
    return datetime.datetime.now().astimezone(PACIFIC_TIME).replace(hour=0, minute=0)

def _get_tomorrow() -> datetime.datetime:
    return _get_today() + datetime.timedelta(days=1)

def _get_upcoming_events():
    tomorrow = _get_tomorrow()
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT * FROM public.events WHERE start > %s ORDER BY start ASC',
            (tomorrow, )
        )
        events = cur.fetchall()
    conn.close()
    return events

def _get_previous_events():
    today = _get_today()
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT * FROM public.events WHERE start < %s ORDER BY start DESC',
            (today, )
        )
        events = cur.fetchall()
    conn.close()
    return events

def _get_today_events():
    today = _get_today()
    tomorrow = _get_tomorrow()
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT * FROM public.events WHERE start > %s AND start < %s ORDER BY start ASC',
            (today, tomorrow)
        )
        events = cur.fetchall()
    conn.close()
    return events

def _get_id_event_data(row):
    ret = get_event_data(row)
    ret['id'] = row['id']
    return ret

def _get_user_event_data(row):
    data = get_event_data(row)
    data['event_id'] = row['eid']
    data['check_in'] = row['check_in']
    data['check_out'] = row['check_out']
    data['position'] = row['position']
    data['start'] = row['start']
    return data

def upcoming():
    rows = _get_upcoming_events()
    ret = []
    for row in rows:
        ret.append(_get_id_event_data(row))
    return ret

def previous():
    rows = _get_previous_events()
    ret = []
    for row in rows:
        ret.append(_get_id_event_data(row))
    return ret

def today():
    rows = _get_today_events()
    ret = []
    for row in rows:
        ret.append(_get_id_event_data(row))
    return ret

def list_events():
    return {
        'success': True,
        'upcoming': upcoming(),
        'previous': previous(),
        'today': today()
    }

def _get_upcoming_user_events(user_id):
    tomorrow = _get_tomorrow()
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT eid, title, start, "end", position, check_in, check_out FROM public.entries JOIN public.events ON eid = id WHERE uid = %s AND start > %s ORDER BY start ASC',
            (user_id, tomorrow)
        )
        events = cur.fetchall()
    conn.close()
    return events

def _get_previous_user_events(user_id):
    today = _get_today()
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT eid, title, start, "end", position, check_in, check_out FROM public.entries JOIN public.events ON eid = id WHERE uid = %s AND start < %s ORDER BY start DESC',
            (user_id, today)
        )
        events = cur.fetchall()
    conn.close()
    return events

def _get_today_user_events(user_id):
    tomorrow = _get_tomorrow()
    today = _get_today()
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT eid, title, start, "end", position, check_in, check_out FROM public.entries JOIN public.events ON eid = id WHERE uid = %s AND start > %s AND start < %s ORDER BY start ASC',
            (user_id, today, tomorrow)
        )
        events = cur.fetchall()
    conn.close()
    return events

def user_upcoming(user_id):
    rows = _get_upcoming_user_events(user_id)
    ret = []
    for row in rows:
        data = _get_user_event_data(row)
        ret.append(data)
    return ret

def user_previous(user_id):
    rows = _get_previous_user_events(user_id)
    ret = []
    for row in rows:
        data = _get_user_event_data(row)
        ret.append(data)
    return ret

def user_today(user_id):
    rows = _get_today_user_events(user_id)
    ret = []
    for row in rows:
        data = _get_user_event_data(row)
        ret.append(data)
    return ret

def list_user_events(user_id):
    return {
        'success': True,
        'upcoming': user_upcoming(user_id),
        'previous': user_previous(user_id),
        'today': user_today(user_id)
    }

def get_single_user_event_data(event_id, user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT eid, title, start, "end", position, check_in, check_out FROM public.entries JOIN public.events ON eid = id WHERE uid = %s AND eid = %s',
            (user_id, event_id)
        )
        row = cur.fetchone()
    conn.close()

    return {
        'success': True,
        'userEventData': _get_user_event_data(row)
    }

def _get_event_for_edit(event_id):
    row = get_event_row(event_id)
    date = localize_time(row['start']).strftime('%m/%d/%Y')
    start_time = localize_time(row['start']).strftime('%H:%M')
    end_time = localize_time(row['end']).strftime('%H:%M')
    limit = str(row['limit'])
    if not limit:
        limit = ''
    reserved = str(row['reserved'])
    if not reserved:
        reserved = ''
    return {
        'success': True,
        'eventTitle': row['title'],
        'date': date,
        'startTime': start_time,
        'endTime': end_time,
        'limit': limit,
        'reserved': reserved
    }
