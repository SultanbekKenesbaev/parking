from flask import Flask, render_template, redirect, url_for, request, session, make_response, render_template_string, send_from_directory, Response
from datetime import datetime
import cv2
import easyocr
import threading
import time
from werkzeug.security import generate_password_hash, check_password_hash
from xhtml2pdf import pisa
from io import BytesIO
import os
from matplotlib.figure import Figure
import io
import base64
import numpy as np

from utils import crop_plate_image, save_images, is_valid_uz_plate
from database import (insert_entry, get_entry_by_plate, update_exit,
                      create_user, get_user, get_stats, get_all_entries,
                      get_entry_by_id, get_active_entries, get_daily_stats)

app = Flask(__name__)
app.secret_key = 'your_secret_key'
reader = easyocr.Reader(['en'])
frame_holder = {"frame": None}
recognized_plates = {"boxes": []}

# MJPEG видеопоток
camera_stream = cv2.VideoCapture('rtsp://172.16.15.28:8080/h264_ulaw.sdp')

def gen_frames():
    while True:
        success, frame = camera_stream.read()
        if not success:
            continue

        frame_holder["frame"] = frame.copy()

        # Рисуем прямоугольники вокруг распознанных номеров
        for box in recognized_plates.get("boxes", []):
            pts = [tuple(map(int, point)) for point in box]
            if len(pts) == 4:
                cv2.rectangle(frame, pts[0], pts[2], (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        hashed_password = generate_password_hash(password)
        create_user(username, hashed_password, role)
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user(username)
        if user and check_password_hash(user[2], password):
            session['username'] = username
            session['role'] = user[3]
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    plate_filter = request.args.get('plate')
    date_filter = request.args.get('date')

    from database import get_filtered_entries

    if session['role'] == 'admin':
        count, total_sum = get_stats()
        entries = get_filtered_entries(plate_filter, date_filter)
        return render_template('dashboard_admin.html',
                               count=count,
                               total_sum=total_sum,
                               entries=entries,
                               plate_filter=plate_filter or '',
                               date_filter=date_filter or '')
    else:
        entries = get_filtered_entries(plate_filter, date_filter)
        return render_template('dashboard_operator.html',
                               entries=entries,
                               plate_filter=plate_filter or '',
                               date_filter=date_filter or '')

recent_plates = {}

def plate_processing_loop():
    time.sleep(3)  # дать времени видеопотоку стартовать
    print("🟡 Обработка кадра...")

    frame_count = 0
    frame_skip = 5  # каждые 5 кадров обрабатывать

    while True:
        frame = frame_holder.get("frame")
        if frame is None:
            time.sleep(0.05)
            continue

        frame_count += 1
        if frame_count % frame_skip != 0:
            time.sleep(0.05)
            continue

        # Уменьшаем для ускорения OCR
        resized = cv2.resize(frame, (0, 0), fx=0.6, fy=0.6)
        results = reader.readtext(resized)

        # Масштабируем координаты обратно под оригинал
        recognized_plates["boxes"] = [np.array([[int(p[0]/0.6), int(p[1]/0.6)] for p in bbox]) for (bbox, _, _) in results]

        for (bbox, text, prob) in results:
            plate = text.replace(" ", "").upper()
            if not is_valid_uz_plate(plate):
                continue

            now = datetime.now()
            if plate in recent_plates and (now - recent_plates[plate]).total_seconds() < 10:
                continue
            recent_plates[plate] = now

            # Восстанавливаем координаты для вырезания
            bbox_scaled = np.array([[int(p[0]/0.6), int(p[1]/0.6)] for p in bbox])
            plate_img = crop_plate_image(frame, bbox_scaled)

            record = get_entry_by_plate(plate)
            if record:
                exit_img_path, _ = save_images(f"{plate}_exit", frame, plate_img)
                entry_time = datetime.strptime(record[1], "%Y-%m-%d %H:%M:%S")
                exit_time = datetime.now()
                total_time = exit_time - entry_time
                total_hours = max(1, int(total_time.total_seconds() // 3600))
                fee = total_hours * 30000
                update_exit(record[0], exit_time.strftime("%Y-%m-%d %H:%M:%S"), str(total_time), fee, exit_img_path)
                print(f"Выезд: {plate} | Сумма: {fee} сум")
            else:
                full_path, plate_path = save_images(plate, frame, plate_img)
                insert_entry(plate, now.strftime("%Y-%m-%d %H:%M:%S"), full_path, plate_path)
                print(f"Въезд: {plate}")

        time.sleep(0.05)



@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    entries = get_all_entries()
    return render_template('dashboard_admin.html', entries=entries)

@app.route('/plates/<path:filename>')
def serve_plate_image(filename):
    return send_from_directory('plates', filename)

@app.route('/receipt/<int:entry_id>')
def generate_receipt(entry_id):
    entry = get_entry_by_id(entry_id)
    if not entry or not entry[5]:
        return "Чек доступен только после выезда.", 400

    template = render_template('receipt.html',
                               plate=entry[1],
                               entry_time=entry[2],
                               exit_time=entry[3],
                               total_time=entry[4],
                               total_fee=entry[5])

    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(template, dest=pdf)
    if pisa_status.err:
        return "Ошибка генерации PDF", 500

    pdf.seek(0)
    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=receipt_{entry[1]}.pdf'
    return response

@app.route('/chart')
def chart():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    stats = get_daily_stats()
    days = [row[0] for row in stats][::-1]
    entries = [row[1] for row in stats][::-1]
    exits = [row[2] for row in stats][::-1]

    fig = Figure()
    ax = fig.subplots()
    ax.plot(days, entries, label='Въезды', marker='o')
    ax.plot(days, exits, label='Выезды', marker='s')
    ax.set_title('График въездов/выездов за последние 7 дней')
    ax.set_xlabel('Дата')
    ax.set_ylabel('Количество')
    ax.legend()
    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.getvalue()).decode()

    return render_template('chart.html', chart=image_base64)

if __name__ == '__main__':
    thread = threading.Thread(target=plate_processing_loop, daemon=True)
    thread.start()
    app.run(debug=True)
