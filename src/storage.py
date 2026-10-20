"""Persistencia local (JSON) e importación / exportación Excel-CSV de balances cargados a mano."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

from .model import FIELDS, FIELD_BY_KEY, LABEL_TO_KEY, num

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "empresas.json"


def empty_company(nombre: str) -> dict:
    return {
        "meta": {"nombre": nombre, "corredor": "", "cuit": "", "moneda": "ARS",
                 "unidad": "miles", "mes_cierre": 12},
        "years": {},
    }


def load_db(path: Path = DATA_FILE) -> dict:
    if path.exists():
        try:
            db = json.loads(path.read_text(encoding="utf-8"))
            db.setdefault("empresas", {})
            return db
        except (json.JSONDecodeError, OSError):
            pass
    return {"empresas": {}}


def save_db(db: dict, path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def company_to_frame(company: dict) -> pd.DataFrame:
    """Filas = conceptos, columnas = ejercicios (ascendente)."""
    years = sorted(company.get("years", {}).keys())
    data = {y: [num(company["years"][y].get(f.key)) for f in FIELDS] for y in years}
    df = pd.DataFrame(data, index=[f.label for f in FIELDS], dtype="float64")
    df.index.name = "Concepto"
    return df


def frame_to_years(df: pd.DataFrame) -> dict:
    years: dict = {}
    for col in df.columns:
        y = str(col).strip()
        if not y:
            continue
        vals = {}
        for label, v in df[col].items():
            key = LABEL_TO_KEY.get(label, label if label in FIELD_BY_KEY else None)
            if key:
                vals[key] = num(v)
        years[y] = vals
    return years


def template_frame(years: list[str]) -> pd.DataFrame:
    df = pd.DataFrame({"campo": [f.key for f in FIELDS],
                       "concepto": [f.label for f in FIELDS],
                       "seccion": [f.section for f in FIELDS]})
    for y in years:
        df[y] = None
    return df


def export_excel(company: dict) -> bytes:
    years = sorted(company.get("years", {}).keys())
    df = template_frame(years)
    for y in years:
        df[y] = [num(company["years"][y].get(k)) for k in df["campo"]]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="balances", index=False)
        meta = pd.DataFrame(list(company.get("meta", {}).items()), columns=["dato", "valor"])
        meta.to_excel(xw, sheet_name="empresa", index=False)
        ws = xw.sheets["balances"]
        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["B"].width = 62
        ws.column_dimensions["C"].width = 34
        from openpyxl.utils import get_column_letter
        for i in range(len(years)):
            ws.column_dimensions[get_column_letter(4 + i)].width = 18
    return buf.getvalue()


def blank_template_excel(years: list[str]) -> bytes:
    return export_excel({"meta": empty_company("Nueva concesionaria")["meta"],
                         "years": {y: {} for y in years}})


def parse_upload(name: str, raw: bytes) -> dict:
    """Lee una planilla (xlsx/csv) con columna 'campo' o 'concepto' y una columna por ejercicio."""
    if name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw), sheet_name=0)
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        sep = ";" if text.count(";") > text.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
    cols = {str(c).strip().lower(): c for c in df.columns}
    key_col = cols.get("campo")
    label_col = cols.get("concepto")
    if key_col is None and label_col is None:
        raise ValueError("La planilla debe tener una columna 'campo' o 'concepto'.")
    year_cols = [c for c in df.columns if str(c).strip().lower() not in ("campo", "concepto", "seccion", "sección")]
    years: dict = {}
    for yc in year_cols:
        y = str(yc).strip()
        if y.endswith(".0"):
            y = y[:-2]
        vals = {}
        for _, row in df.iterrows():
            key = None
            if key_col is not None and str(row[key_col]).strip() in FIELD_BY_KEY:
                key = str(row[key_col]).strip()
            elif label_col is not None:
                key = LABEL_TO_KEY.get(str(row[label_col]).strip())
            if key:
                vals[key] = num(row[yc])
        if any(v is not None for v in vals.values()):
            years[y] = vals
    if not years:
        raise ValueError("No se encontraron ejercicios con datos.")
    return years
