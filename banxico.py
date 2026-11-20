"""
Conexión a Banxico (SIE API, dato oportuno).
url es la puerta, el token es la llave.
Solo se usa la tasa de CETES a 28 días (serie SF43936).
"""
import os
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv
from fastapi import HTTPException
from pydantic import BaseModel

# El .env se busca junto a este archivo, sin depender de la carpeta desde la que se corra uvicorn.
# override=True evita que una variable vacía ya existente en la terminal tape el valor del .env.
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")

TOKEN = (os.getenv("TOKENBNX") or "").strip()
SERIE_CETES_28 = "SF43936"
URL_BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos/oportuno"


class DatoBanxico(BaseModel):
    serie: str
    titulo: str
    valor: float
    fecha: str


def consultar_serie(serie: str) -> DatoBanxico:
    """
    @consultar_serie: consulta el dato oportuno de una serie de Banxico.
    @serie: clave de la serie (ej. 'SF43936').
    Regresa el dato como DatoBanxico; si algo falla lanza HTTPException.
    """
    if not TOKEN:
        existe = ENV_PATH.exists()
        leidas = list(dotenv_values(ENV_PATH, encoding="utf-8-sig")) if existe else []
        raise HTTPException(
            500,
            f"Falta TOKENBNX en el archivo .env. Archivo buscado: {ENV_PATH} | "
            f"existe: {existe} | variables leídas: {leidas}",
        )

    headers = {"Bmx-Token": TOKEN}
    enlace = URL_BASE.format(serie=serie)
    try:
        response = requests.get(url=enlace, headers=headers, timeout=10)
        if response.status_code == 200:
            json_response = response.json()
            serie_json = json_response["bmx"]["series"][0]
            dato = serie_json["datos"][0]
            return DatoBanxico(
                serie=serie,
                titulo=serie_json.get("titulo", ""),
                valor=float(dato["dato"].replace(",", "")),  # "N/E" lanza ValueError
                fecha=dato["fecha"],
            )
        elif response.status_code == 404:
            raise HTTPException(404, f"Banxico no encontró la serie {serie}.")
        else:
            raise HTTPException(
                502, f"Banxico respondió con código {response.status_code}, revise su token."
            )
    except requests.exceptions.RequestException as error:
        raise HTTPException(502, f"No se pudo conectar con Banxico: {error}")
    except (KeyError, IndexError, ValueError, TypeError) as error:
        raise HTTPException(
            502,
            "La respuesta de Banxico no tiene el formato esperado "
            f"o el dato no es numérico: {error}",
        )


def Cetes() -> DatoBanxico:
    """
    @Cetes: consulta la tasa de interés de CETES a 28 días.
    Regresa el dato; `valor` viene en porcentaje (ej. 7.5 = 7.5%).
    """
    return consultar_serie(SERIE_CETES_28)


def interes_a_descuento(interes: float) -> float:
    """
    @interes_a_descuento: convierte una tasa de interés a tasa de descuento.
    d = i / (1 + i)
    @interes: tasa de interés en decimal (0.075 = 7.5%).
    Regresa la tasa de descuento en decimal.
    """
    return interes / (1 + interes)