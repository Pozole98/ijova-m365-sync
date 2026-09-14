"""
Generador de contraseñas temporales criptográficamente seguras para cuentas de alumnos.
Cumple con las directivas de complejidad de Microsoft Entra ID.
"""
import secrets
import string


def generate_secure_password(length: int = 12) -> str:
    """
    Genera una contraseña aleatoria y segura de al menos 12 caracteres.
    Garantiza al menos una mayúscula, una minúscula, un dígito y un símbolo especial permitido por M365.
    """
    if length < 10:
        length = 12

    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%*-_+"

    # Garantizar presencia de cada categoría
    password = [
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]

    all_chars = upper + lower + digits + symbols
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))

    # Mezclar caracteres para evitar patrones predecibles
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def validate_password_complexity(password: str) -> tuple[bool, str]:
    """
    Valida si una contraseña personalizada cumple con las directivas de complejidad de Microsoft 365 / Entra ID:
    - Longitud mínima de 8 caracteres.
    - Contiene al menos 3 de las siguientes 4 categorías:
      1. Letras mayúsculas (A-Z)
      2. Letras minúsculas (a-z)
      3. Números (0-9)
      4. Caracteres especiales (@, #, $, %, etc.)
    """
    if not password or len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres (recomendado: 10 o más)."

    categories = 0
    if any(c in string.ascii_uppercase for c in password):
        categories += 1
    if any(c in string.ascii_lowercase for c in password):
        categories += 1
    if any(c in string.digits for c in password):
        categories += 1
    if any(not c.isalnum() for c in password):
        categories += 1

    if categories < 3:
        return False, "La contraseña debe incluir al menos 3 de las 4 categorías: mayúsculas, minúsculas, números y símbolos."

    return True, ""
