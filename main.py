"""
MFAonline: matemáticas financieras con la tasa de CETES a 28 días de Banxico.
El usuario manda los datos en la URL (?parametro=valor) y la API calcula.
"""
import math
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from banxico import Cetes, interes_a_descuento

app = FastAPI(
    title="MFAonline",
    description=(
        "Matemáticas financieras. El usuario envía los datos en la URL; "
        "la tasa de interés (CETES 28 días, serie SF43936) se obtiene de Banxico."
    ),
    version="1.0.0",
)

# Validación de los parámetros de la URL (Pydantic a través de Query)
Positivo = Annotated[float, Query(gt=0)]
NoNegativo = Annotated[float, Query(ge=0)]
Periodos = Annotated[int, Query(gt=0)]


class TipoTasa(str, Enum):
    interes = "i"
    descuento = "d"


# ---------------------------------------------------------------------------
# Modelos de respuesta
# ---------------------------------------------------------------------------
class BaseOut(BaseModel):
    formula: str
    tasa_cetes_28_pct: float
    fecha_tasa: str


class InteresSimpleOut(BaseOut):
    interes: float
    monto: float


class PerpetuidadOut(BaseOut):
    tipo_tasa: str
    tasa_usada_pct: float
    valor_presente: float


class AnualidadGeometricaOut(BaseOut):
    valor_presente: float


class DescuentoSimpleOut(BaseOut):
    tasa_descuento_pct: float
    descuento: float
    valor_presente: float


# ---------------------------------------------------------------------------
# Inicio
# ---------------------------------------------------------------------------
@app.get("/", tags=["Inicio"])
def home():
    return {
        "mensaje": "Hola, bienvenid@ a MFAonline. Mande los datos en la URL y se calcula.",
        "documentacion": "/docs",
        "ejemplos": {
            "interes_simple": "/calcular/interes-simple?capital=1000&tiempo_anios=2",
            "perpetuidad_vencida": "/calcular/perpetuidad-vencida?pago=500&tipo_tasa=i",
            "anualidad_vencida_geometrica": "/calcular/anualidad-vencida-geometrica?primer_pago=100&crecimiento_pct=5&periodos=3",
            "anualidad_anticipada_geometrica": "/calcular/anualidad-anticipada-geometrica?primer_pago=100&crecimiento_pct=5&periodos=3",
            "descuento_simple": "/calcular/descuento-simple?valor_futuro=1000&tiempo_anios=0.5",
        },
    }


# ---------------------------------------------------------------------------
# 1. Interés simple
# ---------------------------------------------------------------------------
@app.get("/calcular/interes-simple", response_model=InteresSimpleOut, tags=["Cálculos"],
         summary="Interés simple: M = C(1 + i·t)")
def calcular_interes_simple(capital: Positivo, tiempo_anios: Positivo):
    """
    - **capital**: monto inicial invertido (C).
    - **tiempo_anios**: tiempo en años (t).

    La tasa de interés (i) se obtiene de CETES a 28 días en Banxico.
    """
    cetes = Cetes()
    i = cetes.valor / 100

    monto = capital * (1 + i * tiempo_anios)
    interes = monto - capital

    return InteresSimpleOut(
        formula="M = C(1 + i·t)",
        tasa_cetes_28_pct=cetes.valor,
        fecha_tasa=cetes.fecha,
        interes=round(interes, 2),
        monto=round(monto, 2),
    )


# ---------------------------------------------------------------------------
# 2. Perpetuidad vencida
# ---------------------------------------------------------------------------
@app.get("/calcular/perpetuidad-vencida", response_model=PerpetuidadOut, tags=["Cálculos"],
         summary="Perpetuidad vencida: VP = R / i  o  VP = R·(1-d)/d")
def calcular_perpetuidad_vencida(pago: Positivo, tipo_tasa: TipoTasa = TipoTasa.interes):
    """
    - **pago**: pago periódico (R), anual porque la tasa de CETES es anual.
    - **tipo_tasa**: `i` calcula con la tasa de interés; `d` la convierte a descuento
      con d = i / (1 + i). Ambos dan el mismo resultado.
    """
    cetes = Cetes()
    i = cetes.valor / 100
    if i <= 0:
        raise HTTPException(422, "La tasa de CETES debe ser mayor que cero.")

    if tipo_tasa == TipoTasa.interes:
        tasa_usada = i
        vp = pago / i
    else:
        tasa_usada = interes_a_descuento(i)
        vp = pago * ((1 - tasa_usada) / tasa_usada)

    return PerpetuidadOut(
        formula="VP = R / i" if tipo_tasa == TipoTasa.interes else "VP = R·(1-d)/d",
        tasa_cetes_28_pct=cetes.valor,
        fecha_tasa=cetes.fecha,
        tipo_tasa=tipo_tasa.value,
        tasa_usada_pct=round(tasa_usada * 100, 4),
        valor_presente=round(vp, 2),
    )


