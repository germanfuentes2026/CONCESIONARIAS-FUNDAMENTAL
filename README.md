# Concession Terminal

Análisis fundamental de concesionarias viales que no cotizan en bolsa. Los balances se cargan a mano
(o desde una planilla Excel/CSV); no hay descargas de ninguna web.

## Cómo correrla

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Flujo

1. Barra lateral → **Nueva empresa** (o **Cargar empresa demo**, con datos ficticios).
2. Pestaña **CARGA DE BALANCES** → agregar ejercicios y completar la grilla
   (o descargar la plantilla Excel, llenarla e importarla) → **Guardar balances**.
3. Elegir el ejercicio en la barra lateral y revisar RESUMEN, PIOTROSKI VIAL, ALTMAN Z'',
   CONCESIÓN y GRÁFICOS.

La base queda en `data/empresas.json`. En Streamlit Cloud el disco no es permanente:
usar **Descargar base (JSON)** / **Restaurar base** de la barra lateral.

## Modelos

**Piotroski vial (9 señales):** ROA > 0 · CFO > 0 · ΔMargen EBITDA · CFO > RN ·
ΔDeuda neta/EBITDA · ΔLiquidez · DSCR ≥ umbral · ΔTránsito pagante · ΔRotación del activo.

**Altman Z'' (1995) / Z''-EM (2005):** 6,56 X1 + 3,26 X2 + 6,72 X3 + 1,05 X4 (+3,25 en EM),
con patrimonio neto contable en X4 y sin X5 (ventas/activo).

Cargar los balances en moneda homogénea (RT 6 / NIC 29) y excluir de los ingresos operativos
los ingresos por construcción CINIIF 12 (tienen su propia fila).

## Estructura

```
app.py              interfaz Streamlit
src/model.py        campos de carga y métricas derivadas (EBITDA, deuda neta, DSCR, cola…)
src/piotroski.py    Piotroski vial
src/altman.py       Altman Z'' / Z''-EM y rating equivalente
src/storage.py      JSON local + importación/exportación Excel/CSV
data/demo_concesionaria.json   empresa de ejemplo (ficticia)
.streamlit/config.toml         tema oscuro (necesario para que la grilla de carga combine)
```
