import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

st.set_page_config(page_title="ELEVA vs STOXX Europe 600", layout="wide")
st.title("📊 ELEVA European Selection I EUR Acc vs STOXX Europe 600 Net Return")

# =====================
# Stockage persistant (JSON)
# =====================
STORE_PATH = "nav_store.json"

def save_data(eleva: pd.Series, stoxx: pd.Series):
    data = {
        "eleva_dates":  [d.strftime("%Y-%m-%d") for d in eleva.index],
        "eleva_values": [float(v) for v in eleva.values],
        "stoxx_dates":  [d.strftime("%Y-%m-%d") for d in stoxx.index],
        "stoxx_values": [float(v) for v in stoxx.values],
    }
    with open(STORE_PATH, "w") as f:
        json.dump(data, f)

def load_data():
    if not os.path.exists(STORE_PATH):
        return None, None
    try:
        with open(STORE_PATH, "r") as f:
            data = json.load(f)
        eleva = pd.Series(
            data["eleva_values"],
            index=pd.DatetimeIndex(pd.to_datetime(data["eleva_dates"])),
            name="ELEVA"
        ).sort_index()
        stoxx = pd.Series(
            data["stoxx_values"],
            index=pd.DatetimeIndex(pd.to_datetime(data["stoxx_dates"])),
            name="STOXX"
        ).sort_index()
        return eleva, stoxx
    except Exception:
        return None, None

# =====================
# Sidebar — upload Excel
# =====================
start = st.sidebar.date_input("Date de début", datetime(2015, 1, 26))

st.sidebar.markdown("---")
st.sidebar.subheader("📂 Mise à jour des données")
st.sidebar.markdown("""
Uploadez un fichier Excel avec :
- **Colonne A** : Date
- **Colonne B** : NAV ELEVA European Selection
- **Colonne C** : NAV STOXX Europe 600
- La **ligne 1** contient les en-têtes
""")

uploaded = st.sidebar.file_uploader("Uploader un fichier Excel", type=["xlsx", "xls"])

if uploaded is not None:
    try:
        df_up = pd.read_excel(uploaded, header=0)

        # Colonnes A, B, C = positions 0, 1, 2
        date_col  = df_up.columns[0]
        eleva_col = df_up.columns[1]
        stoxx_col = df_up.columns[2]

        df_up[date_col] = pd.to_datetime(df_up[date_col], dayfirst=True)
        df_up = df_up.set_index(date_col).sort_index()

        new_eleva = df_up[eleva_col].astype(float).dropna()
        new_stoxx = df_up[stoxx_col].astype(float).dropna()

        # Fusionner avec les données existantes
        existing_eleva, existing_stoxx = load_data()

        if existing_eleva is not None:
            new_eleva = pd.concat([existing_eleva, new_eleva])
            new_eleva = new_eleva[~new_eleva.index.duplicated(keep="last")].sort_index()
        if existing_stoxx is not None:
            new_stoxx = pd.concat([existing_stoxx, new_stoxx])
            new_stoxx = new_stoxx[~new_stoxx.index.duplicated(keep="last")].sort_index()

        save_data(new_eleva, new_stoxx)
        st.cache_data.clear()

        st.sidebar.success(
            f"✅ Données sauvegardées !\n\n"
            f"**ELEVA** : {len(new_eleva)} points "
            f"({new_eleva.index[0].strftime('%d/%m/%Y')} → {new_eleva.index[-1].strftime('%d/%m/%Y')})\n\n"
            f"**STOXX** : {len(new_stoxx)} points "
            f"({new_stoxx.index[0].strftime('%d/%m/%Y')} → {new_stoxx.index[-1].strftime('%d/%m/%Y')})"
        )
    except Exception as e:
        st.sidebar.error(f"Erreur lors du chargement du fichier : {e}")

# Statut des données en base
stored_eleva, stored_stoxx = load_data()
if stored_eleva is not None:
    st.sidebar.info(
        f"📊 **Données en base**\n\n"
        f"ELEVA : {len(stored_eleva)} pts — "
        f"{stored_eleva.index[0].strftime('%d/%m/%Y')} → {stored_eleva.index[-1].strftime('%d/%m/%Y')}\n\n"
        f"STOXX : {len(stored_stoxx)} pts — "
        f"{stored_stoxx.index[0].strftime('%d/%m/%Y')} → {stored_stoxx.index[-1].strftime('%d/%m/%Y')}"
    )
else:
    st.sidebar.warning("⚠️ Aucune donnée en base. Uploadez un fichier Excel.")

# =====================
# Vérification données disponibles
# =====================
if stored_eleva is None or stored_stoxx is None:
    st.warning("⚠️ Aucune donnée disponible. Uploadez un fichier Excel via la sidebar.")
    st.stop()

# =====================
# Rebasage dynamique à 100
# =====================
def build_index(series: pd.Series, start) -> pd.Series:
    series = series.dropna().squeeze()
    series = series[series.index >= pd.Timestamp(start)]
    if series.empty:
        return series
    return series / float(series.iloc[0]) * 100

eleva_index = build_index(stored_eleva, start)
stoxx_index = build_index(stored_stoxx, start)

if eleva_index.empty or stoxx_index.empty:
    st.warning("⚠️ Pas de données sur la période sélectionnée. Changez la date de début.")
    st.stop()

# Aligner sur les dates communes
common = eleva_index.index.intersection(stoxx_index.index)
eleva_index = eleva_index.loc[common]
stoxx_index = stoxx_index.loc[common]