# ---------------------------------------------------------------------------
# 3. Anualidad vencida geométrica
# ---------------------------------------------------------------------------
@app.get("/calcular/anualidad-vencida-geometrica", response_model=AnualidadGeometricaOut,
         tags=["Cálculos"], summary="Anualidad vencida geométrica (valor presente)")
def calcular_anualidad_vencida_geometrica(
    primer_pago: Positivo, crecimiento_pct: NoNegativo, periodos: Periodos
):
    """
    - **primer_pago**: primer pago (R).
    - **crecimiento_pct**: crecimiento de los pagos en porcentaje (g).
    - **periodos**: número de periodos (n), en años.

    La tasa de interés (i) se obtiene de CETES a 28 días en Banxico.
    """
    cetes = Cetes()
    i = cetes.valor / 100
    g = crecimiento_pct / 100

    if math.isclose(i, g):
        vp = (primer_pago * periodos) / (1 + i)
    else:
        vp = (primer_pago / (i - g)) * (1 - ((1 + g) / (1 + i)) ** periodos)

    return AnualidadGeometricaOut(
        formula="VP = R/(i-g) · [1 - ((1+g)/(1+i))^n]",
        tasa_cetes_28_pct=cetes.valor,
        fecha_tasa=cetes.fecha,
        valor_presente=round(vp, 2),
    )


# ---------------------------------------------------------------------------
# 4. Anualidad anticipada geométrica
# ---------------------------------------------------------------------------
@app.get("/calcular/anualidad-anticipada-geometrica", response_model=AnualidadGeometricaOut,
         tags=["Cálculos"], summary="Anualidad anticipada geométrica (valor presente)")
def calcular_anualidad_anticipada_geometrica(
    primer_pago: Positivo, crecimiento_pct: NoNegativo, periodos: Periodos
):
    """
    Igual que la vencida, multiplicada por (1 + i) porque los pagos van al inicio.

    - **primer_pago**: primer pago (R).
    - **crecimiento_pct**: crecimiento de los pagos en porcentaje (g).
    - **periodos**: número de periodos (n), en años.
    """
    cetes = Cetes()
    i = cetes.valor / 100
    g = crecimiento_pct / 100

    if math.isclose(i, g):
        vp = (primer_pago * periodos) / (1 + i)
    else:
        vp = (primer_pago / (i - g)) * (1 - ((1 + g) / (1 + i)) ** periodos)

    vp = vp * (1 + i)  # pagos al inicio de cada periodo

    return AnualidadGeometricaOut(
        formula="VP = (1+i) · R/(i-g) · [1 - ((1+g)/(1+i))^n]",
        tasa_cetes_28_pct=cetes.valor,
        fecha_tasa=cetes.fecha,
        valor_presente=round(vp, 2),
    )


# ---------------------------------------------------------------------------
# 5. Descuento simple
# ---------------------------------------------------------------------------
@app.get("/calcular/descuento-simple", response_model=DescuentoSimpleOut, tags=["Cálculos"],
         summary="Descuento simple: VP = VF(1 - d·t)")
def calcular_descuento_simple(valor_futuro: Positivo, tiempo_anios: Positivo):
    """
    - **valor_futuro**: monto futuro de la operación (VF).
    - **tiempo_anios**: tiempo en años (t).

    La tasa de descuento (d) se obtiene de CETES a 28 días convertida con d = i / (1 + i).
    """
    cetes = Cetes()
    i = cetes.valor / 100
    d = interes_a_descuento(i)

    descuento = valor_futuro * d * tiempo_anios
    vp = valor_futuro - descuento
    if vp <= 0:
        raise HTTPException(422, "El descuento no puede ser igual o mayor al valor futuro.")

    return DescuentoSimpleOut(
        formula="VP = VF(1 - d·t)",
        tasa_cetes_28_pct=cetes.valor,
        fecha_tasa=cetes.fecha,
        tasa_descuento_pct=round(d * 100, 4),
        descuento=round(descuento, 2),
        valor_presente=round(vp, 2),
    )