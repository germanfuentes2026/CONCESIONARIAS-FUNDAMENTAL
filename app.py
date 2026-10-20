"""Concession Terminal — análisis fundamental de concesionarias viales que no cotizan.

Balances de carga manual · Piotroski vial (9 señales sectoriales) · Altman Z'' / Z''-EM.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from src.altman import EM_CONSTANT, EM_RATING_TABLE, WEIGHTS, compute_altman, cutoffs
from src.model import FIELDS, SECTIONS, consistency_warnings, derived, num
from src.piotroski import compute_piotroski, prior_year_of
from src.storage import (
    blank_template_excel,
    company_to_frame,
    empty_company,
    export_excel,
    frame_to_years,
    load_db,
    parse_upload,
    save_db,
)

st.set_page_config(
    page_title="Concession Terminal",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

TERMINAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"]  {
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
}

.stApp {
    background: radial-gradient(1200px 600px at 10% -10%, #1a2420 0%, #0b0e11 45%, #07090b 100%);
    color: #d7e0d8;
}

header[data-testid="stHeader"] {
    background: #0b0e11;
    border-bottom: 1px solid #1f2a22;
}

section[data-testid="stSidebar"] {
    background: #0a0d10;
    border-right: 1px solid #1f2a22;
}

section[data-testid="stSidebar"] * {
    color: #c5d0c6;
}

.block-container {
    padding-top: 4.5rem;
    max-width: 1480px;
}

h1, h2, h3 {
    font-family: "IBM Plex Sans", sans-serif;
    letter-spacing: 0.04em;
}

.ft-masthead {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border: 1px solid #243328;
    background: linear-gradient(90deg, #101612 0%, #0d1210 60%, #151208 100%);
    padding: 14px 18px 12px 18px;
    margin-bottom: 14px;
}
.ft-brand {
    font-family: "IBM Plex Mono", monospace;
    color: #f5a623;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    line-height: 1.4;
}
.ft-title {
    font-size: 28px;
    font-weight: 700;
    color: #eef6ef;
    line-height: 1.1;
    margin-top: 4px;
}
.ft-sub {
    color: #7f8f82;
    font-size: 13px;
    margin-top: 4px;
}
.ft-clock {
    text-align: right;
    font-family: "IBM Plex Mono", monospace;
    color: #9aa89b;
    font-size: 12px;
}
.ft-ticker {
    color: #f5a623;
    font-size: 22px;
    font-weight: 600;
}

div[data-testid="stMetric"] {
    background: #111714;
    border: 1px solid #243328;
    padding: 12px 8px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
div[data-testid="stMetric"] [data-testid="stMetricLabel"],
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
    width: 100%;
    justify-content: center;
    text-align: center;
}
div[data-testid="stMetric"] [data-testid="stMetricLabel"] *,
div[data-testid="stMetric"] [data-testid="stMetricValue"] *,
div[data-testid="stMetric"] [data-testid="stMetricDelta"] * {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    text-align: center;
    justify-content: center;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] > div {
    font-size: 1.7rem;
    line-height: 1.2;
}
div[data-testid="stMetric"] label {
    color: #8b9a8d !important;
    font-family: "IBM Plex Mono", monospace;
    letter-spacing: 0.12em;
    font-size: 11px !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: "IBM Plex Mono", monospace;
    color: #e8f3e9;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #0d1110;
    border-bottom: 1px solid #243328;
}
.stTabs [data-baseweb="tab"] {
    background: #0d1110;
    color: #8b9a8d;
    font-family: "IBM Plex Mono", monospace;
    letter-spacing: 0.08em;
}
.stTabs [aria-selected="true"] {
    color: #f5a623 !important;
    border-bottom: 2px solid #f5a623;
}

.pass { color: #3ddc84; font-weight: 600; }
.fail { color: #ff5c5c; font-weight: 600; }
.miss { color: #f5a623; font-weight: 600; }

.stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {
    background: #f5a623;
    color: #111;
    border: 0;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-family: "IBM Plex Mono", monospace;
}
.stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {
    background: #ffc056;
    color: #111;
}
.stButton>button p, .stDownloadButton>button p, .stFormSubmitButton>button p { color: #111 !important; }

hr { border-color: #243328; }

.stDataFrame { border: 1px solid #243328; }

.audit-note {
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
    color: #8b9a8d;
}

.sec-head {
    font-family: "IBM Plex Mono", monospace;
    color: #f5a623;
    font-size: 12px;
    letter-spacing: 0.22em;
    border-bottom: 1px solid #243328;
    padding: 10px 0 4px 0;
    margin: 6px 0 6px 0;
}

table.sem {
    width: 100%;
    border-collapse: collapse;
    font-family: "IBM Plex Mono", monospace;
    font-size: 13px;
    border: 1px solid #243328;
}
table.sem th {
    text-align: left;
    color: #8b9a8d;
    font-weight: 500;
    letter-spacing: 0.12em;
    font-size: 11px;
    background: #0d1110;
    padding: 8px 10px;
    border-bottom: 1px solid #243328;
}
table.sem td {
    padding: 8px 10px;
    border-bottom: 1px solid #1a241d;
    color: #d7e0d8;
}
table.sem td.v { text-align: right; color: #e8f3e9; }
.dot-OK { color: #3ddc84; }
.dot-ALERTA { color: #f5a623; }
.dot-CRITICO { color: #ff5c5c; }
.dot-ND { color: #5b6a5e; }
</style>
"""

st.markdown(TERMINAL_CSS, unsafe_allow_html=True)


# ───────────────────────────── FORMATO ─────────────────────────────

def _bad(v) -> bool:
    return v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def fmt_ar(v, dec: int = 0) -> str:
    """Formato argentino: 1.234.567,89"""
    if _bad(v):
        return "—"
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_x(v) -> str:
    return "—" if _bad(v) else fmt_ar(v, 2) + "x"


def fmt_pct(v) -> str:
    return "—" if _bad(v) else fmt_ar(v * 100, 1) + "%"


def _pass_label(passed: bool | None) -> str:
    if passed is True:
        return "PASA · 1"
    if passed is False:
        return "NO PASA · 0"
    return "N/D · —"


def _avg(vals):
    v = [x for x in vals if x is not None]
    return (sum(v) / len(v)) if v else None


# ───────────────────────────── ESTADO ─────────────────────────────

if "db" not in st.session_state:
    st.session_state.db = load_db()
