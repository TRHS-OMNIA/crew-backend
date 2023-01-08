from flask import Flask, request, g
from flask_cors import CORS

from auth import gauth_login, authorization_required, admin_only, inject_user
from events import new_event, get_event_row, get_event_data, get_event_limits, join_event, get_user_event_limits, get_limit_entries

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, origins='*', send_wildcard=False)

@app.post('/auth/google')
def google_login():
    body = request.json
    return gauth_login(body['token'])

@app.post('/create')
@authorization_required
@admin_only
def create_event():
    payload = request.json
    try:
        return new_event(payload)
    except Exception:
        return {
            'success': False,
            'error': 'Unknown Error',
            'friendly': 'No idea what went wrong, might be a Google OAuth Delegation token issue...'
        }

@app.get('/event/<event_id>')
@inject_user
def get_event(event_id):
    row = get_event_row(event_id)
    if row:
        data = get_event_data(row)
        entries = get_limit_entries(event_id)
        event_limits = get_event_limits(row, entries)
        if g.user:
            return {
                'success': True,
                'eventData': data,
                'eventLimits': event_limits,
                'userEventLimits': get_user_event_limits(event_limits, entries, g.user)
            }
        else: 
            return {
                'success': True,
                'eventData': data,
                'eventLimits': event_limits,
                'userEventLimits': {
                    'user_available': False,
                    'user_justification': 'Join Event'
                }
            }
    return {
        'success': False,
        'error': 'Invalid Event',
        'friendly': 'There is no record of this event.'
    }

@app.post('/join')
@authorization_required
def user_join_event():
    payload = request.json
    return join_event(payload['eventId'], g.user)