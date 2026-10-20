"""Piotroski vial: nueve señales binarias adaptadas a concesionarias de peaje que no cotizan.

Cambios respecto del F-Score original (Piotroski, 2000) y por qué:
  · ΔMargen bruto → ΔMargen EBITDA: una concesión no tiene "costo de ventas" comparable;
    el margen EBITDA es la métrica de eficiencia que siguen bancos y calificadoras.
  · ΔDeuda LP / Activo → ΔDeuda neta / EBITDA: la capacidad de repago importa más que el
    peso contable de la deuda sobre un activo intangible que se amortiza.
  · Emisión de acciones → DSCR ≥ umbral: sin cotización la dilución no informa; la cobertura
    del servicio de deuda es el covenant central del project finance vial.
  · ΔRotación de activos se conserva pero con ingresos operativos sin CINIIF 12.
  · Nueva: ΔTránsito pagante, el driver de demanda propio del sector.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import derived, num


@dataclass
class Criterion:
    code: str
    name: str
    group: str
    passed: bool | None
    explanation: str
    formula: str
    latex: str
    narrative: str
    inputs: dict = field(default_factory=dict)

    @property
    def points(self) -> int:
        return 1 if self.passed else 0


@dataclass
class PiotroskiResult:
    score: int | None
    label: str
    year: str | None
    prior_year: str | None
    criteria: list[Criterion]
    missing: list[str]


def _f(v, kind="ratio"):
    if v is None:
        return "—"
    if kind == "pct":
        return f"{v:.2%}"
    if kind == "x":
        return f"{v:.2f}x"
    if kind == "int":
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:.4f}"


def label_for(score: int | None) -> str:
    if score is None:
        return "n/d"
    if score >= 8:
        return "ALTA"
    if score >= 5:
        return "MEDIA"
    return "BAJA"


def prior_year_of(years: dict, year: str) -> str | None:
    ks = sorted(k for k in years if k < year)
    return ks[-1] if ks else None


def compute_piotroski(years: dict, year: str, dscr_min: float = 1.20) -> PiotroskiResult:
    py = prior_year_of(years, year)
    cur = years.get(year, {})
    prv = years.get(py, {}) if py else {}
    pprv = years.get(prior_year_of(years, py), {}) if py else {}
    d1 = derived(cur, prv)
    d0 = derived(prv, pprv) if py else {}
    g1 = lambda k: num(cur.get(k))  # noqa: E731
    g0 = lambda k: num(prv.get(k))  # noqa: E731

    def gt(a, b):
        return None if a is None or b is None else a > b

    def lt(a, b):
        return None if a is None or b is None else a < b

    C = []
    # ── Rentabilidad
    C.append(Criterion(
        "F1 ROA", "Rentabilidad sobre activos positiva", "RENTABILIDAD",
        None if d1["roa"] is None else d1["roa"] > 0,
        "La concesionaria genera resultado neto positivo sobre su activo.",
        "ROA_t = Resultado neto_t / Activo total promedio_t > 0",
        r"ROA_t = \frac{RN_t}{\overline{AT}_t} > 0",
        f"ROA {year}: {_f(d1['roa'], 'pct')}",
        {"resultado_neto": g1("resultado_neto"), "activo_promedio": d1["activo_promedio"], "roa": d1["roa"]},
    ))
    C.append(Criterion(
        "F2 CFO", "Flujo operativo positivo", "RENTABILIDAD",
        None if g1("cfo") is None else g1("cfo") > 0,
        "La recaudación se convierte en caja después de pagar la operación.",
        "CFO_t > 0",
        r"CFO_t > 0",
        f"CFO {year}: {_f(g1('cfo'), 'int')}",
        {"cfo": g1("cfo")},
    ))
    C.append(Criterion(
        "F3 ΔMARGEN", "Margen EBITDA en mejora", "RENTABILIDAD",
        gt(d1["margen_ebitda"], d0.get("margen_ebitda")),
        "La tarifa le gana a los costos de operación y mantenimiento rutinario.",
        "EBITDA_t / Ingresos op._t > EBITDA_t-1 / Ingresos op._t-1",
        r"\frac{EBITDA_t}{I_t} > \frac{EBITDA_{t-1}}{I_{t-1}}",
        f"Margen EBITDA: {_f(d0.get('margen_ebitda'), 'pct')} ({py}) → {_f(d1['margen_ebitda'], 'pct')} ({year})",
        {"margen_t": d1["margen_ebitda"], "margen_t-1": d0.get("margen_ebitda"),
         "ebitda_t": d1["ebitda"], "ingresos_op_t": d1["ingresos_operativos"]},
    ))
    C.append(Criterion(
        "F4 ACCRUAL", "Calidad del resultado (CFO > resultado neto)", "RENTABILIDAD",
        gt(g1("cfo"), g1("resultado_neto")),
        "El resultado está respaldado por caja y no por devengamientos o ajustes contables.",
        "CFO_t > Resultado neto_t",
        r"CFO_t > RN_t",
        f"CFO {_f(g1('cfo'), 'int')} vs RN {_f(g1('resultado_neto'), 'int')}",
        {"cfo": g1("cfo"), "resultado_neto": g1("resultado_neto")},
    ))
    # ── Solvencia y liquidez
    dn1, dn0 = d1["dn_ebitda"], d0.get("dn_ebitda")
    eb1, eb0 = d1["ebitda"], d0.get("ebitda")
    if dn1 is not None and dn0 is not None and eb1 and eb0 and eb1 > 0 and eb0 > 0:
        p5 = dn1 < dn0
    elif d1["deuda_neta"] is not None and d1["deuda_neta"] <= 0 and eb1 and eb1 > 0:
        p5 = True  # caja neta positiva con EBITDA positivo
    elif eb1 is not None and eb1 <= 0:
        p5 = False
    else:
        p5 = None
    C.append(Criterion(
        "F5 ΔDN/EBITDA", "Apalancamiento (Deuda neta / EBITDA) en baja", "SOLVENCIA",
        p5,
        "Menos años de EBITDA comprometidos con la deuda. Con EBITDA ≤ 0 la señal falla.",
        "DN_t / EBITDA_t < DN_t-1 / EBITDA_t-1",
        r"\frac{DN_t}{EBITDA_t} < \frac{DN_{t-1}}{EBITDA_{t-1}}",
        f"DN/EBITDA: {_f(dn0, 'x')} ({py}) → {_f(dn1, 'x')} ({year})",
        {"dn_ebitda_t": dn1, "dn_ebitda_t-1": dn0, "deuda_neta_t": d1["deuda_neta"], "ebitda_t": eb1},
    ))
    C.append(Criterion(
        "F6 ΔLIQUIDEZ", "Liquidez corriente en mejora", "SOLVENCIA",
        gt(d1["liquidez"], d0.get("liquidez")),
        "Más activo corriente por cada peso de pasivo corriente que el año anterior.",
        "AC_t / PC_t > AC_t-1 / PC_t-1",
        r"\frac{AC_t}{PC_t} > \frac{AC_{t-1}}{PC_{t-1}}",
        f"Liquidez: {_f(d0.get('liquidez'), 'x')} ({py}) → {_f(d1['liquidez'], 'x')} ({year})",
        {"liquidez_t": d1["liquidez"], "liquidez_t-1": d0.get("liquidez")},
    ))
    dscr = d1["dscr"]
    if dscr is None and d1["servicio_deuda"] in (None, 0) and d1["cfads"] is not None and (d1["deuda_financiera"] or 0) == 0:
        p7 = d1["cfads"] > 0  # sin deuda: pasa si genera CFADS positivo
    else:
        p7 = None if dscr is None else dscr >= dscr_min
    C.append(Criterion(
        "F7 DSCR", f"Cobertura del servicio de deuda ≥ {dscr_min:.2f}x", "SOLVENCIA",
        p7,
        "El flujo disponible cubre intereses y amortizaciones con margen. Es el covenant típico "
        "del financiamiento de concesiones (reemplaza la señal de emisión de acciones).",
        "DSCR = (EBITDA − Capex mant. − Impuestos pagados) / (Intereses + Amortización de capital)",
        r"DSCR_t = \frac{EBITDA_t - Capex^{mant}_t - Imp_t}{Int_t + K_t} \geq " + f"{dscr_min:.2f}",
        f"DSCR {year}: {_f(dscr, 'x')} (umbral {dscr_min:.2f}x)",
        {"cfads": d1["cfads"], "servicio_deuda": d1["servicio_deuda"], "dscr": dscr, "umbral": dscr_min},
    ))
    # ── Eficiencia operativa
    C.append(Criterion(
        "F8 ΔTRÁNSITO", "Tránsito pagante en crecimiento", "OPERACIÓN",
        gt(g1("transito"), g0("transito")),
        "Más vehículos equivalentes pagantes: la demanda del corredor se expande.",
        "Tránsito_t > Tránsito_t-1",
        r"TR_t > TR_{t-1}",
        f"Tránsito: {_f(g0('transito'), 'int')} ({py}) → {_f(g1('transito'), 'int')} ({year})",
        {"transito_t": g1("transito"), "transito_t-1": g0("transito")},
    ))
    C.append(Criterion(
        "F9 ΔROTACIÓN", "Rotación del activo en mejora", "OPERACIÓN",
        gt(d1["rotacion"], d0.get("rotacion")),
        "Más ingresos operativos (sin construcción CINIIF 12) por peso de activo concesionado.",
        "Ingresos op._t / Activo prom._t > Ingresos op._t-1 / Activo prom._t-1",
        r"\frac{I_t}{\overline{AT}_t} > \frac{I_{t-1}}{\overline{AT}_{t-1}}",
        f"Rotación: {_f(d0.get('rotacion'))} ({py}) → {_f(d1['rotacion'])} ({year})",
        {"rotacion_t": d1["rotacion"], "rotacion_t-1": d0.get("rotacion")},
    ))

    if not py:
        for c in C:
            if c.code.startswith(("F3", "F5", "F6", "F8", "F9")):
                c.passed = None
    missing = [c.code for c in C if c.passed is None]
    # Sin ejercicio comparativo el score no es comparable con la escala 0–9: no se informa.
    score = sum(c.points for c in C) if py and len(missing) < len(C) else None
    label = label_for(score) if py else "requiere ejercicio anterior"
    return PiotroskiResult(score, label, year, py, C, missing)