if "ver" not in st.session_state:
    st.session_state.ver = 0
db = st.session_state.db
empresas = db["empresas"]


def persist(msg: str | None = None) -> None:
    try:
        save_db(db)
    except OSError as exc:
        st.session_state.flash = ("error", f"No se pudo guardar en disco: {exc}. Exportá un respaldo JSON.")
        return
    if msg:
        st.session_state.flash = ("success", msg)


def bump() -> None:
    st.session_state.ver += 1


DEMO_FILE = ROOT / "data" / "demo_concesionaria.json"


# ───────────────────────────── SIDEBAR ─────────────────────────────

with st.sidebar:
    st.markdown("**EMPRESA**")
    nombres = sorted(empresas.keys())
    if nombres:
        default = st.session_state.get("active")
        idx = nombres.index(default) if default in nombres else 0
        active = st.selectbox("Concesionaria", nombres, index=idx, label_visibility="collapsed")
        st.session_state.active = active
    else:
        active = None
        st.caption("Todavía no hay empresas cargadas.")

    with st.expander("➕  Nueva empresa", expanded=not nombres):
        nuevo = st.text_input("Razón social", placeholder="Ej.: Autovía del Norte S.A.")
        if st.button("Crear empresa", width="stretch"):
            n = nuevo.strip()
            if not n:
                st.warning("Ingresá un nombre.")
            elif n in empresas:
                st.warning("Ya existe una empresa con ese nombre.")
            else:
                empresas[n] = empty_company(n)
                st.session_state.active = n
                persist(f"Empresa «{n}» creada. Cargá sus balances en la pestaña CARGA.")
                bump()
                st.rerun()
        if DEMO_FILE.exists() and st.button("Cargar empresa demo", width="stretch"):
            demo = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
            empresas[demo["meta"]["nombre"]] = demo
            st.session_state.active = demo["meta"]["nombre"]
            persist("Empresa demo cargada (datos ficticios).")
            bump()
            st.rerun()

    company = empresas.get(active) if active else None
    years_all = sorted(company["years"].keys()) if company else []

    st.markdown("---")
    st.markdown("**EJERCICIO**")
    if years_all:
        sel_year = st.selectbox("Ejercicio analizado", list(reversed(years_all)), label_visibility="collapsed")
    else:
        sel_year = None
        st.caption("Sin ejercicios cargados.")

    st.markdown("---")
    st.markdown("**PARÁMETROS**")
    variant_lbl = st.radio(
        "Altman",
        ["Z'' · privada no manufacturera", "Z''-EM · mercados emergentes"],
        index=1,
        help="Z''-EM suma 3,25 al Z'' y permite leer una calificación equivalente (Altman, 2005).",
    )
    variant = "EM" if variant_lbl.startswith("Z''-EM") else "Z2"
    dscr_min = st.number_input("Umbral DSCR (señal F7)", min_value=0.80, max_value=3.00,
                               value=1.20, step=0.05, format="%.2f")

    st.markdown("---")
    st.markdown("**SOBRE LOS MODELOS**")
    st.caption(
        "Piotroski vial: nueve señales binarias adaptadas a concesiones de peaje — "
        "rentabilidad, solvencia (DN/EBITDA, liquidez, DSCR) y operación (tránsito, rotación). Score 0–9."
    )
    st.caption(
        "Altman Z'' (1995): 6,56 X1 + 3,26 X2 + 6,72 X3 + 1,05 X4, con patrimonio contable y sin X5. "
        "Cortes 1,10 / 2,60 (Z'') o 4,35 / 5,85 (Z''-EM). No es una calificación de riesgo."
    )

    st.markdown("---")
    st.markdown("**RESPALDO**")
    st.download_button(
        "Descargar base (JSON)",
        data=json.dumps(db, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="concesionarias_base.json",
        mime="application/json",
        width="stretch",
    )
    up_db = st.file_uploader("Restaurar base (JSON)", type=["json"], key=f"updb_{st.session_state.ver}")
    if up_db is not None and st.button("Restaurar", width="stretch"):
        try:
            new_db = json.loads(up_db.getvalue().decode("utf-8"))
            if "empresas" not in new_db:
                raise ValueError("el archivo no tiene la clave 'empresas'")
            empresas.update(new_db["empresas"])
            persist(f"Base restaurada: {len(new_db['empresas'])} empresa(s).")
            bump()
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Archivo inválido: {exc}")

    if company:
        with st.expander("Eliminar empresa"):
            ok = st.checkbox(f"Confirmo eliminar «{active}» y todos sus balances")
            if st.button("Eliminar", width="stretch", disabled=not ok):
                empresas.pop(active, None)
                st.session_state.active = None
                persist("Empresa eliminada.")
                bump()
                st.rerun()
    st.markdown("---")
    st.caption("Datos de carga manual. Usar balances en moneda homogénea (RT 6 / NIC 29).")


# ───────────────────────────── HISTORIA ─────────────────────────────

F_CODES = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"]


def build_history(years: dict, variant: str, dscr_min: float, n: int = 10):
    ys = sorted(years.keys())[-n:]
    f_rows, z_rows = [], []
    for y in reversed(ys):
        fr = compute_piotroski(years, y, dscr_min)
        row = {"Ejercicio": y, "F-Score": fr.score, "calidad": fr.label}
        for cr in fr.criteria:
            row[cr.code.split()[0]] = cr.points if cr.passed is not None else None
        f_rows.append(row)

        zr = compute_altman(years, y, variant)
        zrow = {"Ejercicio": y, "Z-Score": None if zr.z is None else round(zr.z, 2),
                "zona": zr.zone, "rating eq.": zr.rating or "—"}
        for cm in zr.components:
            zrow[cm.code] = None if cm.value is None else round(cm.value, 4)
        z_rows.append(zrow)
    return f_rows, z_rows


def sector_rows(years: dict) -> list[dict]:
    out = []
    for y in sorted(years.keys()):
        py = prior_year_of(years, y)
        d = derived(years[y], years.get(py) if py else None)
        out.append({"Ejercicio": y, **d, "transito": num(years[y].get("transito"))})
    return out


# ───────────────────────────── GRÁFICOS ─────────────────────────────

def _style_chart(ch: alt.Chart) -> alt.Chart:
    return (
        ch.configure(background="#0b0e11")
        .configure_view(stroke="#243328")
        .configure_axis(
            labelColor="#8b9a8d", titleColor="#8b9a8d",
            gridColor="#1f2a22", domainColor="#243328", tickColor="#243328",
            labelFont="IBM Plex Mono", titleFont="IBM Plex Mono",
        )
        .configure_legend(labelColor="#8b9a8d", titleColor="#8b9a8d",
                          labelFont="IBM Plex Mono", titleFont="IBM Plex Mono")
        .configure_title(color="#e8f3e9", font="IBM Plex Mono", fontSize=14)
    )


def _threshold_layer(levels: list[tuple[float, str, str]]) -> alt.Chart:
    df = pd.DataFrame(levels, columns=["y", "label", "color"])
    rules = alt.Chart(df).mark_rule(strokeDash=[5, 4], opacity=0.8).encode(
        y="y:Q", color=alt.Color("color:N", scale=None)
    )
    texts = alt.Chart(df).mark_text(align="left", dx=4, dy=-6, fontSize=10).encode(
        y="y:Q", text="label:N", color=alt.Color("color:N", scale=None), x=alt.value(4),
    )
    return rules + texts


def _line(df, field, title, fmt, domain, levels, tooltip):
    base = alt.Chart(df).encode(
        x=alt.X("Ejercicio:N", title="Ejercicio", sort=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{field}:Q", title=title, scale=alt.Scale(domain=domain)),
        tooltip=tooltip,
    )
    line = base.mark_line(color="#f5a623", strokeWidth=2.5,
                          point=alt.OverlayMarkDef(color="#f5a623", size=90, filled=True))
    labels = base.mark_text(dy=-14, color="#e8f3e9", fontSize=12,
                            font="IBM Plex Mono").encode(text=alt.Text(f"{field}:Q", format=fmt))
    return _threshold_layer(levels) + line + labels


def piotroski_chart(hist_f):
    df = pd.DataFrame(hist_f)
    if df.empty:
        return None
    df = df.dropna(subset=["F-Score"]).sort_values("Ejercicio")
    if df.empty:
        return None
    layer = _line(df, "F-Score", "F-Score vial", "d", [0, 9],
                  [(8, "ALTA ≥ 8", "#3ddc84"), (5, "MEDIA ≥ 5", "#8b9a8d")],
                  ["Ejercicio", "F-Score", "calidad"])
    return _style_chart(layer.properties(height=340, title="Piotroski vial · F-Score"))


def altman_chart(hist_z, variant):
    df = pd.DataFrame(hist_z)
    if df.empty:
        return None
    df = df.dropna(subset=["Z-Score"]).sort_values("Ejercicio")
    if df.empty:
        return None
    lo_c, hi_c = cutoffs(variant)
    lo = min(0.0, float(df["Z-Score"].min()) - 0.5)
    hi = max(hi_c + 0.8, float(df["Z-Score"].max()) + 0.5)
    layer = _line(df, "Z-Score", "Z-Score", ".2f", [lo, hi],
                  [(hi_c, f"SEGURA > {hi_c:.2f}", "#3ddc84"), (lo_c, f"RIESGO < {lo_c:.2f}", "#ff5c5c")],
                  ["Ejercicio", "Z-Score", "zona", "rating eq."])
    name = "Z''-EM" if variant == "EM" else "Z''"
    return _style_chart(layer.properties(height=340, title=f"Altman {name}"))


def piotroski_criteria_chart(hist_f):
    df = pd.DataFrame(hist_f)
    if df.empty:
        return None
    df = df.dropna(subset=["F-Score"])
    codes = [c for c in F_CODES if c in df.columns]
    if df.empty or not codes:
        return None
    long = df.melt(id_vars=["Ejercicio", "F-Score"], value_vars=codes,
                   var_name="señal", value_name="puntos").dropna(subset=["puntos"])
    long = long[long["puntos"] > 0]
    if long.empty:
        return None
    years = sorted(df["Ejercicio"].unique())
    bars = alt.Chart(long).mark_bar(stroke="#0b0e11", strokeWidth=1).encode(
        x=alt.X("Ejercicio:N", title="Ejercicio", sort=years, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("sum(puntos):Q", title="Señales aprobadas", scale=alt.Scale(domain=[0, 9])),
        color=alt.Color("señal:N", title="Señal", sort=codes, scale=alt.Scale(scheme="tableau10")),
        order=alt.Order("señal:N", sort="ascending"),
        tooltip=["Ejercicio", "señal", "puntos"],
    )
    totals = alt.Chart(df).mark_text(dy=-8, color="#e8f3e9", fontSize=13, font="IBM Plex Mono").encode(
        x=alt.X("Ejercicio:N", sort=years),
        y=alt.Y("F-Score:Q", scale=alt.Scale(domain=[0, 9])),
        text=alt.Text("F-Score:Q", format="d"),
    )
    return _style_chart((bars + totals).properties(height=360, title="Piotroski vial · señales por ejercicio"))


def altman_contrib_chart(hist_z, variant):
    df = pd.DataFrame(hist_z)
    if df.empty:
        return None
    df = df.dropna(subset=["Z-Score"]).copy()
    factors = [c for c in WEIGHTS if c in df.columns]
    if df.empty or not factors:
        return None
    for col in factors:
        df[col] = pd.to_numeric(df[col], errors="coerce") * WEIGHTS[col]
    vars_ = list(factors)
    if variant == "EM":
        df["EM +3,25"] = EM_CONSTANT
        vars_.append("EM +3,25")
    long = df.melt(id_vars=["Ejercicio", "Z-Score"], value_vars=vars_,
                   var_name="factor", value_name="aporte").dropna(subset=["aporte"])
    years = sorted(df["Ejercicio"].unique())
    bars = alt.Chart(long).mark_bar(stroke="#0b0e11", strokeWidth=1).encode(
        x=alt.X("Ejercicio:N", title="Ejercicio", sort=years, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("aporte:Q", title="Aporte al Z-Score"),
        color=alt.Color("factor:N", title="Factor", sort=vars_,
                        scale=alt.Scale(domain=["X1", "X2", "X3", "X4", "EM +3,25"],
                                        range=["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#3a4a3e"])),
        order=alt.Order("factor:N", sort="ascending"),
        tooltip=["Ejercicio", "factor", alt.Tooltip("aporte:Q", format=".3f")],
    )
    total = alt.Chart(df).mark_point(shape="diamond", size=140, filled=True, color="#f5a623",
                                     stroke="#0b0e11").encode(
        x=alt.X("Ejercicio:N", sort=years), y="Z-Score:Q",
        tooltip=["Ejercicio", alt.Tooltip("Z-Score:Q", format=".2f"), "zona"])
    total_lbl = alt.Chart(df).mark_text(dx=24, color="#f5a623", fontSize=12, font="IBM Plex Mono").encode(
        x=alt.X("Ejercicio:N", sort=years), y="Z-Score:Q", text=alt.Text("Z-Score:Q", format=".2f"))
    lo_c, hi_c = cutoffs(variant)
    zones = _threshold_layer([(hi_c, f"SEGURA > {hi_c:.2f}", "#3ddc84"),
                              (lo_c, f"RIESGO < {lo_c:.2f}", "#ff5c5c")])
    return _style_chart((zones + bars + total + total_lbl).properties(
        height=380, title="Altman · aporte ponderado de X1–X4 por ejercicio"))


def dscr_chart(rows, dscr_min):
    df = pd.DataFrame(rows)[["Ejercicio", "dscr", "dn_ebitda"]].dropna(subset=["dscr"])
    if df.empty:
        return None
    hi = max(dscr_min + 1.0, float(df["dscr"].max()) + 0.5)
    lo = min(0.0, float(df["dscr"].min()) - 0.3)
    layer = _line(df, "dscr", "DSCR (x)", ".2f", [lo, hi],
                  [(dscr_min, f"UMBRAL {dscr_min:.2f}x", "#3ddc84"), (1.0, "1,00x", "#ff5c5c")],
                  ["Ejercicio", alt.Tooltip("dscr:Q", format=".2f", title="DSCR"),
                   alt.Tooltip("dn_ebitda:Q", format=".2f", title="DN/EBITDA")])
    return _style_chart(layer.properties(height=320, title="Cobertura del servicio de deuda (DSCR)"))


def leverage_chart(rows):
    df = pd.DataFrame(rows)[["Ejercicio", "dn_ebitda"]].dropna()
    if df.empty:
        return None
    hi = max(6.0, float(df["dn_ebitda"].max()) + 0.5)
    lo = min(0.0, float(df["dn_ebitda"].min()) - 0.5)
    layer = _line(df, "dn_ebitda", "Deuda neta / EBITDA (x)", ".2f", [lo, hi],
                  [(3.0, "REF. 3,0x", "#3ddc84"), (5.0, "ALERTA 5,0x", "#ff5c5c")],
                  ["Ejercicio", alt.Tooltip("dn_ebitda:Q", format=".2f", title="DN/EBITDA")])
    return _style_chart(layer.properties(height=320, title="Apalancamiento · Deuda neta / EBITDA"))


def traffic_chart(rows):
    df = pd.DataFrame(rows)[["Ejercicio", "transito", "tmda", "ingreso_por_veh"]].dropna(subset=["transito"])
    if df.empty:
        return None
    df["millones"] = df["transito"] / 1e6
    base = alt.Chart(df).encode(x=alt.X("Ejercicio:N", title="Ejercicio", sort=None,
                                        axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar(color="#2b3a2f", stroke="#f5a623", strokeWidth=1).encode(
        y=alt.Y("millones:Q", title="Tránsito pagante (millones de veh. eq.)"),
        tooltip=["Ejercicio", alt.Tooltip("transito:Q", format=",.0f", title="tránsito"),
                 alt.Tooltip("tmda:Q", format=",.0f", title="TMDA"),
                 alt.Tooltip("ingreso_por_veh:Q", format=",.4f", title="ingreso/veh")],
    )
    lbl = base.mark_text(dy=-8, color="#e8f3e9", fontSize=12, font="IBM Plex Mono").encode(
        y="millones:Q", text=alt.Text("millones:Q", format=".1f"))
    return _style_chart((bars + lbl).properties(height=320, title="Tránsito pagante anual"))


# ───────────────────────────── UI ─────────────────────────────

def render_masthead(company: dict | None, stmt: str = "") -> None:
    ticker_html = ""
    right = "Fuente: balances de carga manual"
    if company:
        m = company["meta"]
        extra = f" · {m['corredor']}" if m.get("corredor") else ""
        ticker_html = (f'<div class="ft-ticker">{m["nombre"]} &nbsp;'
                       f'<span style="color:#9aa89b;font-size:14px">{extra.lstrip(" ·")}</span></div>')
        right += f" &nbsp;|&nbsp; Cifras: {m.get('moneda', 'ARS')} {m.get('unidad', '')}"
    if stmt:
        right += f"<br/>{stmt}"
    st.markdown(
        f"""
        <div class="ft-masthead">
          <div>
            <div class="ft-brand">Concession Terminal</div>
            <div class="ft-title">Concesionarias Viales · Análisis Fundamental</div>
            <div class="ft-sub">Piotroski vial · Altman Z'' para empresas que no cotizan</div>
            {ticker_html}
          </div>
          <div class="ft-clock">{right}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


flash = st.session_state.pop("flash", None)

if not company:
    render_masthead(None)
    if flash:
        getattr(st, flash[0])(flash[1])
    st.info("Creá una empresa en la barra lateral (**➕ Nueva empresa**) o cargá la **empresa demo** para ver la terminal funcionando.")
    st.stop()

meta = company["meta"]
years = company["years"]
unit_lbl = f"{meta.get('moneda', 'ARS')} {meta.get('unidad', '')}".strip()

f_res = compute_piotroski(years, sel_year, dscr_min) if sel_year else None
z_res = compute_altman(years, sel_year, variant) if sel_year else None
d_sel = derived(years[sel_year], years.get(prior_year_of(years, sel_year))) if sel_year else {}

stmt = f"Ejercicio {sel_year}" + (f" · comparativo {f_res.prior_year}" if f_res and f_res.prior_year else "") \
    if sel_year else "Sin ejercicios cargados"
render_masthead(company, stmt)
if flash:
    getattr(st, flash[0])(flash[1])

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("F-SCORE VIAL", "—" if not f_res or f_res.score is None else f"{f_res.score}/9",
          f_res.label if f_res else None, delta_color="off")
zname = "Z''-EM" if variant == "EM" else "Z''"
c2.metric(f"{zname}-SCORE", "—" if not z_res or z_res.z is None else fmt_ar(z_res.z, 2),
          z_res.zone if z_res else None, delta_color="off")
c3.metric("DSCR", fmt_x(d_sel.get("dscr")))
c4.metric("DEUDA NETA / EBITDA", fmt_x(d_sel.get("dn_ebitda")))
c5.metric("MARGEN EBITDA", fmt_pct(d_sel.get("margen_ebitda")))
c6.metric("EJERCICIO", sel_year or "—", (f"rating eq. {z_res.rating}" if z_res and z_res.rating else None),
          delta_color="off")

hist_f, hist_z = build_history(years, variant, dscr_min) if years else ([], [])
srows = sector_rows(years) if years else []

tab_load, tab_ov, tab_f, tab_z, tab_c, tab_form, tab_charts = st.tabs(
    ["CARGA DE BALANCES", "RESUMEN", "PIOTROSKI VIAL", "ALTMAN Z''", "CONCESIÓN", "FÓRMULAS", "GRÁFICOS"]
)

# ───────────── CARGA
with tab_load:
    with st.expander("Datos de la empresa", expanded=not years):
        with st.form(f"meta_{active}_{st.session_state.ver}"):
            m1, m2, m3 = st.columns([3, 3, 2])
            n_nombre = m1.text_input("Razón social", meta.get("nombre", active))
            n_corr = m2.text_input("Corredor / tramo", meta.get("corredor", ""), placeholder="Ej.: RN 9 · 312 km")
            n_cuit = m3.text_input("CUIT", meta.get("cuit", ""))
            m4, m5, m6 = st.columns(3)
            n_mon = m4.selectbox("Moneda", ["ARS", "USD", "UYU", "CLP", "BRL", "EUR"],
                                 index=["ARS", "USD", "UYU", "CLP", "BRL", "EUR"].index(meta.get("moneda", "ARS"))
                                 if meta.get("moneda", "ARS") in ["ARS", "USD", "UYU", "CLP", "BRL", "EUR"] else 0)
            units = ["unidades", "miles", "millones"]
            n_uni = m5.selectbox("Unidad de los montos", units,
                                 index=units.index(meta.get("unidad", "miles")) if meta.get("unidad") in units else 1)
            n_mes = m6.number_input("Mes de cierre", 1, 12, int(meta.get("mes_cierre", 12)))
            if st.form_submit_button("Guardar datos de la empresa"):
                nn = n_nombre.strip() or active
                if nn != active and nn in empresas:
                    st.error("Ya existe otra empresa con esa razón social.")
                else:
                    meta.update({"nombre": nn, "corredor": n_corr.strip(), "cuit": n_cuit.strip(),
                                 "moneda": n_mon, "unidad": n_uni, "mes_cierre": int(n_mes)})
                    if nn != active:
                        empresas[nn] = empresas.pop(active)
                        st.session_state.active = nn
                    persist("Datos de la empresa guardados.")
                    bump()
                    st.rerun()

    st.markdown(
        f"<div class='audit-note'>Montos en {unit_lbl}, en moneda homogénea del último cierre. "
        "Valores de deuda, capex, impuestos e intereses en positivo. Tránsito en vehículos equivalentes "
        "pagantes por año. Celdas vacías = dato no disponible.</div>",
        unsafe_allow_html=True,
    )

    full = company_to_frame(company)
    edited_parts = []
    col_cfg = {"_index": st.column_config.TextColumn("Concepto", width="large", disabled=True)}
    for ycol in full.columns:
        col_cfg[ycol] = st.column_config.NumberColumn(ycol, format="localized", width="small")
    if full.columns.empty:
        st.info("Agregá el primer ejercicio con el control de abajo (por ejemplo 2024) "
                "o importá una planilla.")
    else:
        for i, sec in enumerate(SECTIONS):
            labels = [f.label for f in FIELDS if f.section == sec]
            st.markdown(f"<div class='sec-head'>{sec}</div>", unsafe_allow_html=True)
            part = st.data_editor(
                full.loc[labels],
                key=f"ed_{active}_{i}_{st.session_state.ver}",
                width="stretch",
                num_rows="fixed",
                column_config=col_cfg,
                height=36 * (len(labels) + 1) + 4,
            )
            edited_parts.append(part)

    def collect_edits() -> dict:
        if not edited_parts:
            return dict(years)
        return frame_to_years(pd.concat(edited_parts))

    st.markdown("<div class='sec-head'>ACCIONES</div>", unsafe_allow_html=True)
    a1, a2, a3, a4, a5 = st.columns([2, 1.3, 1.6, 1.3, 1.6])
    if a1.button("Guardar balances", width="stretch", disabled=not edited_parts, type="primary"):
        company["years"] = collect_edits()
        persist("Balances guardados.")
        bump()
        st.rerun()
    new_year = a2.number_input("Nuevo ejercicio", min_value=1990, max_value=2100,
                               value=(int(years_all[-1]) + 1) if years_all else 2024, step=1,
                               label_visibility="collapsed")
    if a3.button("Agregar ejercicio", width="stretch"):
        ys = collect_edits()
        if str(new_year) in ys:
            st.warning(f"El ejercicio {new_year} ya existe.")
        else:
            ys[str(new_year)] = {}
            company["years"] = dict(sorted(ys.items()))
            persist(f"Ejercicio {new_year} agregado. Los cambios en pantalla también se guardaron.")
            bump()
            st.rerun()
    del_year = a4.selectbox("Ejercicio a eliminar", list(reversed(years_all)) or ["—"],
                            label_visibility="collapsed")
    if a5.button("Eliminar ejercicio", width="stretch", disabled=not years_all):
        ys = collect_edits()
        ys.pop(str(del_year), None)
        company["years"] = ys
        persist(f"Ejercicio {del_year} eliminado.")
        bump()
        st.rerun()

    warns = []
    for y in years_all:
        for w in consistency_warnings(years[y]):
            warns.append(f"**{y}** · {w}")
    if warns:
        st.warning("Controles de consistencia:\n\n" + "\n\n".join(warns))

    st.markdown("<div class='sec-head'>IMPORTAR / EXPORTAR PLANILLA</div>", unsafe_allow_html=True)
    e1, e2 = st.columns(2)
    with e1:
        st.caption("Formato: columna **campo** (o **concepto**) y una columna por ejercicio. "
                   "Acepta números con formato argentino (1.234.567,89) y negativos entre paréntesis.")
        tmpl_years = years_all or [str(new_year)]
        st.download_button("Descargar plantilla Excel", data=blank_template_excel(tmpl_years),
                           file_name="plantilla_concesionaria.xlsx", width="stretch",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if years_all:
            st.download_button("Exportar balances a Excel", data=export_excel(company),
                               file_name=f"{meta['nombre'].replace(' ', '_')}_balances.xlsx", width="stretch",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with e2:
        up = st.file_uploader("Importar Excel / CSV", type=["xlsx", "xls", "csv"],
                              key=f"up_{active}_{st.session_state.ver}")
        if up is not None:
            try:
                imp = parse_upload(up.name, up.getvalue())
                st.caption("Ejercicios detectados: " + ", ".join(sorted(imp)))
                if st.button("Importar a esta empresa", width="stretch"):
                    ys = collect_edits()
                    for y, vals in imp.items():
                        base = ys.get(y, {})
                        base.update({k: v for k, v in vals.items() if v is not None})
                        ys[y] = base
                    company["years"] = dict(sorted(ys.items()))
                    persist(f"Importados {len(imp)} ejercicio(s) desde {up.name}.")
                    bump()
                    st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo leer la planilla: {exc}")
    st.caption("La base se guarda en data/empresas.json. Si la app corre en Streamlit Cloud el disco no es "
               "permanente: descargá el respaldo JSON desde la barra lateral.")

if not sel_year:
    for t in (tab_ov, tab_f, tab_z, tab_c, tab_form, tab_charts):
        with t:
            st.info("Cargá al menos un ejercicio en **CARGA DE BALANCES**.")
    st.stop()

# ───────────── RESUMEN
with tab_ov:
    st.subheader("Piotroski vial")
    rows = [{"señal": cr.code, "grupo": cr.group, "nombre": cr.name,
             "puntos": cr.points if cr.passed is not None else None, "detalle": cr.narrative}
            for cr in f_res.criteria]
    st.dataframe(
        pd.DataFrame(rows), width="stretch", hide_index=True,
        column_config={
            "señal": st.column_config.TextColumn("señal", width="small"),
            "grupo": st.column_config.TextColumn("grupo", width="small"),
            "nombre": st.column_config.TextColumn("nombre", width="medium"),
            "puntos": st.column_config.NumberColumn("puntos", width="small", format="%d"),
            "detalle": st.column_config.TextColumn("detalle", width="large"),
        },
    )
    st.markdown(
        f"**Score:** `{'n/d' if f_res.score is None else f'{f_res.score}/9'}` — {f_res.label}  \n"
        f"Ejercicios: {f_res.prior_year or '—'} → {f_res.year}"
    )
    if f_res.prior_year is None:
        st.info("El F-Score necesita un ejercicio comparativo: cargá el año anterior.")
    elif f_res.missing:
        st.warning("Señales incompletas (cuentan 0): " + ", ".join(f_res.missing))

    st.markdown("**Historia Piotroski vial**")
    st.dataframe(pd.DataFrame(hist_f), width="stretch", hide_index=True)
    _fv = [r["F-Score"] for r in hist_f if r["F-Score"] is not None]
    if _fv:
        st.markdown(f"**F-Score promedio:** `{fmt_ar(_avg(_fv), 2)}/9` en {len(_fv)} ejercicios  \n"
                    f"Mín `{min(_fv)}` · Máx `{max(_fv)}`")

    st.subheader(f"Altman {zname}")
    zrows = [{"factor": cm.code, "nombre": cm.name, "peso": cm.weight,
              "ratio": None if cm.value is None else round(cm.value, 4),
              "aporte": None if cm.contribution is None else round(cm.contribution, 4)}
             for cm in z_res.components]
    if variant == "EM":
        zrows.append({"factor": "EM", "nombre": "Constante mercados emergentes", "peso": None,
                      "ratio": None, "aporte": EM_CONSTANT})
    st.dataframe(
        pd.DataFrame(zrows), width="stretch", hide_index=True,
        column_config={
            "peso": st.column_config.NumberColumn("peso", format="%.2f"),
            "ratio": st.column_config.NumberColumn("ratio", format="%.4f"),
            "aporte": st.column_config.NumberColumn("aporte", format="%.4f"),
        },
    )
    st.markdown(
        f"**Z-Score:** `{'n/d' if z_res.z is None else fmt_ar(z_res.z, 2)}` · {z_res.variant}\n\n"
        f"**Zona:** `{z_res.zone}` — {z_res.zone_detail}  \n"
        f"**Calificación equivalente (EM Score, indicativa):** `{z_res.rating or '—'}`  \n"
        "X4 usa patrimonio neto contable: la empresa no cotiza."
    )
    if z_res.missing:
        st.warning("Factores faltantes: " + ", ".join(z_res.missing))

    st.markdown(f"**Historia Altman {zname}**")
    st.dataframe(pd.DataFrame(hist_z), width="stretch", hide_index=True)
    _zv = [r["Z-Score"] for r in hist_z if r["Z-Score"] is not None]
    if _zv:
        st.markdown(f"**Z-Score promedio:** `{fmt_ar(_avg(_zv), 2)}` en {len(_zv)} ejercicios  \n"
                    f"Mín `{fmt_ar(min(_zv), 2)}` · Máx `{fmt_ar(max(_zv), 2)}`")

# ───────────── PIOTROSKI
with tab_f:
    st.markdown(
        f"Ejercicios **{f_res.prior_year or '—'} → {f_res.year}**. "
        f"Score **{f_res.score if f_res.score is not None else 'n/d'} / 9** · {f_res.label}."
    )
    for grp in ["RENTABILIDAD", "SOLVENCIA", "OPERACIÓN"]:
        st.markdown(f"<div class='sec-head'>{grp}</div>", unsafe_allow_html=True)
        for cr in [c for c in f_res.criteria if c.group == grp]:
            color = "pass" if cr.passed else ("fail" if cr.passed is False else "miss")
            with st.expander(f"{cr.code}  ·  {cr.name}  ·  {_pass_label(cr.passed)}", expanded=False):
                st.markdown(f"<span class='{color}'>{_pass_label(cr.passed)}</span> — {cr.explanation}",
                            unsafe_allow_html=True)
                st.latex(cr.latex)
                st.code(cr.formula, language="text")
                st.markdown(cr.narrative)
                st.json({k: (round(v, 6) if isinstance(v, float) else v) for k, v in cr.inputs.items()})

# ───────────── ALTMAN
with tab_z:
    z_tex = r"Z''_{EM} = 3{,}25 + " if variant == "EM" else r"Z'' = "
    st.markdown(
        "$" + z_tex + r"6{,}56X_1 + 3{,}26X_2 + 6{,}72X_3 + 1{,}05X_4$"
        + (f"  =  **{fmt_ar(z_res.z, 3)}**" if z_res.z is not None else "  =  *incompleto*")
    )
    st.caption(f"{z_res.variant} · {z_res.zone_detail}")
    for cm in z_res.components:
        with st.expander(
            f"{cm.code}  ·  {cm.name}  ·  "
            f"{'—' if cm.contribution is None else f'{cm.weight} × {cm.value:.4f} = {cm.contribution:.4f}'}",
            expanded=False,
        ):
            st.latex(cm.latex)
            st.code(cm.formula, language="text")
            st.write(cm.explanation)
            st.json({k: (round(v, 6) if isinstance(v, float) else v) for k, v in cm.inputs.items()})

    st.markdown("<div class='sec-head'>CALIFICACIÓN EQUIVALENTE · EM SCORE (ALTMAN, 2005)</div>",
                unsafe_allow_html=True)
    em_now = None if z_res.z is None else (z_res.z if variant == "EM" else z_res.z + EM_CONSTANT)
    tbl = pd.DataFrame([{"EM Score ≥": lim, "calificación": r} for lim, r in EM_RATING_TABLE]
                       + [{"EM Score ≥": None, "calificación": "D"}])
    tbl["actual"] = ["◀" if r == z_res.rating else "" for r in tbl["calificación"]]
    st.dataframe(tbl, width="stretch", hide_index=True, height=300,
                 column_config={"EM Score ≥": st.column_config.NumberColumn(format="%.2f")})
    st.caption(f"EM Score del ejercicio: {fmt_ar(em_now, 2)}. Equivalencia orientativa, no reemplaza "
               "una calificación de riesgo.")

# ───────────── CONCESIÓN
REFS = [
    # clave, nombre, formato, verde, ámbar, mayor_es_mejor, comentario
    ("dscr", "DSCR", "x", dscr_min, 1.0, True, "Flujo disponible / servicio de deuda"),
    ("dn_ebitda", "Deuda neta / EBITDA", "x", 3.0, 5.0, False, "Años de EBITDA para cancelar la deuda"),
    ("cobertura_intereses", "EBITDA / Intereses", "x", 3.0, 1.5, True, "Cobertura de intereses"),
    ("margen_ebitda", "Margen EBITDA", "pct", 0.50, 0.30, True, "Sin ingresos de construcción CINIIF 12"),
    ("cola_concesion", "Cola de concesión (años)", "n1", 3.0, 0.0, True,
     "Años remanentes − años de repago con CFADS"),
    ("capex_amort", "Capex / Amortizaciones", "x", 1.0, 0.7, True, "Reinversión en el activo concesionado"),
    ("liquidez", "Liquidez corriente", "x", 1.0, 0.6, True, "Activo corriente / pasivo corriente"),
]


def _fmt_kind(v, kind):
    if kind == "pct":
        return fmt_pct(v)
    if kind == "x":
        return fmt_x(v)
    if kind == "n1":
        return fmt_ar(v, 1)
    return fmt_ar(v)


def _state(v, green, amber, higher):
    if _bad(v):
        return "ND"
    if higher:
        return "OK" if v >= green else ("ALERTA" if v >= amber else "CRITICO")
    return "OK" if v <= green else ("ALERTA" if v <= amber else "CRITICO")


with tab_c:
    st.subheader(f"Semáforo sectorial · {sel_year}")
    html = ["<table class='sem'><tr><th>INDICADOR</th><th style='text-align:right'>VALOR</th>"
            "<th>ESTADO</th><th>REFERENCIA</th><th>LECTURA</th></tr>"]
    for key, name, kind, green, amber, higher, note in REFS:
        v = d_sel.get(key)
        s = _state(v, green, amber, higher)
        op = "≥" if higher else "≤"
        ref = f"OK {op} {_fmt_kind(green, kind)} · alerta {op} {_fmt_kind(amber, kind)}"
        lbl = {"OK": "OK", "ALERTA": "ALERTA", "CRITICO": "CRÍTICO", "ND": "N/D"}[s]
        html.append(f"<tr><td>{name}</td><td class='v'>{_fmt_kind(v, kind)}</td>"
                    f"<td><span class='dot-{s}'>●</span> {lbl}</td><td>{ref}</td><td>{note}</td></tr>")
    html.append("</table>")
    st.markdown("".join(html), unsafe_allow_html=True)
    st.caption("Referencias orientativas de project finance vial; ajustarlas a los covenants de cada contrato.")

    st.markdown("<div class='sec-head'>INDICADORES POR EJERCICIO</div>", unsafe_allow_html=True)
    METRICS = [
        ("ingresos_operativos", f"Ingresos operativos ({unit_lbl})", "n0"),
        ("ebitda", f"EBITDA ({unit_lbl})", "n0"),
        ("margen_ebitda", "Margen EBITDA", "pct"),
        ("deuda_neta", f"Deuda neta ({unit_lbl})", "n0"),
        ("dn_ebitda", "Deuda neta / EBITDA", "x"),
        ("cobertura_intereses", "EBITDA / Intereses", "x"),
        ("cfads", f"CFADS ({unit_lbl})", "n0"),
        ("servicio_deuda", f"Servicio de deuda ({unit_lbl})", "n0"),
        ("dscr", "DSCR", "x"),
        ("anios_repago", "Años de repago (DN / CFADS)", "n1"),
        ("cola_concesion", "Cola de concesión (años)", "n1"),
        ("capex_amort", "Capex / Amortizaciones", "x"),
        ("liquidez", "Liquidez corriente", "x"),
        ("roa", "ROA", "pct"),
        ("transito", "Tránsito pagante (veh. eq.)", "n0"),
        ("tmda", "TMDA (veh. eq. / día)", "n0"),
        ("ingreso_por_veh", f"Ingreso de peaje por vehículo ({meta.get('moneda', 'ARS')} {meta.get('unidad', '')})", "n4"),
        ("ingreso_por_km", f"Ingresos operativos por km ({unit_lbl})", "n1"),
    ]
    tbl = {"Indicador": [m[1] for m in METRICS]}
    for r in srows:
        col = []
        for key, _, kind in METRICS:
            v = r.get(key)
            col.append(fmt_ar(v, 4) if kind == "n4" else
                       fmt_ar(v, 0) if kind == "n0" else _fmt_kind(v, kind))
        tbl[r["Ejercicio"]] = col
    st.dataframe(pd.DataFrame(tbl), width="stretch", hide_index=True, height=36 * (len(METRICS) + 1) + 4)
    st.caption("CFADS = EBITDA − capex de mantenimiento − impuestos pagados. "
               "Servicio de deuda = intereses + amortización de capital.")

# ───────────── FÓRMULAS
with tab_form:
    st.subheader("Piotroski vial (adaptación del F-Score de Piotroski, 2000)")
    st.markdown(
        rf"""
Nueve señales binarias. $F=\sum_{{i=1}}^{{9}} F_i \in \{{0,\ldots,9\}}$. Requiere el ejercicio actual y el anterior.

**Rentabilidad**
- $F_1\;ROA=1$ si $RN_t / \overline{{AT}}_t > 0$
- $F_2\;CFO=1$ si $CFO_t > 0$
- $F_3\;\Delta MARGEN=1$ si $\frac{{EBITDA_t}}{{I_t}} > \frac{{EBITDA_{{t-1}}}}{{I_{{t-1}}}}$ — *reemplaza el margen bruto*
- $F_4\;ACCRUAL=1$ si $CFO_t > RN_t$

**Solvencia y liquidez**
- $F_5\;\Delta DN/EBITDA=1$ si $\frac{{DN_t}}{{EBITDA_t}} < \frac{{DN_{{t-1}}}}{{EBITDA_{{t-1}}}}$ — *reemplaza deuda LP / activo*
- $F_6\;\Delta LIQUIDEZ=1$ si $\frac{{AC_t}}{{PC_t}} > \frac{{AC_{{t-1}}}}{{PC_{{t-1}}}}$
- $F_7\;DSCR=1$ si $\frac{{EBITDA_t - Capex^{{mant}}_t - Imp_t}}{{Int_t + K_t}} \geq {dscr_min:.2f}$ — *reemplaza la emisión de acciones*

**Operación**
- $F_8\;\Delta TRÁNSITO=1$ si $TR_t > TR_{{t-1}}$ — *señal nueva, propia del sector*
- $F_9\;\Delta ROTACIÓN=1$ si $\frac{{I_t}}{{\overline{{AT}}_t}} > \frac{{I_{{t-1}}}}{{\overline{{AT}}_{{t-1}}}}$

$I$ = ingresos operativos (peaje + otros), **sin** ingresos de construcción CINIIF 12.
Lectura: 8–9 calidad alta, 5–7 media, 0–4 baja.

**Por qué se adaptó.** Una concesionaria no tiene un costo de ventas comparable (el margen bruto
no informa), su activo principal es un intangible que se amortiza hasta el fin del contrato (deuda/activo
pierde sentido), y al no cotizar la dilución accionaria es irrelevante. En su lugar entran las métricas
que miran bancos, fiduciarios y calificadoras: margen EBITDA, deuda neta/EBITDA, DSCR y tránsito.
        """
    )
    st.subheader("Altman Z'' (Altman, 1995) y Z''-EM (Altman, 2005)")
    st.markdown(
        r"""
$$
Z'' = 6{,}56\,X_1 + 3{,}26\,X_2 + 6{,}72\,X_3 + 1{,}05\,X_4 \qquad Z''_{EM} = 3{,}25 + Z''
$$

| Factor | Definición | Peso |
|---|---|---|
| $X_1$ | Capital de trabajo / Activo total | 6,56 |
| $X_2$ | Resultados acumulados / Activo total | 3,26 |
| $X_3$ | EBIT / Activo total | 6,72 |
| $X_4$ | Patrimonio neto **contable** / Pasivo total | 1,05 |

Cortes $Z''$: $>2{,}60$ zona segura · $1{,}10$–$2{,}60$ zona gris · $<1{,}10$ zona de riesgo.
Cortes $Z''_{EM}$: $>5{,}85$ · $4{,}35$–$5{,}85$ · $<4{,}35$.

**Por qué Z'' y no el Z original.** El Z de 1968 necesita valor de mercado del patrimonio (no existe en
una empresa que no cotiza) e incluye $X_5$ = ventas / activo, que castiga a los negocios intensivos en
activos de larga vida como una concesión vial por su modelo de negocio y no por su riesgo. El Z''
reemplaza el valor de mercado por el patrimonio contable y elimina $X_5$. La variante EM ancla el score
a calificaciones de bonos de emisores de mercados emergentes.

**Advertencias sectoriales.** El capital de trabajo de una concesión suele ser negativo (penaliza $X_1$);
el ajuste por inflación modifica resultados acumulados y patrimonio ($X_2$, $X_4$), por eso los balances
deben cargarse en moneda homogénea. Leer el Z'' junto con el DSCR y la cola de concesión.
        """
    )

# ───────────── GRÁFICOS
with tab_charts:
    st.subheader("Evolución de los indicadores")
    st.caption("Todos los ejercicios cargados, del más antiguo al más reciente.")
    for ch, cap in [
        (piotroski_chart(hist_f), None),
        (piotroski_criteria_chart(hist_f), "Cada segmento es una señal aprobada (1 punto). La altura total es el F-Score."),
        (altman_chart(hist_z, variant), "X4 usa patrimonio neto contable / pasivo total."),
        (altman_contrib_chart(hist_z, variant), "Barras: peso × ratio de cada factor (las negativas bajan el Z). "
                                                "El rombo ámbar es el Z-Score total."),
    ]:
        if ch is not None:
            st.altair_chart(ch, width="stretch")
            if cap:
                st.caption(cap)
    st.markdown("<div class='sec-head'>INDICADORES DE LA CONCESIÓN</div>", unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    with g1:
        ch = dscr_chart(srows, dscr_min)
        if ch is not None:
            st.altair_chart(ch, width="stretch")
        else:
            st.info("Faltan datos para el DSCR.")
    with g2:
        ch = leverage_chart(srows)
        if ch is not None:
            st.altair_chart(ch, width="stretch")
        else:
            st.info("Faltan datos para Deuda neta / EBITDA.")
    ch = traffic_chart(srows)
    if ch is not None:
        st.altair_chart(ch, width="stretch")
