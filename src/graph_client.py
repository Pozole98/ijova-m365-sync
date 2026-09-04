"""
Cliente de Microsoft Graph API para Linux utilizando MSAL Python y el principio de mínimo privilegio.
Implementa Device Code Flow, paginación completa exhaustiva (@odata.nextLink) y reintentos con backoff.
"""
import os
import time
import requests
from typing import List, Dict, Any, Optional
from msal import PublicClientApplication, SerializableTokenCache
from src.models import EntraUser, DomainStatus


class GraphClientError(Exception):
    """Excepción para errores críticos de comunicación con Microsoft Graph."""
    pass


class GraphClient:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        scopes: List[str],
        cache_path: Optional[str] = "secrets/token_cache.bin"
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.scopes = scopes
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.cache_path = cache_path
        self.cache: Optional[SerializableTokenCache] = None

        if self.cache_path:
            self.cache = SerializableTokenCache()
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        self.cache.deserialize(f.read())
                except Exception:
                    pass

        self.app = PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            token_cache=self.cache
        )
        self.access_token: Optional[str] = None
        self.admin_upn: Optional[str] = None

    def _save_cache(self):
        """Guarda el estado del token cache en disco con permisos seguros 0600."""
        if self.cache and self.cache.has_state_changed and self.cache_path:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.cache_path)), exist_ok=True)
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    f.write(self.cache.serialize())
                try:
                    os.chmod(self.cache_path, 0o600)
                except Exception:
                    pass
            except Exception:
                pass

    def clear_session_cache(self):
        """Elimina el caché de tokens para forzar un nuevo inicio de sesión interactivo."""
        if self.cache_path and os.path.exists(self.cache_path):
            try:
                os.remove(self.cache_path)
            except Exception:
                pass
        self.access_token = None
        self.admin_upn = None

    def authenticate_device_code(self) -> str:
        """
        Inicia el flujo Device Code Flow para autenticación interactiva segura en terminal Linux.
        Muestra la URL y el código al operador y captura la identidad del administrador.
        """
        # First attempt silent token acquisition from cache
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
            if result and "access_token" in result:
                self.access_token = result["access_token"]
                self.admin_upn = accounts[0].get("username")
                self._save_cache()
                print(f"⚡ Sesión restaurada desde caché seguro. Administrador: \033[1;32m{self.admin_upn or 'Identificado'}\033[0m")
                return self.access_token

        # Initiate Device Code Flow
        flow = self.app.initiate_device_flow(scopes=self.scopes)
        if "user_code" not in flow:
            raise GraphClientError(f"Fallo al iniciar Device Code Flow: {flow.get('error_description', flow)}")

        print("\n" + "=" * 70)
        print("🔐 AUTENTICACIÓN REQUERIDA EN MICROSOFT ENTRA ID")
        print("=" * 70)
        print(f"1. Abre tu navegador e ingresa a:  \033[1;34m{flow['verification_uri']}\033[0m")
        print(f"2. Introduce el siguiente código:   \033[1;32m{flow['user_code']}\033[0m")
        print("3. Inicia sesión con tu cuenta de administrador de Microsoft 365.")
        print("=" * 70)
        print("Esperando autorización del administrador en el navegador...\n")

        result = self.app.acquire_token_by_device_flow(flow)
        if "access_token" in result:
            self.access_token = result["access_token"]
            # Extract admin UPN from id_token_claims or accounts
            id_claims = result.get("id_token_claims", {})
            self.admin_upn = (
                id_claims.get("preferred_username") or
                id_claims.get("upn") or
                id_claims.get("email")
            )
            if not self.admin_upn:
                accounts = self.app.get_accounts()
                if accounts:
                    self.admin_upn = accounts[0].get("username")
            self._save_cache()
            print(f"✅ Autenticación exitosa. Administrador identificado: \033[1;32m{self.admin_upn or 'Desconocido'}\033[0m")
            return self.access_token
        else:
            raise GraphClientError(f"Error de autenticación: {result.get('error_description', result.get('error'))}")

    def _request_with_retry(self, url: str, max_retries: int = 4) -> Dict[str, Any]:
        """
        Ejecuta una petición GET a Graph con reintentos para HTTP 429 y errores 5xx.
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible. Ejecute authenticate_device_code() primero.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "ConsistencyLevel": "eventual"
        }

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=30)

                # Rate limiting (HTTP 429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", attempt * 3))
                    print(f"⚠️ Microsoft Graph Rate Limit (429). Esperando {retry_after}s antes de reintentar (Intento {attempt}/{max_retries})...")
                    time.sleep(retry_after)
                    continue

                # Temporary server errors (5xx)
                if 500 <= response.status_code < 600:
                    wait_time = attempt * 2
                    print(f"⚠️ Error temporal de Graph ({response.status_code}). Esperando {wait_time}s (Intento {attempt}/{max_retries})...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    raise GraphClientError(f"Fallo de conexión no recuperable con Microsoft Graph: {e}")
                time.sleep(attempt * 2)

        raise GraphClientError(f"Petición fallida tras {max_retries} intentos: {url}")

    def verify_domain(self, domain_name: str) -> DomainStatus:
        """
        Verifica el estado del dominio en Microsoft Entra ID (/v1.0/domains).
        """
        url = "https://graph.microsoft.com/v1.0/domains"
        data = self._request_with_retry(url)

        for d in data.get("value", []):
            if d.get("id", "").lower() == domain_name.lower():
                is_verified = d.get("isVerified", False)
                is_default = d.get("isDefault", False)
                auth_type = d.get("authenticationType", "Managed")

                is_blocked = not is_verified
                block_reason = None
                if not is_verified:
                    block_reason = f"El dominio '{domain_name}' no está verificado en el tenant de Microsoft 365."

                return DomainStatus(
                    domain_name=domain_name,
                    is_verified=is_verified,
                    is_default=is_default,
                    authentication_type=auth_type,
                    is_blocked=is_blocked,
                    block_reason=block_reason
                )

        return DomainStatus(
            domain_name=domain_name,
            is_verified=False,
            is_default=False,
            authentication_type="Unknown",
            is_blocked=True,
            block_reason=f"El dominio '{domain_name}' no existe en el tenant."
        )

    def get_all_users(self) -> List[EntraUser]:
        """
        Descarga todos los usuarios del tenant con paginación exhaustiva (@odata.nextLink).
        Si la paginación se interrumpe, lanza una excepción fatal para evitar clasificaciones incorrectas.
        """
        url = (
            "https://graph.microsoft.com/v1.0/users"
            "?$select=id,userPrincipalName,displayName,givenName,surname,accountEnabled,mail,mailNickname,userType"
            "&$top=999"
        )

        all_users: List[EntraUser] = []
        page_count = 0

        while url:
            page_count += 1
            print(f"   📄 Consultando página {page_count} de usuarios de Entra ID...")
            data = self._request_with_retry(url)

            users_data = data.get("value", [])
            for u in users_data:
                all_users.append(EntraUser(
                    id=u.get("id", ""),
                    user_principal_name=u.get("userPrincipalName", "").strip().lower(),
                    display_name=u.get("displayName"),
                    given_name=u.get("givenName"),
                    surname=u.get("surname"),
                    account_enabled=u.get("accountEnabled"),
                    mail=u.get("mail"),
                    mail_nickname=u.get("mailNickname"),
                    user_type=u.get("userType")
                ))

            print(f"   ✅ Página {page_count}: {len(users_data)} usuarios procesados exitosamente.")
            # Follow next page link
            url = data.get("@odata.nextLink")

        print(f"\n📊 RESUMEN DE DESCARGA DE GRAPH:")
        print(f"   - Total de páginas descargadas: {page_count}")
        print(f"   - Total de usuarios recuperados de Entra ID: {len(all_users)}")
        print(f"   - Estado de paginación: Completada al 100% (@odata.nextLink finalizado sin interrupciones)\n")
        return all_users

    def get_subscribed_skus(self) -> List[Dict[str, Any]]:
        """
        Consulta las licencias disponibles en el tenant (/v1.0/subscribedSkus).
        """
        url = "https://graph.microsoft.com/v1.0/subscribedSkus"
        data = self._request_with_retry(url)
        return data.get("value", [])

    def find_student_sku(self) -> Optional[Dict[str, Any]]:
        """
        Identifica el SKU de Office 365 A1 for Students / Education disponible en el tenant.
        """
        skus = self.get_subscribed_skus()
        # Search for student skus
        student_skus = []
        for s in skus:
            part_number = s.get("skuPartNumber", "").upper()
            prepaid = s.get("prepaidUnits", {}).get("enabled", 0)
            consumed = s.get("consumedUnits", 0)
            available = prepaid - consumed

            if "STUDENT" in part_number or "A1" in part_number or "STANDARDWOFFPACK" in part_number:
                student_skus.append({
                    "skuId": s.get("skuId"),
                    "skuPartNumber": part_number,
                    "available": available,
                    "consumed": consumed,
                    "total": prepaid
                })

        if student_skus:
            # Pick the one with available units or the main student sku
            student_skus.sort(key=lambda x: x["available"], reverse=True)
            return student_skus[0]

        # Fallback to any sku with available licenses
        for s in skus:
            prepaid = s.get("prepaidUnits", {}).get("enabled", 0)
            consumed = s.get("consumedUnits", 0)
            if prepaid - consumed > 0:
                return {
                    "skuId": s.get("skuId"),
                    "skuPartNumber": s.get("skuPartNumber"),
                    "available": prepaid - consumed,
                    "consumed": consumed,
                    "total": prepaid
                }

        return None

    def get_user_by_upn(self, upn: str) -> Optional[Dict[str, Any]]:
        """
        Consulta en tiempo real un usuario específico por su UPN (salvaguarda anti-drift).
        Retorna el diccionario del usuario si existe o None si no existe (HTTP 404).
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        url = f"https://graph.microsoft.com/v1.0/users/{upn.strip().lower()}?$select=id,userPrincipalName,displayName,accountEnabled"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 404:
                return None
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                time.sleep(retry_after)
                return self.get_user_by_upn(upn)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise GraphClientError(f"Error al verificar usuario {upn}: {e}")

        return None

    def create_user(self, payload: Dict[str, Any], max_retries: int = 4) -> Dict[str, Any]:
        """
        Crea un nuevo usuario en Microsoft Entra ID vía POST /v1.0/users con reintentos para 429/5xx.
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        url = "https://graph.microsoft.com/v1.0/users"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=30)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", attempt * 3))
                    print(f"⚠️ Rate limit en creación. Esperando {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                if 500 <= resp.status_code < 600:
                    time.sleep(attempt * 2)
                    continue

                if resp.status_code == 201:
                    return resp.json()

                # If already exists (409 Conflict)
                if resp.status_code == 409:
                    print(f"ℹ️ El usuario {payload.get('userPrincipalName')} ya existía en Entra ID (HTTP 409 Conflict).")
                    existing = self.get_user_by_upn(payload.get('userPrincipalName'))
                    if existing:
                        return existing

                resp.raise_for_status()

            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    raise GraphClientError(f"Fallo al crear usuario {payload.get('userPrincipalName')}: {e}")
                time.sleep(attempt * 2)

        raise GraphClientError(f"Fallo al crear usuario tras {max_retries} intentos: {payload.get('userPrincipalName')}")

    def assign_license(self, user_id: str, sku_id: str, max_retries: int = 3) -> bool:
        """
        Asigna una licencia al usuario vía POST /v1.0/users/{user_id}/assignLicense.
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        url = f"https://graph.microsoft.com/v1.0/users/{user_id}/assignLicense"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        body = {
            "addLicenses": [{"skuId": sku_id}],
            "removeLicenses": []
        }

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=body, timeout=25)

                if resp.status_code in [200, 204]:
                    return True

                if resp.status_code == 429:
                    time.sleep(int(resp.headers.get("Retry-After", 2)))
                    continue

                if resp.status_code == 400 and "licenseAlreadyAssigned" in resp.text:
                    return True

                resp.raise_for_status()

            except Exception as e:
                if attempt == max_retries:
                    print(f"⚠️ No se pudo asignar licencia a usuario {user_id}: {e}")
                    return False
                time.sleep(attempt * 2)

        return False

    def delete_user(self, user_id: str, max_retries: int = 3) -> bool:
        """
        Elimina un usuario en Microsoft Entra ID vía DELETE /v1.0/users/{user_id}.
        Envía la cuenta a la papelera de reciclaje de Entra ID (Soft Delete, retención de 30 días).
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.delete(url, headers=headers, timeout=25)

                if resp.status_code in [200, 204]:
                    return True

                if resp.status_code == 404:
                    # User already deleted or does not exist
                    return True

                if resp.status_code == 429:
                    time.sleep(int(resp.headers.get("Retry-After", 2)))
                    continue

                if 500 <= resp.status_code < 600:
                    time.sleep(attempt * 2)
                    continue

                resp.raise_for_status()

            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    raise GraphClientError(f"Fallo al eliminar usuario {user_id}: {e}")
                time.sleep(attempt * 2)

        return False

    def reset_password(self, user_id: str, new_password: str, max_retries: int = 3) -> bool:
        """
        Restablece la contraseña de un usuario en Microsoft Entra ID vía PATCH /v1.0/users/{user_id}.
        Forza el cambio de contraseña en el próximo inicio de sesión.
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": new_password
            }
        }

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.patch(url, headers=headers, json=payload, timeout=25)

                if resp.status_code in [200, 204]:
                    return True

                if resp.status_code == 429:
                    time.sleep(int(resp.headers.get("Retry-After", 2)))
                    continue

                if 500 <= resp.status_code < 600:
                    time.sleep(attempt * 2)
                    continue

                resp.raise_for_status()

            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    raise GraphClientError(f"Fallo al restablecer contraseña de {user_id}: {e}")
                time.sleep(attempt * 2)

        return False

    def get_deleted_users(self) -> List[Dict[str, Any]]:
        """
        Consulta los usuarios en la papelera de reciclaje de Microsoft Entra ID (/v1.0/directory/deletedItems/microsoft.graph.user).
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        url = "https://graph.microsoft.com/v1.0/directory/deletedItems/microsoft.graph.user?$select=id,userPrincipalName,displayName,deletedDateTime,mailNickname"
        deleted_users = []

        while url:
            data = self._request_with_retry(url)
            users_chunk = data.get("value", [])
            deleted_users.extend(users_chunk)
            url = data.get("@odata.nextLink")

        return deleted_users

    def restore_deleted_user(self, user_id: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Restaura un usuario desde la papelera de reciclaje vía POST /v1.0/directory/deletedItems/{user_id}/restore.
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        url = f"https://graph.microsoft.com/v1.0/directory/deletedItems/{user_id}/restore"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json={}, timeout=25)

                if resp.status_code in [200, 201]:
                    return resp.json()

                if resp.status_code == 429:
                    time.sleep(int(resp.headers.get("Retry-After", 2)))
                    continue

                if 500 <= resp.status_code < 600:
                    time.sleep(attempt * 2)
                    continue

                resp.raise_for_status()

            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    raise GraphClientError(f"Fallo al restaurar usuario {user_id}: {e}")
                time.sleep(attempt * 2)

        raise GraphClientError(f"Fallo al restaurar usuario tras {max_retries} intentos: {user_id}")

    def execute_batch(self, subrequests: List[Dict[str, Any]], max_retries: int = 4) -> List[Dict[str, Any]]:
        """
        Ejecuta múltiples operaciones en lotes utilizando el endpoint POST /v1.0/$batch de Microsoft Graph.
        Fragmenta automáticamente las peticiones en bloques de hasta 20 operaciones concurrentes.
        """
        if not self.access_token:
            raise GraphClientError("No hay token de acceso disponible.")

        batch_url = "https://graph.microsoft.com/v1.0/$batch"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        all_responses: List[Dict[str, Any]] = []

        # Fragmentar en bloques de máximo 20 peticiones permitidas por Graph
        chunk_size = 20
        for i in range(0, len(subrequests), chunk_size):
            chunk = subrequests[i:i + chunk_size]
            payload = {"requests": chunk}

            for attempt in range(1, max_retries + 1):
                try:
                    resp = requests.post(batch_url, headers=headers, json=payload, timeout=45)

                    if resp.status_code == 401:
                        accounts = self.app.get_accounts()
                        if accounts:
                            r = self.app.acquire_token_silent(self.scopes, account=accounts[0])
                            if r and "access_token" in r:
                                self.access_token = r["access_token"]
                                headers["Authorization"] = f"Bearer {self.access_token}"
                                self._save_cache()
                                resp = requests.post(batch_url, headers=headers, json=payload, timeout=45)

                    if resp.status_code == 429:
                        wait_sec = int(resp.headers.get("Retry-After", attempt * 3))
                        time.sleep(wait_sec)
                        continue

                    if 500 <= resp.status_code < 600:
                        time.sleep(attempt * 2)
                        continue

                    resp.raise_for_status()
                    data = resp.json()
                    chunk_responses = data.get("responses", [])
                    all_responses.extend(chunk_responses)
                    break

                except requests.exceptions.RequestException as e:
                    if attempt == max_retries:
                        raise GraphClientError(f"Error en ejecución de lote $batch de Graph: {e}")
                    time.sleep(attempt * 2)

        return all_responses

    def batch_reset_passwords(self, students_reset_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Restablece contraseñas de múltiples alumnos en lote acelerado vía $batch.
        :param students_reset_list: Lista de dicts con claves: id, matricula, upn, new_password
        :return: Dict con métricas: total, success_count, failed_count, successes, failures
        """
        subrequests = []
        id_to_student = {}
        for idx, s in enumerate(students_reset_list, start=1):
            req_id = str(idx)
            id_to_student[req_id] = s
            subrequests.append({
                "id": req_id,
                "method": "PATCH",
                "url": f"/users/{s['id']}",
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": {
                    "passwordProfile": {
                        "forceChangePasswordNextSignIn": True,
                        "password": s["new_password"]
                    }
                }
            })

        batch_responses = self.execute_batch(subrequests)
        resp_map = {str(r.get("id")): r for r in batch_responses}

        successes = []
        failures = []

        for req_id, student in id_to_student.items():
            r = resp_map.get(req_id)
            status_code = r.get("status", 500) if r else 500
            if status_code in [200, 204]:
                successes.append({
                    "student": student,
                    "status_code": status_code
                })
            else:
                error_body = r.get("body", {}) if r else {"error": "Sin respuesta en batch"}
                failures.append({
                    "student": student,
                    "status_code": status_code,
                    "error": error_body
                })

        return {
            "total": len(students_reset_list),
            "success_count": len(successes),
            "failed_count": len(failures),
            "successes": successes,
            "failures": failures
        }
