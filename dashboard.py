import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

st.set_page_config(page_title="ELEVA vs STOXX Europe 600", layout="wide")
st.title("📊 ELEVA European Selection I EUR Acc vs STOXX Europe 600 Net Return")

# =====================
# Stockage persistant des NAV ELEVA
# On utilise un fichier local dans le repo Streamlit Cloud
# =====================
NAV_STORE_PATH = "eleva_nav_store.json"

def save_nav(df: pd.Series):
    """Sauvegarde la série NAV en JSON"""
    data = {
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "values": [float(v) for v in df.values]
    }
    with open(NAV_STORE_PATH, "w") as f:
        json.dump(data, f)

def load_nav_stored() -> pd.Series | None:
    """Charge la série NAV sauvegardée"""
    if not os.path.exists(NAV_STORE_PATH):
        return None
    try:
        with open(NAV_STORE_PATH, "r") as f:
            data = json.load(f)
        index = pd.to_datetime(data["dates"])
        series = pd.Series(data["values"], index=index, name="NAV")
        series.index = pd.DatetimeIndex(series.index)
        return series.sort_index()
    except Exception:
        return None

# =====================
# Sidebar
# =====================
start = st.sidebar.date_input("Date de début", datetime(2015, 1, 26))

st.sidebar.markdown("---")
st.sidebar.subheader("📂 Mise à jour NAV ELEVA")
st.sidebar.markdown("""
Uploadez un CSV avec les colonnes :
- `Date` (format DD/MM/YYYY ou YYYY-MM-DD)
- `NAV` (valeur liquidative)
""")

uploaded = st.sidebar.file_uploader("Uploader un CSV de NAV", type=["csv"])

if uploaded is not None:
    try:
        df_up = pd.read_csv(uploaded)
        # Détecter la colonne date
        date_col = next((c for c in df_up.columns if "date" in c.lower()), df_up.columns[0])
        # Détecter la colonne valeur
        val_col = next((c for c in df_up.columns if c.lower() not in [date_col.lower()]), df_up.columns[1])
        df_up[date_col] = pd.to_datetime(df_up[date_col], dayfirst=True)
        df_up = df_up.set_index(date_col).sort_index()
        nav_series = df_up[val_col].squeeze().astype(float)

        # Fusionner avec les données existantes
        existing = load_nav_stored()
        if existing is not None:
            nav_series = pd.concat([existing, nav_series])
            nav_series = nav_series[~nav_series.index.duplicated(keep="last")]
            nav_series = nav_series.sort_index()

        save_nav(nav_series)
        st.sidebar.success(f"✅ {len(nav_series)} points de NAV sauvegardés (du {nav_series.index[0].strftime('%d/%m/%Y')} au {nav_series.index[-1].strftime('%d/%m/%Y')})")
        st.cache_data.clear()
    except Exception as e:
        st.sidebar.error(f"Erreur lors du chargement du CSV : {e}")

# Afficher le statut des données stockées
stored_nav = load_nav_stored()
if stored_nav is not None:
    st.sidebar.info(f"📊 Données en base : {len(stored_nav)} points\n\n{stored_nav.index[0].strftime('%d/%m/%Y')} → {stored_nav.index[-1].strftime('%d/%m/%Y')}")
else:
    st.sidebar.warning("⚠️ Aucune donnée ELEVA en base. Uploadez un CSV.")

# =====================
# Chargement STOXX 600
# =====================
STOXX600_TICKER = "^STOXX"

@st.cache_data(ttl=3600)
def load_stoxx(ticker, start):
    try:
        tmp = yf.download(ticker, start=start, auto_adjust=True, progress=False)
        if tmp.empty:
            return None
        col = "Close" if "Close" in tmp.columns else tmp.columns[0]
        return tmp[col].squeeze()
    except Exception:
        return None

with st.spinner("Chargement STOXX 600…"):
    stoxx_raw = load_stoxx(STOXX600_TICKER, start)

if stoxx_raw is None:
    st.error("⚠️ Impossible de charger les données STOXX 600 (^STOXX).")
    st.stop()

# =====================
# Préparer les séries sur la période sélectionnée
# =====================
def build_index(series: pd.Series, start) -> pd.Series:
    series = series.dropna().squeeze()
    series = series[series.index >= pd.Timestamp(start)]
    if series.empty:
        return series
    return series / float(series.iloc[0]) * 100

stoxx_index = build_index(stoxx_raw, start)

eleva_index = None
if stored_nav is not None:
    eleva_index = build_index(stored_nav, start)
    if eleva_index.empty:
        st.warning("⚠️ Pas de données ELEVA sur la période sélectionnée. Changez la date de début.")
        eleva_index = None

if eleva_index is not None:
    common = eleva_index.index.intersection(stoxx_index.index)
    eleva_index = eleva_index.loc[common]
    stoxx_index_plot = stoxx_index.loc[common]
else:
    stoxx_index_plot = stoxx_index

# =====================
# Graphique performance cumulée
# =====================
fig = go.Figure()

if eleva_index is not None:
    fig.add_trace(go.Scatter(
        x=eleva_index.index, y=eleva_index,
        name="ELEVA European Selection I EUR Acc",
        line=dict(width=3, color="#1f77b4")
    ))

fig.add_trace(go.Scatter(
    x=stoxx_index_plot.index, y=stoxx_index_plot,
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
if eleva_index is not None:
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
            s = (float(stoxx_index_plot.iloc[-1]) / float(stoxx_index_plot.iloc[0]) - 1) * 100
        elif days is None:
            e = perf_ytd(eleva_index)
            s = perf_ytd(stoxx_index_plot)
        else:
            e = perf_safe(eleva_index, days)
            s = perf_safe(stoxx_index_plot, days)
        rows.append({
            "Période": label,
            "ELEVA I EUR Acc": fmt(e),
            "STOXX 600 NR": fmt(s),
            "Surperformance ELEVA": fmt(e - s),
        })

    st.subheader("📈 Tableau des performances")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("📉 Statistiques de risque (annualisées)")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**ELEVA European Selection I EUR Acc**")
        for k, v in risk_stats(eleva_index).items():
            st.metric(k, v)
    with col2:
        st.markdown("**STOXX Europe 600 Net Return**")
        for k, v in risk_stats(stoxx_index_plot).items():
            st.metric(k, v)

    fig_dd = go.Figure()
    dd = lambda s: (s - s.cummax()) / s.cummax() * 100
    fig_dd.add_trace(go.Scatter(x=eleva_index.index, y=dd(eleva_index),
        name="ELEVA", fill="tozeroy", line=dict(color="#1f77b4", width=1.5)))
    fig_dd.add_trace(go.Scatter(x=stoxx_index_plot.index, y=dd(stoxx_index_plot),
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
| ELEVA European Selection I EUR Acc | CSV manuel | ISIN LU1111643042 — NAV uploadées manuellement |
| STOXX Europe 600 Net Return | `^STOXX` Yahoo Finance | Indice Total Return Net en EUR |

- **Base 100** : rebasé à 100 à la date de début sélectionnée dans la sidebar.
- **NAV ELEVA** : persistantes entre les sessions. Uploadez un nouveau CSV pour mettre à jour.
- Le nouveau CSV est **fusionné** avec les données existantes (pas d'écrasement).
- **Ratio de Sharpe** : sans taux sans risque (approximation).
""")
st.caption("STOXX 600 : Yahoo Finance (yfinance) | ELEVA : NAV manuelles — Mise à jour sur upload")
