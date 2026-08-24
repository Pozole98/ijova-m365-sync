# Sistema de Gestión, Aprovisionamiento y Sincronización Segura de Alumnos hacia Microsoft 365 Education / Microsoft Entra ID

Herramienta profesional en Python 3 para Linux diseñada para la validación, auditoría, aprovisionamiento masivo, altas continuas y bajas seguras de alumnos en **Microsoft 365 Education** / **Microsoft Entra ID** bajo el **principio de mínimo privilegio**, **cero impacto sobre usuarios existentes** y **protección estricta de datos de menores**.

---

## 🛡️ Principios de Seguridad y Reglas Absolutas

1. **Protección Total de Cuentas Existentes**:
   - Ningún usuario existente en Microsoft 365 es modificado, alterado o eliminado durante los procesos de sincronización masiva.
2. **Criterio de Existencia por UPN**:
   - La existencia de una cuenta se determina **únicamente por su `userPrincipalName` (UPN)** en Microsoft Entra ID (`[matricula]@ijova.com`).
3. **Mínimo Privilegio**:
   - Device Code Flow (`https://microsoft.com/devicelogin`) con permisos delegados estrictamente necesarios (`User.ReadWrite.All`, `Domain.Read.All`, `LicenseAssignment.Read.All`).
4. **Protección Criptográfica de Contraseñas Iniciales**:
   - Contraseñas temporales aleatorias de 12 caracteres generadas con entropía criptográfica (`secrets` de Python), forzando cambio de contraseña en el primer inicio de sesión (`forceChangePasswordNextSignIn: True`).
   - Almacenadas exclusivamente en `secrets/` con permisos Unix restrictivos **`0600`** (`-rw-------`), excluidas de Git.
5. **Salvaguarda contra Eliminación de Personal / Administradores**:
   - El motor de bajas (`delete`) solo acepta matrículas numéricas estudiantiles y **bloquea terminantemente** cualquier intento de eliminar cuentas de personal docente o administrativo (`admin@`, `docente@`, etc.).
6. **Papelera de Reciclaje (Soft-Delete)**:
   - Toda eliminación envía la cuenta a la papelera de reciclaje de Entra ID (30 días de retención recuperable).
7. **Snapshot Preventivo Integrado**:
   - Respaldo previo con timestamp de los usuarios del tenant antes de cualquier escritura.

---

## 📋 Requisitos Previos

- **Sistema Operativo:** Linux (Ubuntu/Debian, Fedora, CentOS, Arch, openSUSE, etc.)
- **Python:** 3.10 o superior
- **Cuenta de Administrador de Microsoft 365** (para autorizar el inicio de sesión vía navegador)
- **App Registration en Microsoft Entra ID**

---

## ⚙️ 1. Configuración de App Registration en Microsoft Entra ID

