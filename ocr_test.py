import cv2
import easyocr
import time

# Инициализация EasyOCR
reader = easyocr.Reader(['en'])

# Запуск камеры (0 — встроенная, 1 — внешняя)
cap = cv2.VideoCapture(1)  # поменяй на 0 если не показывает

print("Запуск камеры...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Не удалось получить кадр.")
        break

    # Преобразование BGR → RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Распознавание текста
    results = reader.readtext(frame_rgb)
    
    for (bbox, text, prob) in results:
        plate = text.replace(" ", "").upper()
        print(f"[{round(prob, 2)}] Найдено: {plate}")
        
        # Отрисовка прямоугольника
        (top_left, top_right, bottom_right, bottom_left) = bbox
        top_left = tuple(map(int, top_left))
        bottom_right = tuple(map(int, bottom_right))
        cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)
        cv2.putText(frame, plate, top_left, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow('EasyOCR Test', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
