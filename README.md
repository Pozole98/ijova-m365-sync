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
8. **Verificación Previa y Confirmación Obligatoria de Alumno**:
   - Antes de cambiar cualquier contraseña, el sistema consulta en tiempo real Microsoft Entra ID y cruza con el listado escolar oficial (Excel/ODS). Muestra la ficha de identidad completa (Nombre, Matrícula, UPN, Nivel, Grado y Foto) y solicita confirmación explícita (`¿Confirmas que es el alumno correcto? [s/N]`) para evitar cambios accidentales por error de captura.
9. **Aislamiento Local Estricto y Escudo Web (Loopback, Anti-CSRF y Anti-Rebinding)**:
   - El servidor de la interfaz gráfica (`gui`) se enlaza exclusivamente a la interfaz virtual loopback (`127.0.0.1`), haciendo que el puerto sea física y lógicamente inaccesible desde cualquier otra computadora de la red local o Wi-Fi.
   - Cuenta con un escudo de seguridad HTTP en tiempo de ejecución: filtro estricto de IP local (`127.0.0.1`/`::1`), mitigación de DNS Rebinding (validación de cabecera `Host`), bloqueo de peticiones cross-site (`Sec-Fetch-Site` / `Origin`), cabeceras de blindaje (`Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`) y sanitización estricta contra path traversal en la descarga de PDFs.

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
   - ✅ `Group.ReadWrite.All` (Creación y gestión de grupos M365 y clases de Teams)
   - ✅ `TeamSettings.ReadWrite.All` (Renombrado y configuración institucional de equipos)
   - ✅ `TeamMember.ReadWrite.All` (Matriculación asistida de alumnos y docentes)
   - ✅ `Team.ReadBasic.All` (Auditoría de inventario básico de equipos en Teams)
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
    "LicenseAssignment.Read.All",
    "Group.ReadWrite.All",
    "TeamSettings.ReadWrite.All",
    "TeamMember.ReadWrite.All",
    "Team.ReadBasic.All"
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

El menú interactivo organiza todas las operaciones en bloques temáticos accesibles mediante una tecla:
- `[1]` a `[3]`: Validación offline, simulación `dry-run` y aprovisionamiento masivo `apply`.
- `[4]`: Alta rápida extemporánea de alumno nuevo (`enroll`).
- `[5]` y `[6]`: Reseteo guiado de contraseñas y generación de fichas PDF con código QR.
- **`[T]`**: **Auditoría y Gestión de Equipos / Clases en Teams** (auditoría en tiempo real, libro Excel de 4 hojas, renombrado y creación asistida de clases con matriculación automática de alumnos por nivel y grado).
- `[7]` y `[8]`: Bajas seguras anti-admin y restauración desde papelera de Entra ID.
- `[9]` a `[12]`: Monitoreo de salud del tenant, snapshots preventivos y auditoría con galería de fotos.
- **`[G]`**: **Lanzar la Interfaz Gráfica Web Local (Dashboard)** en el navegador.

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

### 🔹 Comando `gui` (Interfaz Gráfica Web Local / Dashboard Completo)
Inicia un panel web moderno, responsivo e intuitivo en tu navegador (`http://127.0.0.1:5000`) con **8 módulos especializados**:

1. **🔑 Restablecer Contraseña**:
   - **Buscador predictivo**: Búsqueda en tiempo real por matrícula o por nombre completo.
   - **Ficha de Verificación con Fotografía**: Despliega fotografía institucional oficial de Entra ID, grupo, nivel escolar y estado de cuenta.
   - **Confirmación Obligatoria**: Exige verificar los datos del alumno y marcar la casilla de confirmación antes de habilitar el reseteo.
   - **Emisión e Impresión Inmediata**: Muestra la nueva clave temporal generada y permite imprimir directamente la ficha de acceso con código QR o descargar el archivo PDF.

2. **🗑️ Bajas de Alumnos (Con Confirmación Estricta por Matrícula)**:
   - Localización visual del alumno y verificación de su estado.
   - **Salvaguarda de seguridad crítica**: Para evitar bajas accidentales, el botón de eliminación permanece bloqueado hasta que el operador **escribe textualmente la matrícula del alumno** en un campo de validación.
   - La baja es enviada a la papelera (*soft-delete*, 30 días de retención) y salvaguardada contra cuentas de personal/admin.

3. **🔄 Papelera & Restauración**:
   - Listado interactivo de alumnos eliminados en los últimos 30 días en Microsoft Entra ID.
   - Restauración en un solo clic con recuperación intacta de buzón de correo, archivos de OneDrive y equipos de Teams.

