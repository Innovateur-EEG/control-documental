import bcrypt

def generar_hash(password: str) -> str:
    """Genera un hash seguro usando bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica la contraseña plana contra el hash guardado"""
    if not hashed_password:
        return False
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))