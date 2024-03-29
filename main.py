from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, g
from flask_cors import CORS

from auth import gauth_login, authorization_required, admin_only, inject_user
from events import (
    new_event, 
    get_event_row, 
    get_event_data, 
    get_event_limits, 
    join_event, 
    get_user_event_limits, 
    get_limit_entries,
    get_event_dashboard,
    instant_check_in,
    instant_check_out,
    edit_entry, list_events,
    list_user_events,
    get_single_user_event_data,
    remove_user,
    _get_event_for_edit,
    edit_event,
    remove_event
    )

from qr import (
    create_qr,
    get_data_from_qrid,
    is_qrid_scanned
)

from users import (
    get_all_users
)

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

@app.get('/event/<event_id>/dashboard')
@authorization_required
@admin_only
def populate_event_dashboard(event_id):
    return get_event_dashboard(event_id)

@app.get('/event/<event_id>/user/<user_id>/checkin')
@authorization_required
@admin_only
def check_in(event_id, user_id):
    return instant_check_in(event_id, user_id)

@app.get('/event/<event_id>/user/<user_id>/checkout')
@authorization_required
@admin_only
def check_out(event_id, user_id):
    return instant_check_out(event_id, user_id)

@app.post('/event/<event_id>/user/<user_id>')
@authorization_required
@admin_only
def dashboard_edit(event_id, user_id):
    payload = request.json
    return edit_entry(event_id, user_id, payload)

@app.get('/event/<event_id>/user/<user_id>/remove')
@authorization_required
@admin_only
def delete_user_from_event(event_id, user_id):
    return remove_user(event_id, user_id)

@app.get('/events')
@inject_user
def get_event_lists():
    return list_events(user=g.user)

@app.get('/events/user')
@authorization_required
def get_user_events():
    return list_user_events(g.user['id'])

@app.get('/events/user/<user_id>')
@authorization_required
@admin_only
def get_users_events(user_id):
    return list_user_events(user_id)

@app.get('/event/<event_id>/user')
@authorization_required
def get_single_event_user(event_id):
    return get_single_user_event_data(event_id, g.user['id'])

@app.get('/event/<event_id>/qr')
@authorization_required
def generate_checkin_qr(event_id):
    return create_qr(event_id, g.user['id'])

@app.get('/scan/qr/<qrid>')
@authorization_required
@admin_only
def scan_qr_data(qrid):
    return get_data_from_qrid(qrid)

@app.get('/event/<event_id>/edit')
@authorization_required
@admin_only
def get_editable_event(event_id):
    return _get_event_for_edit(event_id)

@app.post('/event/<event_id>/edit')
@authorization_required
@admin_only
def edit_existing_event(event_id):
    payload = request.json
    return edit_event(event_id, payload)

@app.get('/event/<event_id>/delete')
@authorization_required
@admin_only
def delete_event(event_id):
    return remove_event(event_id)

@app.get('/users')
@authorization_required
@admin_only
def list_all_users():
    return get_all_users()

@app.get('/event/<event_id>/add/<user_id>')
@authorization_required
@admin_only
def admin_add_user_to_event(event_id, user_id):
    user = {'id': user_id}
    return join_event(event_id, user, admin=True)

@app.get('/qr/<qrid>')
@authorization_required
def check_qrid_scan_state(qrid):
    return is_qrid_scanned(qrid, g.user['id'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6512)