4. **👥 Auditoría y Administración de Microsoft Teams**:
   - **Métricas Ejecutivas en Tiempo Real**: Tarjetas con conteo total de equipos, clases activas ciclo 2026-2027, clases históricas 2025-2026, equipos docentes/staff, equipos huérfanos (0 propietarios) y equipos creados por alumnos.
   - **Regla Estricta de Ciclos Escolares**: Detección automática por fecha de creación (`>= 2026-08-01` -> Ciclo 2026-2027; `< 2026-08-01` -> Ciclo Histórico 2025-2026).
   - **Filtros Rápidos Multicriterio (Pills)**:
     - *Ciclo:* Todos, 2026-2027, 2025-2026.
     - *Nivel/Sección:* Todos, Preparatoria, Secundaria, Primaria, Preescolar, Otros / Staff.
     - *Tipo / Dueño:* Todos, Clase Educativa, Personal / Staff, Huérfano (0 Dueños), Creado por Alumno.
   - **Tabla Interactiva**: Búsqueda en vivo por nombre, ID o profesor, badges visuales de ciclo, tipo de equipo, propietarios (destacando alertas si fue creado por alumno o si es huérfano), conteo de miembros/estudiantes y menú de acciones.
   - **🎓 Asistente de Creación de Nueva Clase**:
     - Formulario interactivo donde el administrador introduce la materia, selecciona el nivel educativo y grado escolar.
     - **Matriculación automática de alumnos**: El sistema cruza en tiempo real el grado seleccionado con la base escolar, muestra exactamente cuántos alumnos serán matriculados y los enrola automáticamente al crear el equipo.
     - **Selección de Docente Responsable**: Desplegable cargado directamente desde el catálogo de profesores y personal en Entra ID para asignarlo como propietario del equipo.
   - **✏️ Renombrado Institucional y Archivado**: Modales interactivos para renombrar equipos al instante en Microsoft Teams o archivarlos para fin de ciclo.
   - **📊 Exportación Oficial a Excel (4 Hojas)**: Descarga directa con un solo clic del libro de auditoría consolidado (`Inventario Consolidado`, `Clases 2026-2027`, `Clases Históricas 2025-2026` y `Auditoría y Huérfanos`).

5. **🖼️ Auditoría de Fotos de Perfil**:
   - **Métricas ejecutivas**: Indicadores de total auditado, porcentaje con foto y cuentas pendientes de subir fotografía institucional.
   - **Mosaico visual interactivo**: Galería filtrable en tiempo real (*Todos*, *Con Foto*, *Sin Foto*) con avatares descargados y preview de credencial.
   - **Escaneo concurrente**: Botón para disparar auditoría en segundo plano contra Microsoft Graph.

6. **📋 Historial de Fichas**:
   - Bitácora de las contraseñas restablecidas durante la sesión.
   - Accesos directos para descargar o imprimir el comprobante PDF oficial generado para cada alumno.

7. **📈 Salud del Tenant**:
   - Diagnóstico en tiempo real del dominio institucional (`ijova.com`), Tenant ID, cuentas activas y enlaces a portales de administración.

8. **💻 Terminal & Guía CLI**:
   - Pestaña integrada que cataloga todas las operaciones masivas y avanzadas disponibles desde la línea de comandos (aprovisionamiento masivo, validación offline, simulación `dry-run`, reseteo grupal por Excel, reportes ejecutivos).
   - Botones de copiado en 1 clic para cada comando.

```bash
# Iniciar la interfaz gráfica web (abre el navegador automáticamente)
python3 main.py gui

# Iniciar en un puerto o host específico sin abrir navegador
python3 main.py gui --port 8080 --no-browser
```
> **Nota:** También puedes iniciar la interfaz gráfica desde el **Menú Interactivo en Terminal** (`python3 main.py` o `python3 main.py menu`) seleccionando la opción **`[G]`**.

### 🔹 Comando `teams` (Auditoría, Creación Asistida y Administración de Microsoft Teams)
Permite auditar el estado completo de todos los equipos del tenant en tiempo real, exportar reportes ejecutivos en Excel con 4 hojas formateadas, renombrar equipos y crear nuevas clases educativas con enrolamiento automático de alumnos:

```bash
# 1. Auditoría en tiempo real en consola (Conteo de equipos, ciclos, dueños y huérfanos)
python3 main.py teams audit

# 2. Generar y exportar libro Excel de auditoría consolidada (4 hojas de trabajo)
python3 main.py teams export
python3 main.py teams audit --export -o reports/Auditoria_Teams_Oficial.xlsx

# 3. Renombrar un equipo o clase en Microsoft Teams
python3 main.py teams rename --id "0bf824c9-c3d3-469b-83e9-74e68e4bf96f" --name "3er Semestre - Lengua y Comunicación"

# 4. Crear nueva clase educativa y enrolar alumnos automáticamente según base escolar
python3 main.py teams create \
  --subject "Lengua y Comunicación" \
  --nivel "Preparatoria" \
  --grado "3er Semestre" \
  --teacher "docente@ijova.com"
```

