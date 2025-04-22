import os
import cv2
from datetime import datetime
import re
from flask import render_template
from xhtml2pdf import pisa


def is_valid_uz_plate(plate: str) -> bool:
    plate = plate.replace(" ", "").upper()
    pattern1 = r"^\d{2}[A-Z]\d{3}[A-Z]{2}$"
    pattern2 = r"^\d{2}\d{3}[A-Z]{3}$"
    return re.match(pattern1, plate) or re.match(pattern2, plate)

def generate_pdf_receipt(plate, entry_time, exit_time, total_time, total_fee):
    from pathlib import Path
    from datetime import datetime
    os.makedirs("receipts", exist_ok=True)

    html = render_template("receipt.html", plate=plate,
                           entry_time=entry_time,
                           exit_time=exit_time,
                           total_time=total_time,
                           total_fee=total_fee)

    filename = f"receipts/{plate}_{int(datetime.now().timestamp())}.pdf"
    with open(filename, "wb") as f:
        pisa.CreatePDF(html, dest=f)
    return filename

def crop_plate_image(frame, bbox):
    (top_left, top_right, bottom_right, bottom_left) = bbox
    x_min = int(min(top_left[0], bottom_left[0]))
    x_max = int(max(top_right[0], bottom_right[0]))
    y_min = int(min(top_left[1], top_right[1]))
    y_max = int(max(bottom_left[1], bottom_right[1]))
    return frame[y_min:y_max, x_min:x_max]

def save_images(plate, full_img, plate_img):
    os.makedirs("plates", exist_ok=True)
    timestamp = int(datetime.now().timestamp())
    filename = f"plates/{plate}_{timestamp}"
    full_path = filename + "_full.jpg"
    plate_path = filename + "_plate.jpg"
    cv2.imwrite(full_path, full_img)
    cv2.imwrite(plate_path, plate_img)
    return full_path, plate_path