1. Ingresa al portal de **[Microsoft Entra admin center](https://entra.microsoft.com/)**.
2. Ve a **Identity > Applications > App registrations > New registration**.
3. Configura:
   - **Name:** `IJOVA-Provisioning-Tool`
   - **Supported account types:** `Accounts in this organizational directory only (Single tenant)`
   - **Redirect URI:** Selecciona plataforma `Public client/native (mobile & desktop)` e ingresa `https://login.microsoftonline.com/common/oauth2/nativeclient`.
4. En **Authentication > Advanced settings > Allow public client flows**, selecciona **Yes** y guarda.
5. En **API permissions > Add a permission > Microsoft Graph > Delegated permissions**, agrega:
   - ✅ `User.ReadWrite.All` (Creación, licenciamiento y eliminación de usuarios)
   - ✅ `Domain.Read.All` (Verificación de estado del dominio institucional)
   - ✅ `LicenseAssignment.Read.All` (Consulta de licencias y SKUs A1)
   - Haz clic en **Grant admin consent for [Tu Organización]**.
6. Copia el **Application (client) ID** y el **Directory (tenant) ID** desde la página de información general (*Overview*).

---

## 🚀 2. Instalación en Linux

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/ijova-m365-sync.git
cd ijova-m365-sync

# 2. Crear entorno virtual de Python 3
python3 -m venv .venv

# 3. Activar el entorno virtual
source .venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt
```

---

## 🔧 3. Configuración Inicial (`config.json`)

Copia la plantilla `config.example.json` a `config.json`:

```bash
cp config.example.json config.json
```

Edita `config.json` con tus identificadores de Entra ID:

```json
{
  "tenant_id": "TU_TENANT_ID_GUID",
  "client_id": "TU_CLIENT_ID_GUID",
  "domain": "ijova.com",
  "excel_path": "Listado de Alumnos Inscritos.xlsx",
  "sheet_name": "Listado Global Matriculado",
  "auth_method": "device_code",
  "graph_scopes": [
    "User.ReadWrite.All",
    "Domain.Read.All",
    "LicenseAssignment.Read.All"
  ],
  "reports_dir": "reports",
  "backups_dir": "backups",
  "data_dir": "data",
  "secrets_dir": "secrets"
}
```

---

## 💻 4. Uso del Sistema

### 🌟 Modo 1: Menú Interactivo en Terminal (Recomendado)
Para acceder a todas las funciones mediante un menú guiado paso a paso con explicaciones detalladas en pantalla, simplemente ejecuta:
```bash
python3 main.py
```
*(También puedes iniciarlo con `python3 main.py menu`)*.

---

### ⚡ Modo 2: Comandos Directos por Terminal (Para Scripts y Automatización)

### 🔹 Comando `validate` (Validación Local Offline)
Verifica la integridad de la hoja de cálculo, valida reglas de formato y exporta una copia normalizada sin conectar a internet:
```bash
python3 main.py validate
```

### 🔹 Comando `dry-run` (Simulación contra Microsoft 365)
Conecta a Microsoft Graph, descarga los usuarios de Entra ID y simula la sincronización sin realizar ninguna modificación en la nube:
```bash
python3 main.py dry-run
```

### 🔹 Comando `apply` (Aprovisionamiento Masivo)
Crea las cuentas de los alumnos nuevos en Microsoft 365, asigna licencias **Office 365 A1 for Students**, genera contraseñas seguras en `secrets/` y preserva 100% intactos los alumnos existentes:
```bash
python3 main.py apply
```

### 🔹 Comando `enroll` (Alta Rápida Extemporánea de Alumno Nuevo)
Asistente interactivo en terminal para dar de alta a un alumno que se inscribe a mitad de ciclo:
```bash
python3 main.py enroll
```
- Solicita matrícula, nombre(s), apellidos, nivel y grado.
- Valida disponibilidad en tiempo real en Entra ID.
- Crea la cuenta en Microsoft 365 (`[matricula]@ijova.com`).
- Asigna la licencia **Office 365 A1**.
- Añade el registro al archivo Excel para mantener el histórico sincronizado.
- Genera e imprime en pantalla la **Ficha de Acceso de Bienvenida** lista para entregar al alumno o tutor.

### 🔹 Comando `export-pdf` (Generador de Fichas Imprimibles con QR)
Genera documentos PDF de alta resolución con diseño institucional, datos del alumno, código QR directo a `portal.office.com` e instrucciones claras de primer inicio de sesión:
```bash
# Modo 1: Tarjetas recortables (4 por hoja A4 / Carta, ideal para grupos)
python3 main.py export-pdf -m cards

# Modo 2: Ficha individual completa (1 por hoja, ideal para expedientes)
python3 main.py export-pdf -m full

# Especificar archivo CSV de origen y nombre de salida
python3 main.py export-pdf -f secrets/credenciales_alumnos_XXXX.csv -o reports/fichas.pdf
```

### 🔹 Comando `reset` (Reseteo Rápido de Contraseñas por Matrícula)
Restablece la contraseña de un alumno en **2 segundos**, fuerza el cambio en el siguiente inicio y genera la ficha de entrega en PDF y consola:
```bash
python3 main.py reset 250081
```

### 🔹 Comando `delete` (Baja y Eliminación Segura por Matrícula o Excel)
Elimina uno o varios alumnos de Microsoft 365 a partir de su matrícula o desde un archivo Excel simple (solo matrículas), liberando su licencia A1 y enviando la cuenta a la papelera (soft-delete):
```bash
# Eliminar un alumno individual
python3 main.py delete 250010

# Eliminar varios alumnos en una sola línea
python3 main.py delete 250010 250062 250079

# Eliminar masivamente leyendo un archivo Excel con columna de matrículas
python3 main.py delete --excel "Bajas_Graduados_2026.xlsx"

# Eliminar alumnos leyendo una lista desde un archivo de texto
python3 main.py delete --file bajas.txt

# Modo desatendido (sin confirmación interactiva)
python3 main.py delete --excel "Bajas.xlsx" -y
```

### 🔹 Comando `restore` (Restauración Rápida desde la Papelera de Entra ID)
Restaura una cuenta de alumno dada de baja en los últimos 30 días, recuperando su buzón de correo, archivos de OneDrive y tareas de Teams intactos:
```bash
python3 main.py restore 250010
```

### 🔹 Comando `status` / `health` (Monitor Ejecutivo de Salud del Tenant)
Muestra un tablero en consola con el conteo de alumnos activos vs personal, disponibilidad de licencias Office 365 A1, estado del dominio y cuentas en papelera:
```bash
python3 main.py status
```

### 🔹 Comando `backup` (Snapshot de Auditoría)
Descarga y guarda un respaldo JSON/CSV con timestamp del estado actual de todos los usuarios en Entra ID:
```bash
python3 main.py backup
```

---

## 📊 5. Estructura de Directorios

```
ijovausers/
├── .gitignore                      # Excluye credenciales, tokens, Excel con PII y reportes
├── LICENSE                         # Licencia MIT
├── README.md                       # Manual operativo completo
├── requirements.txt                # Dependencias tipadas (msal, requests, openpyxl, reportlab, qrcode)
├── config.example.json             # Plantilla de configuración limpia
├── main.py                         # CLI principal con subcomandos
├── src/
│   ├── config.py                   # Carga de configuración y permisos 0700
│   ├── models.py                   # Modelos Pydantic y enums
│   ├── excel_parser.py             # Lector/escritor no destructivo de Excel
│   ├── validator.py                # Validador de reglas de integridad escolar
│   ├── normalizer.py               # Estandarizador de atributos de identidad
│   ├── password_generator.py       # Generador de contraseñas criptográficas seguras
│   ├── pdf_generator.py            # Generador de fichas y tarjetas PDF con código QR
│   ├── graph_client.py             # Cliente Microsoft Graph (Device Code, paginación, retries)
│   ├── sync_engine.py              # Motor de cruce estricto por UPN
│   ├── provisioner.py              # Motor de creación y licenciamiento A1
│   ├── enroll_engine.py            # Motor de alta interactiva extemporánea
│   ├── delete_engine.py            # Motor de baja con salvaguardas anti-admin
│   ├── reset_engine.py             # Motor de reseteo rápido de contraseñas
│   ├── restore_engine.py           # Motor de restauración desde papelera de Entra ID
│   ├── status_engine.py            # Monitor ejecutivo de salud y licencias
│   ├── auditor.py                  # Generador de snapshots atómicos
│   └── report_generator.py         # Exportador de reportes CSV y resúmenes Markdown
├── tests/
│   └── test_graph_client.py        # Suite de pruebas unitarias automatizadas
├── backups/                        # Snapshots con timestamp (0700) [Excluido de Git]
├── reports/                        # Reportes CSV, PDFs y bitácoras [Excluido de Git]
└── secrets/                        # Archivos de contraseñas de entrega (0600) [Excluido de Git]
```

---

## 🧪 6. Ejecución de Pruebas Unitarias

```bash
source .venv/bin/activate
python3 -m unittest tests/test_graph_client.py
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.