# =====================
# Graphique performance cumulée
# =====================
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=eleva_index.index, y=eleva_index,
    name="ELEVA European Selection I EUR Acc",
    line=dict(width=3, color="#1f77b4")
))
fig.add_trace(go.Scatter(
    x=stoxx_index.index, y=stoxx_index,
    name="STOXX Europe 600 Net Return",
    line=dict(width=3, color="#d62728", dash="dash")
))
fig.update_layout(
    height=550,
    template="plotly_white",
    title=f"Performance cumulée (base 100 au {pd.Timestamp(start).strftime('%d/%m/%Y')})",
    yaxis_title="Valeur de l'indice (base 100)",
    xaxis_title="Date",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified"
)
st.plotly_chart(fig, use_container_width=True)

# =====================
# Utilitaires
# =====================
def fmt(v):
    try:
        v = float(v)
        return f"{v:+.2f}%" if v == v else "N/A"
    except Exception:
        return "N/A"

def perf_safe(series, days):
    try:
        cutoff = series.index[-1] - timedelta(days=days)
        if cutoff < series.index[0]:
            cutoff = series.index[0]
        sv = float(series[series.index >= cutoff].iloc[0])
        ev = float(series.iloc[-1])
        return (ev / sv - 1) * 100
    except Exception:
        return float("nan")

def perf_ytd(series):
    try:
        year_start = pd.Timestamp(series.index[-1].year, 1, 1)
        sub = series[series.index >= year_start]
        if sub.empty:
            return float("nan")
        return (float(sub.iloc[-1]) / float(sub.iloc[0]) - 1) * 100
    except Exception:
        return float("nan")

def risk_stats(series):
    ret = series.pct_change().dropna()
    std = float(ret.std())
    mean = float(ret.mean())
    vol = std * (252 ** 0.5) * 100
    sharpe = (mean * 252) / (std * (252 ** 0.5)) if std > 0 else float("nan")
    roll_max = series.cummax()
    max_dd = float(((series - roll_max) / roll_max).min()) * 100
    return {
        "Volatilité annualisée": f"{vol:.2f}%",
        "Ratio de Sharpe (approx.)": f"{sharpe:.2f}",
        "Drawdown max": f"{max_dd:.2f}%"
    }

# =====================
# Tableau des performances
# =====================
periods = {
    "Hier (J-1)": 1,
    "1 semaine": 7,
    "1 mois": 30,
    "3 mois": 90,
    "YTD": None,
    "6 mois": 180,
    "1 an": 365,
    "3 ans": 3 * 365,
    "Depuis le début": -1,
}

rows = []
for label, days in periods.items():
    if days == -1:
        e = (float(eleva_index.iloc[-1]) / float(eleva_index.iloc[0]) - 1) * 100
        s = (float(stoxx_index.iloc[-1]) / float(stoxx_index.iloc[0]) - 1) * 100
    elif days is None:
        e = perf_ytd(eleva_index)
        s = perf_ytd(stoxx_index)
    else:
        e = perf_safe(eleva_index, days)
        s = perf_safe(stoxx_index, days)
    rows.append({
        "Période": label,
        "ELEVA I EUR Acc": fmt(e),
        "STOXX 600 NR": fmt(s),
        "Surperformance ELEVA": fmt(e - s),
    })

st.subheader("📈 Tableau des performances")
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# =====================
# Statistiques de risque
# =====================
st.subheader("📉 Statistiques de risque (annualisées)")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**ELEVA European Selection I EUR Acc**")
    for k, v in risk_stats(eleva_index).items():
        st.metric(k, v)
with col2:
    st.markdown("**STOXX Europe 600 Net Return**")
    for k, v in risk_stats(stoxx_index).items():
        st.metric(k, v)

# =====================
# Graphique drawdown
# =====================
fig_dd = go.Figure()
dd = lambda s: (s - s.cummax()) / s.cummax() * 100
fig_dd.add_trace(go.Scatter(x=eleva_index.index, y=dd(eleva_index),
    name="ELEVA", fill="tozeroy", line=dict(color="#1f77b4", width=1.5)))
fig_dd.add_trace(go.Scatter(x=stoxx_index.index, y=dd(stoxx_index),
    name="STOXX 600 NR", fill="tozeroy", line=dict(color="#d62728", width=1.5, dash="dash")))
fig_dd.update_layout(height=350, template="plotly_white", title="Drawdown (%)",
    yaxis_title="Drawdown (%)", hovermode="x unified")
st.plotly_chart(fig_dd, use_container_width=True)

# =====================
# Notes méthodologiques
# =====================
st.subheader("ℹ️ Notes méthodologiques")
st.markdown("""
| Instrument | Source | Description |
|---|---|---|
| ELEVA European Selection I EUR Acc | Excel — Colonne B | ISIN LU1111643042 — NAV uploadées manuellement |
| STOXX Europe 600 Net Return | Excel — Colonne C | NAV uploadées manuellement |

- **Base 100** : les deux séries sont rebasées à 100 à la date de début sélectionnée.
- **Fusion** : chaque nouvel upload est fusionné avec les données existantes.
- **Ratio de Sharpe** : calculé sans taux sans risque (approximation).
- **Drawdown** : par rapport au plus haut historique glissant sur la période sélectionnée.
""")
st.caption("Données : fichier Excel uploadé manuellement — Mise à jour sur upload")
