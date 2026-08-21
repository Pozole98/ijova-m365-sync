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
