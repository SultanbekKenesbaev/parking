import sqlite3

conn = sqlite3.connect("db/parking.db", check_same_thread=False)
cur = conn.cursor()

# Таблица парковки
cur.execute('''CREATE TABLE IF NOT EXISTS parking (
    id INTEGER PRIMARY KEY,
    plate TEXT,
    entry_time TEXT,
    exit_time TEXT,
    total_time TEXT,
    total_fee INTEGER,
    full_image TEXT,
    plate_image TEXT,
    exit_image TEXT
)''')

# Таблица пользователей
cur.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'operator'))
)''')
conn.commit()

# ---------------- ФУНКЦИИ ДЛЯ ПАРКОВКИ ------------------

def insert_entry(plate, entry_time, full_path, plate_path):
    cur.execute("INSERT INTO parking (plate, entry_time, full_image, plate_image) VALUES (?, ?, ?, ?)",
                (plate, entry_time, full_path, plate_path))
    conn.commit()

def get_entry_by_plate(plate):
    cur.execute("SELECT id, entry_time FROM parking WHERE plate=? AND exit_time IS NULL", (plate,))
    return cur.fetchone()

def update_exit(id, exit_time, total_time, total_fee, exit_img_path):
    cur.execute("""
        UPDATE parking
        SET exit_time=?, total_time=?, total_fee=?, exit_image=?
        WHERE id=?
    """, (exit_time, total_time, total_fee, exit_img_path, id))
    conn.commit()


# ---------------- ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ------------------

def insert_user(username, password, role):
    cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, role))
    conn.commit()

def get_user_by_username(username):
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    return cur.fetchone()
# Создание нового пользователя
def create_user(username, password, role):
    cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
    conn.commit()

# Получить пользователя по имени
def get_user(username):
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    return cur.fetchone()

# Получить статистику для админа
def get_stats():
    cur.execute("SELECT COUNT(*), SUM(total_fee) FROM parking WHERE exit_time IS NOT NULL")
    return cur.fetchone()
# Получить записи с фильтрацией по номеру и дате
def get_filtered_entries(plate_filter=None, date_filter=None, only_current=False):
    query = '''
        SELECT 
            id,
            plate,
            entry_time,
            full_image,
            plate_image,
            exit_time,
            total_fee
        FROM parking
        WHERE 1=1
    '''
    params = []

    if only_current:
        query += " AND exit_time IS NULL"

    if plate_filter:
        query += " AND plate LIKE ?"
        params.append(f"%{plate_filter.upper()}%")

    if date_filter:
        query += " AND DATE(entry_time) = ?"
        params.append(date_filter)

    query += " ORDER BY id DESC"
    cur.execute(query, params)
    return cur.fetchall()


def get_all_entries():
    cur.execute("SELECT * FROM parking ORDER BY id DESC")
    return cur.fetchall()

def get_entry_by_id(entry_id):
    cur.execute("SELECT id, plate, entry_time, exit_time, total_time, total_fee FROM parking WHERE id=?", (entry_id,))
    return cur.fetchone()


def get_active_entries():
    cur.execute('''
        SELECT id, plate, entry_time, full_image, plate_image
        FROM parking
        WHERE exit_time IS NULL
        ORDER BY id DESC
    ''')
    return cur.fetchall()

def get_daily_stats():
    cur.execute('''
        SELECT DATE(entry_time) AS day, 
               COUNT(*) AS entries,
               SUM(CASE WHEN exit_time IS NOT NULL THEN 1 ELSE 0 END) AS exits
        FROM parking
        GROUP BY day
        ORDER BY day DESC
        LIMIT 7
    ''')
    return cur.fetchall()

