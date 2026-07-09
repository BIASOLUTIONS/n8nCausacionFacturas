import os
import requests
from dotenv import load_dotenv


load_dotenv()


class SiigoClient:
    def __init__(self):
        self.enabled = os.getenv("SIIGO_ENABLED", "false").lower() == "true"
        self.base_url = os.getenv("SIIGO_BASE_URL", "https://api.siigo.com").rstrip("/")
        self.username = os.getenv("SIIGO_USERNAME", "")
        self.access_key = os.getenv("SIIGO_ACCESS_KEY", "")
        self.partner_id = os.getenv("SIIGO_PARTNER_ID", "")

        self._access_token = None

    def validar_configuracion(self):
        faltantes = []

        if not self.base_url:
            faltantes.append("SIIGO_BASE_URL")

        if not self.username:
            faltantes.append("SIIGO_USERNAME")

        if not self.access_key:
            faltantes.append("SIIGO_ACCESS_KEY")

        if not self.partner_id:
            faltantes.append("SIIGO_PARTNER_ID")

        if faltantes:
            raise ValueError(
                "Faltan variables de entorno SIIGO: " + ", ".join(faltantes)
            )

    def autenticar(self):
        self.validar_configuracion()

        url = f"{self.base_url}/auth"

        payload = {
            "username": self.username,
            "access_key": self.access_key
        }

        headers = {
            "Content-Type": "application/json",
            "Partner-Id": self.partner_id
        }

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code not in [200, 201]:
            raise Exception(
                f"Error autenticando en SIIGO. "
                f"Status={response.status_code}. "
                f"Respuesta={response.text}"
            )

        data = response.json()

        token = (
            data.get("access_token")
            or data.get("token")
            or data.get("accessToken")
        )

        if not token:
            raise Exception(
                f"SIIGO respondió correctamente, pero no se encontró access_token. Respuesta={data}"
            )

        self._access_token = token

        return {
            "ok": True,
            "mensaje": "Autenticación SIIGO exitosa.",
            "base_url": self.base_url,
            "partner_id": self.partner_id,
            "username": self.username,
            "token_recibido": True
        }

    def get_token(self):
        if not self._access_token:
            self.autenticar()

        return self._access_token

    def headers_autorizados(self):
        token = self.get_token()

        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "Partner-Id": self.partner_id
        }

    def get(self, endpoint: str, params: dict | None = None):
        self.validar_configuracion()

        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{self.base_url}{endpoint}"

        response = requests.get(
            url,
            headers=self.headers_autorizados(),
            params=params or {},
            timeout=30
        )

        if response.status_code not in [200, 201]:
            raise Exception(
                f"Error consultando SIIGO {endpoint}. "
                f"Status={response.status_code}. "
                f"Respuesta={response.text}"
            )

        return response.json()

    def post(self, endpoint: str, payload: dict):
        self.validar_configuracion()

        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{self.base_url}{endpoint}"

        response = requests.post(
            url,
            headers=self.headers_autorizados(),
            json=payload,
            timeout=30
        )

        if response.status_code not in [200, 201]:
            raise Exception(
                f"Error enviando a SIIGO {endpoint}. "
                f"Status={response.status_code}. "
                f"Respuesta={response.text}. "
                f"Payload={payload}"
            )

        return response.json()

    def consultar_tipos_documento_compra(self):
        return self.get("/v1/document-types", params={"type": "FC"})

    def consultar_medios_pago(self):
        return self.get("/v1/payment-types", params={"document_type": "FC"})

    def consultar_impuestos(self):
        return self.get("/v1/taxes")

    def consultar_centros_costo(self):
        return self.get("/v1/cost-centers")

    def consultar_catalogos_basicos(self):
        return {
            "tipos_documento_compra": self.consultar_tipos_documento_compra(),
            "medios_pago": self.consultar_medios_pago(),
            "impuestos": self.consultar_impuestos(),
            "centros_costo": self.consultar_centros_costo()
        }