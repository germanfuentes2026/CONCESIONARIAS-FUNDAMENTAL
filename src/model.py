"""Modelo de datos de una concesionaria vial: campos de carga manual y métricas derivadas."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    section: str
    help: str = ""


SECTIONS = [
    "ESTADO DE SITUACIÓN PATRIMONIAL",
    "ESTADO DE RESULTADOS",
    "FLUJO DE EFECTIVO Y DEUDA",
    "DATOS OPERATIVOS",
]

FIELDS: list[Field] = [
    # ── Balance
    Field("caja", "Efectivo e inversiones corrientes", SECTIONS[0], "Caja, bancos y colocaciones de corto plazo."),
    Field("activo_corriente", "Activo corriente", SECTIONS[0]),
    Field("activo_concesion", "Activo de concesión (intangible / bienes afectados)", SECTIONS[0],
          "Derecho de concesión bajo CINIIF 12 o bienes afectados a la concesión."),
    Field("activo_total", "Activo total", SECTIONS[0]),
    Field("pasivo_corriente", "Pasivo corriente", SECTIONS[0]),
    Field("deuda_cp", "Deuda financiera corriente", SECTIONS[0], "Préstamos, ON y leasing con vencimiento < 12 meses."),
    Field("deuda_lp", "Deuda financiera no corriente", SECTIONS[0]),
    Field("pasivo_total", "Pasivo total", SECTIONS[0]),
    Field("resultados_acumulados", "Resultados acumulados (no asignados + reservas de ganancias)", SECTIONS[0],
          "Ganancias retenidas. Excluye capital, ajuste de capital y aportes."),
    Field("patrimonio_neto", "Patrimonio neto", SECTIONS[0]),
    # ── Resultados
    Field("ingresos_peaje", "Ingresos por peaje", SECTIONS[1]),
    Field("otros_ingresos", "Otros ingresos operativos (áreas de servicio, publicidad, compensaciones)", SECTIONS[1]),
    Field("ingresos_construccion", "Ingresos por construcción (CINIIF 12)", SECTIONS[1],
          "Se excluyen de los ingresos operativos: tienen margen ~0 y distorsionan los ratios."),
    Field("ebit", "Resultado operativo (EBIT)", SECTIONS[1]),
    Field("amortizaciones", "Depreciaciones y amortizaciones", SECTIONS[1]),
    Field("intereses", "Intereses financieros", SECTIONS[1], "Intereses de la deuda (devengados o pagados), en positivo."),
    Field("resultado_neto", "Resultado neto del ejercicio", SECTIONS[1]),
    # ── Flujos y deuda
    Field("cfo", "Flujo neto de actividades operativas", SECTIONS[2]),
    Field("capex", "Inversiones en obras (capex total)", SECTIONS[2], "En positivo."),
    Field("capex_mant", "Capex de mantenimiento / mantenimiento mayor", SECTIONS[2],
          "Parte del capex necesaria para sostener el servicio. En positivo."),
    Field("impuestos_pagados", "Impuesto a las ganancias pagado", SECTIONS[2], "En positivo."),
    Field("capital_amortizado", "Amortización de capital de deuda pagada", SECTIONS[2], "En positivo."),
    # ── Operativo
    Field("transito", "Tránsito pagante anual (vehículos equivalentes)", SECTIONS[3]),
    Field("km", "Kilómetros concesionados", SECTIONS[3]),
    Field("anios_restantes", "Años remanentes de concesión (al cierre)", SECTIONS[3]),
]

FIELD_BY_KEY = {f.key: f for f in FIELDS}
LABEL_TO_KEY = {f.label: f.key for f in FIELDS}
NON_MONETARY = {"transito", "km", "anios_restantes"}


def num(v):
    """Convierte a float; None/NaN/'' -> None."""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().replace(" ", "").replace("$", "")
        if s in ("", "-", "—"):
            return None
        neg = s.startswith("(") and s.endswith(")")
        s = s.strip("()")
        if "," in s and "." in s:   # 1.234.567,89  o  1,234,567.89
            s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
        elif s.count(".") > 1:
            s = s.replace(".", "")
        v = "-" + s if neg else s
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def div(a, b):
    a, b = num(a), num(b)
    if a is None or b is None or b == 0:
        return None
    return a / b


def add(*vals):
    vals = [num(v) for v in vals]
    if all(v is None for v in vals):
        return None
    return sum(v for v in vals if v is not None)


def avg2(a, b):
    a, b = num(a), num(b)
    if a is None:
        return None
    if b is None:
        return a
    return (a + b) / 2


def derived(y: dict, prev: dict | None = None) -> dict:
    """Métricas derivadas de un ejercicio (prev = ejercicio anterior, para promedios)."""
    g = lambda k: num(y.get(k))  # noqa: E731
    prev = prev or {}
    d: dict = {}
    d["ingresos_operativos"] = add(g("ingresos_peaje"), g("otros_ingresos"))
    d["ebitda"] = add(g("ebit"), g("amortizaciones")) if g("ebit") is not None else None
    d["deuda_financiera"] = add(g("deuda_cp"), g("deuda_lp"))
    d["deuda_neta"] = (d["deuda_financiera"] - (g("caja") or 0)) if d["deuda_financiera"] is not None else None
    d["capital_trabajo"] = (g("activo_corriente") - g("pasivo_corriente")) \
        if g("activo_corriente") is not None and g("pasivo_corriente") is not None else None
    d["liquidez"] = div(g("activo_corriente"), g("pasivo_corriente"))
    d["margen_ebitda"] = div(d["ebitda"], d["ingresos_operativos"])
    d["activo_promedio"] = avg2(g("activo_total"), num(prev.get("activo_total")))
    d["roa"] = div(g("resultado_neto"), d["activo_promedio"])
    d["cfo_activo"] = div(g("cfo"), d["activo_promedio"])
    d["rotacion"] = div(d["ingresos_operativos"], d["activo_promedio"])
    d["dn_ebitda"] = div(d["deuda_neta"], d["ebitda"])
    d["cobertura_intereses"] = div(d["ebitda"], g("intereses"))
    d["cfads"] = (d["ebitda"] - (g("capex_mant") or 0) - (g("impuestos_pagados") or 0)) \
        if d["ebitda"] is not None else None
    servicio = add(g("intereses"), g("capital_amortizado"))
    d["servicio_deuda"] = servicio
    d["dscr"] = div(d["cfads"], servicio)
    d["tmda"] = div(g("transito"), 365)
    d["ingreso_por_veh"] = div(g("ingresos_peaje"), g("transito"))
    d["ingreso_por_km"] = div(d["ingresos_operativos"], g("km"))
    d["capex_amort"] = div(g("capex"), g("amortizaciones"))
    if d["deuda_neta"] is not None and d["deuda_neta"] <= 0:
        d["anios_repago"] = 0.0
    else:
        d["anios_repago"] = div(d["deuda_neta"], d["cfads"]) if (d["cfads"] or 0) > 0 else None
    d["cola_concesion"] = (g("anios_restantes") - d["anios_repago"]) \
        if g("anios_restantes") is not None and d["anios_repago"] is not None else None
    d["pn_pasivo"] = div(g("patrimonio_neto"), g("pasivo_total"))
    return d


def consistency_warnings(y: dict) -> list[str]:
    g = lambda k: num(y.get(k))  # noqa: E731
    w = []
    at, pt, pn = g("activo_total"), g("pasivo_total"), g("patrimonio_neto")
    if None not in (at, pt, pn) and at:
        gap = abs(at - (pt + pn)) / abs(at)
        if gap > 0.01:
            w.append(f"Activo ≠ Pasivo + PN (diferencia {gap:.1%}).")
    ac = g("activo_corriente")
    if ac is not None and at is not None and ac > at:
        w.append("Activo corriente mayor que activo total.")
    pc = g("pasivo_corriente")
    if pc is not None and pt is not None and pc > pt:
        w.append("Pasivo corriente mayor que pasivo total.")
    dfin = add(g("deuda_cp"), g("deuda_lp"))
    if dfin is not None and pt is not None and dfin > pt * 1.001:
        w.append("Deuda financiera mayor que pasivo total.")
    dcp = g("deuda_cp")
    if dcp is not None and pc is not None and dcp > pc * 1.001:
        w.append("Deuda financiera corriente mayor que pasivo corriente.")
    return w
