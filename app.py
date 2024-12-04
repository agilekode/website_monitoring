from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort, jsonify
import os
import pandas as pd
from web_monitering import web_moniter_by_urls, web_moniter_by_file
import asyncio
import threading
import time

app = Flask(__name__)

app.secret_key = 'supersecretkey'

app.config['UPLOAD_FOLDER'] = '/home/ahmad/Documents/web_monitering/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xlsx'}

DOWNLOAD_FOLDER = '/home/ahmad/Documents/web_monitering/result'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

task_status = []
task_status_lock = threading.Lock()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def check_credentials(username, password):
    with open('users.txt', 'r') as f:
        users = [line.strip().split(':') for line in f.readlines()]
        for user, pwd in users:
            if user == username and pwd == password:
                return True
    return False

def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if check_credentials(username, password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')

    return render_template('login.html', show_navbar=False)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if 'username' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            task_id = str(int(time.time() * 1000))
            thread = threading.Thread(target=process_file, args=(file_path, task_id))
            thread.start()
            task_status.append({'task_id': task_id, 'file_name':file.filename, 'status': 'Processing....'})

        web_url = request.form.get('web_url')
        image_url = request.form.get('image_url')
        if web_url or image_url:
            task_id = str(int(time.time() * 1000))
            thread = threading.Thread(target=process_urls, args=(task_id, web_url, image_url))
            thread.start()
            task_status.append({'task_id': task_id, 'file_name':web_url, 'status': 'Processing....'})
        
        return render_template('dashboard.html', extracted_data=task_status, username=session['username'], show_navbar=True)
    
    if task_status:
        return render_template('dashboard.html', extracted_data=task_status, username=session['username'], show_navbar=True)

    return render_template('dashboard.html', username=session['username'], show_navbar=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def safe_update_status(task_id, status):
    with task_status_lock:
        next((task.update({'status': status}) for task in task_status if task['task_id'] == task_id), None)

def process_urls(task_id, web_url, image_url):
    try:
        asyncio.run(web_moniter_by_urls(
            web_url=web_url, 
            img_url=image_url,
            task=task_id
        ))
        safe_update_status(task_id, 'Completed')
    except Exception as e:
        safe_update_status(task_id, str(e))


def process_file(file_path, task_id):
    try:
        asyncio.run(web_moniter_by_file(
            req_file_path=file_path, 
            task=task_id
        ))
        safe_update_status(task_id, 'Completed')
    except Exception as e:
        safe_update_status(task_id, str(e))


@app.route('/download-file')
def download_file():
    task_id = request.args.get('task_id')
    if not task_id:
        return "Task ID is required", 400

    filename = f"{task_id}_web_monitering_output.xlsx"
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)

    if os.path.exists(file_path):
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    else:
        return abort(404, description="File not found!")

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify(task_status)

@app.route('/logout')
@login_required
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
