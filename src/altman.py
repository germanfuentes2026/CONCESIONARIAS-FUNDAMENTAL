"""Altman Z'' (1995) para empresas que no cotizan y no son manufactureras, con variante EM.

Por qué Z'' y no el Z original para una concesionaria vial que no cotiza:
  · No hay precio de mercado → X4 usa patrimonio neto contable / pasivo total.
  · Se elimina X5 (ventas / activo): una concesión es intensiva en activos de larga vida y
    tiene rotación estructuralmente baja; X5 la castigaría por su modelo de negocio, no por su riesgo.
  · Variante Z''-EM (Altman, 2005): suma 3,25 para anclar el score a calificaciones de bonos
    de mercados emergentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import derived, div, num

WEIGHTS = {"X1": 6.56, "X2": 3.26, "X3": 6.72, "X4": 1.05}
EM_CONSTANT = 3.25

# Equivalencia indicativa EM Score → calificación (Altman, 2005)
EM_RATING_TABLE = [
    (8.15, "AAA"), (7.60, "AA+"), (7.30, "AA"), (7.00, "AA-"), (6.85, "A+"), (6.65, "A"),
    (6.40, "A-"), (6.25, "BBB+"), (5.85, "BBB"), (5.65, "BBB-"), (5.25, "BB+"), (4.95, "BB"),
    (4.75, "BB-"), (4.50, "B+"), (4.15, "B"), (3.75, "B-"), (3.20, "CCC+"), (2.50, "CCC"),
    (1.75, "CCC-"),
]


@dataclass
class Component:
    code: str
    name: str
    weight: float
    value: float | None
    contribution: float | None
    formula: str
    latex: str
    explanation: str
    inputs: dict = field(default_factory=dict)


@dataclass
class AltmanResult:
    z: float | None
    zone: str
    zone_detail: str
    variant: str
    year: str | None
    components: list[Component]
    missing: list[str]
    rating: str | None = None


def cutoffs(variant: str) -> tuple[float, float]:
    """(límite distress, límite safe)."""
    if variant == "EM":
        return 4.35, 5.85
    return 1.10, 2.60


def em_rating(z_em: float | None) -> str | None:
    if z_em is None:
        return None
    for lim, rating in EM_RATING_TABLE:
        if z_em >= lim:
            return rating
    return "D"


def compute_altman(years: dict, year: str, variant: str = "Z2") -> AltmanResult:
    y = years.get(year, {})
    d = derived(y)
    g = lambda k: num(y.get(k))  # noqa: E731
    at = g("activo_total")

    comps = [
        Component(
            "X1", "Capital de trabajo / Activo total", WEIGHTS["X1"],
            div(d["capital_trabajo"], at), None,
            "X1 = (Activo corriente − Pasivo corriente) / Activo total",
            r"X_1 = \frac{AC - PC}{AT}",
            "Liquidez de corto plazo relativa al tamaño. En concesiones suele ser baja o negativa "
            "porque la caja se aplica a obras y servicio de deuda; un X1 muy negativo indica "
            "dependencia de refinanciación.",
            {"activo_corriente": g("activo_corriente"), "pasivo_corriente": g("pasivo_corriente"),
             "activo_total": at},
        ),
        Component(
            "X2", "Resultados acumulados / Activo total", WEIGHTS["X2"],
            div(g("resultados_acumulados"), at), None,
            "X2 = Resultados acumulados / Activo total",
            r"X_2 = \frac{RA}{AT}",
            "Rentabilidad histórica retenida. Mide cuánto del activo fue financiado con ganancias "
            "propias en lugar de deuda o aportes. Cargar en moneda homogénea (RT 6 / NIC 29).",
            {"resultados_acumulados": g("resultados_acumulados"), "activo_total": at},
        ),
        Component(
            "X3", "EBIT / Activo total", WEIGHTS["X3"],
            div(g("ebit"), at), None,
            "X3 = Resultado operativo (EBIT) / Activo total",
            r"X_3 = \frac{EBIT}{AT}",
            "Productividad operativa del activo concesionado, antes de intereses e impuestos. "
            "Es el factor de mayor peso.",
            {"ebit": g("ebit"), "activo_total": at},
        ),
        Component(
            "X4", "Patrimonio neto contable / Pasivo total", WEIGHTS["X4"],
            div(g("patrimonio_neto"), g("pasivo_total")), None,
            "X4 = Patrimonio neto (valor libros) / Pasivo total",
            r"X_4 = \frac{PN_{libros}}{PT}",
            "Colchón patrimonial frente a los acreedores. Reemplaza el valor de mercado del Z "
            "original porque la empresa no cotiza.",
            {"patrimonio_neto": g("patrimonio_neto"), "pasivo_total": g("pasivo_total")},
        ),
    ]
    missing = []
    for c in comps:
        if c.value is None:
            missing.append(c.code)
        else:
            c.contribution = c.weight * c.value

    lo, hi = cutoffs(variant)
    variant_name = "Z''-EM (Altman, 2005)" if variant == "EM" else "Z'' (Altman, 1995)"
    if missing:
        return AltmanResult(None, "N/A", "Faltan datos para calcular el score.", variant_name,
                            year, comps, missing)

    z = sum(c.contribution for c in comps) + (EM_CONSTANT if variant == "EM" else 0.0)
    if z > hi:
        zone, detail = "SEGURA", f"Z > {hi:.2f}: baja probabilidad de insolvencia."
    elif z >= lo:
        zone, detail = "GRIS", f"{lo:.2f} ≤ Z ≤ {hi:.2f}: zona de incertidumbre, monitorear."
    else:
        zone, detail = "RIESGO", f"Z < {lo:.2f}: perfil compatible con estrés financiero."
    z_em = z if variant == "EM" else z + EM_CONSTANT
    return AltmanResult(z, zone, detail, variant_name, year, comps, [], em_rating(z_em))