### 🔹 Comando `reset` (Reseteo Individual o Masivo de Contraseñas)
Restablece la contraseña de uno, varios o **todos los alumnos activos** para inicio de semestre, generando automáticamente nuevas contraseñas temporales y las fichas PDF con código QR listas para imprimir.

**Salvaguarda de Verificación:** Al restablecer de forma individual, el sistema primero verifica en tiempo real que la cuenta exista en Microsoft 365, cruza los datos con el archivo escolar y solicita confirmación expresa (`¿Confirmas que deseas restablecer la contraseña a este alumno? [s/N]`) antes de realizar cualquier cambio:
```bash
# Caso 1: Restablecer a UN alumno individual (con verificación previa y confirmación interactiva)
python3 main.py reset 250081

# Caso 2: Restablecer individualmente sin solicitar confirmación (modo desatendido/scripts)
python3 main.py reset 250081 -y

# Caso 3: Restablecer a TODOS los alumnos activos en Microsoft 365 (Inicio de Semestre)
python3 main.py reset --all

# Caso 4: Restablecer a un grupo desde un archivo Excel de matrículas
python3 main.py reset --excel "Alumnos_Secundaria.xlsx"
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
├── requirements.txt                # Dependencias tipadas (msal, requests, openpyxl, reportlab, qrcode, flask)
├── config.example.json             # Plantilla de configuración limpia
├── main.py                         # CLI principal con subcomandos
├── export_students_m365.py         # Extractor y generador de reporte consolidado de estudiantes
├── src/
│   ├── config.py                   # Carga de configuración y permisos 0700
│   ├── models.py                   # Modelos Pydantic y enums
│   ├── excel_parser.py             # Lector/escritor no destructivo de Excel
│   ├── validator.py                # Validador de reglas de integridad escolar
│   ├── normalizer.py               # Estandarizador de atributos de identidad
│   ├── password_generator.py       # Generador de contraseñas criptográficas seguras
│   ├── pdf_generator.py            # Generador de fichas y tarjetas PDF con código QR
│   ├── graph_client.py             # Cliente Microsoft Graph (Device Code, paginación, retries, Teams)
│   ├── sync_engine.py              # Motor de cruce estricto por UPN
│   ├── provisioner.py              # Motor de creación y licenciamiento A1
│   ├── enroll_engine.py            # Motor de alta interactiva extemporánea
│   ├── delete_engine.py            # Motor de baja con salvaguardas anti-admin
│   ├── historical_registry.py      # Gestor de bajas históricas y regla anti-reasignación
│   ├── reset_engine.py             # Motor de verificación previa y reseteo de contraseñas
│   ├── restore_engine.py           # Motor de restauración desde papelera de Entra ID
│   ├── status_engine.py            # Monitor ejecutivo de salud y licencias
│   ├── auditor.py                  # Generador de snapshots atómicos
│   ├── photo_auditor.py            # Auditoría y descarga concurrente de fotos de perfil
│   ├── teams_engine.py             # Auditoría concurrente, tipificación, Excel y creación de Teams
│   ├── report_generator.py         # Exportador de reportes CSV y resúmenes Markdown
│   └── gui/                        # Interfaz Gráfica Web Local (Dashboard)
│       ├── app.py                  # Servidor web local Flask y API REST
│       ├── templates/
│       │   └── index.html          # Panel web interactivo con buscador, fichas y Teams
│       └── static/
│           ├── css/style.css       # Estilos institucionales IJOVA y modo oscuro/claro
│           └── js/app.js           # Lógica cliente para verificación, confirmación y Teams
├── tests/
│   ├── test_teams_engine.py        # Suite de pruebas de auditoría y creación de Teams
│   ├── test_graph_client.py        # Suite de pruebas de Graph, reseteo y paginación
│   ├── test_photo_auditor.py       # Pruebas de auditoría de fotografías
│   └── test_reset_verification_and_gui.py # Pruebas de verificación previa y GUI
├── data/                           # Base de datos histórica y normalizada
├── backups/                        # Snapshots con timestamp (0700) [Excluido de Git]
├── reports/                        # Reportes CSV, PDFs y bitácoras [Excluido de Git]
└── secrets/                        # Archivos de contraseñas de entrega (0600) [Excluido de Git]
```

---

## 🧪 6. Ejecución de Pruebas Unitarias

La suite de pruebas automatizadas incluye **46 pruebas unitarias integrales** que validan la lógica de Graph API, paginación, reseteo seguro, auditoría de fotografías, escudo web contra ataques cibernéticos (DNS rebinding, CSRF, host header), y el motor de auditoría y matriculación de Microsoft Teams:

```bash
source .venv/bin/activate
python3 -m unittest discover tests
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.
