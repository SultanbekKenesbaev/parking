# временное хранение текущей сессии
session_user = {}

def login_user(user_id, role):
    session_user['id'] = user_id
    session_user['role'] = role

def logout_user():
    session_user.clear()

def current_user():
    return session_user if 'id' in session_user else None
