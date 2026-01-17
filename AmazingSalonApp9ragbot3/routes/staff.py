from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import get_user, get_all_users, update_user
from datetime import datetime, timedelta

bp = Blueprint('staff', __name__)

@bp.route('/staff')
@login_required
def index():
    staff = [user for user in get_all_users() if user.get('is_staff', False)]
    return render_template('staff_schedule.html', staff=staff)

@bp.route('/staff/schedule')
@login_required
def schedule():
    staff = [user for user in get_all_users() if user.get('is_staff', False)]
    return render_template('staff_schedule.html', staff=staff)

@bp.route('/staff/schedule/update', methods=['POST'])
@login_required
def update_schedule():
    staff_id = request.form['staff_id']
    date = request.form['date']
    start_time = request.form['start_time']
    end_time = request.form['end_time']

    break_starts = request.form.getlist('break_start[]')
    break_ends = request.form.getlist('break_end[]')

    breaks = []
    for i in range(len(break_starts)):
        if break_starts[i] and break_ends[i]:
            breaks.append({
                "start_time": break_starts[i],
                "end_time": break_ends[i]
            })

    staff = get_user(staff_id)
    if not staff:
        flash('Staff member not found')
        return redirect(url_for('staff.schedule'))

    schedule = staff.get('schedule', {})
    schedule[date] = {'start': start_time, 'end': end_time, 'breaks': breaks}

    update_user(staff_id, schedule=schedule)
    flash('Schedule updated successfully')
    return redirect(url_for('staff.schedule'))
@bp.route('/breaks/<shift_id>', methods=['GET', 'POST'])
@login_required
def manage_breaks(shift_id):
    if request.method == 'POST':
        new_break = {
            'start_time': request.form['break_start'],
            'end_time': request.form['break_end'],
            'type': request.form['break_type']  # lunch, coffee, etc.
        }
        
        shift = db.get(shift_id)
        if shift:
            breaks = shift.get('breaks', [])
            breaks.append(new_break)
            update_shift(shift_id, breaks=breaks)
            flash('Break added successfully')
        
    return redirect(url_for('staff.schedule'))
@bp.route('/breaks/<shift_id>', methods=['POST'])
@login_required
def add_break(shift_id):
    from models import add_break_to_shift
    from datetime import datetime
    
    start_time = datetime.fromisoformat(request.form['break_start'])
    end_time = datetime.fromisoformat(request.form['break_end'])
    
    if add_break_to_shift(shift_id, start_time.isoformat(), end_time.isoformat()):
        flash('Break added successfully')
    else:
        flash('Failed to add break')
    
    return redirect(url_for('staff.schedule'))
