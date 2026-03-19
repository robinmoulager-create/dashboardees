import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="ELEVA vs STOXX Europe 600", layout="wide")
st.title("📊 ELEVA European Selection I EUR Acc vs STOXX Europe 600 Net Return")

# =====================
# Sidebar — date de départ (défaut = date de création du fonds)
# =====================
start = st.sidebar.date_input("Date de début", datetime(2015, 1, 26))

ELEVA_TICKER = "0P00015D09.F"
STOXX600_TICKER = "^STOXX"

# =====================
# Chargement des données
# =====================
@st.cache_data(ttl=3600)
def load_ticker(ticker, start):
    try:
        tmp = yf.download(ticker, start=start, auto_adjust=True, progress=False)
        if tmp.empty:
            return None
        col = "Close" if "Close" in tmp.columns else tmp.columns[0]
        return tmp[col].squeeze()
    except Exception:
        return None

with st.spinner("Chargement des données ELEVA…"):
    eleva_raw = load_ticker(ELEVA_TICKER, start)

with st.spinner("Chargement des données STOXX 600…"):
    stoxx_raw = load_ticker(STOXX600_TICKER, start)

# =====================
# Gestion erreur ELEVA
# =====================
if eleva_raw is None:
    st.error("⚠️ Impossible de charger les données ELEVA (0P00015D09.F). Uploadez un CSV.")
    uploaded = st.file_uploader("📂 CSV (colonnes : Date, VL)", type=["csv"])
    if uploaded is not None:
        df_upload = pd.read_csv(uploaded, parse_dates=["Date"], index_col="Date")
        eleva_raw = df_upload.iloc[:, 0].squeeze()
    else:
        st.info("Seul le benchmark STOXX 600 sera affiché.")

if stoxx_raw is None:
    st.error("⚠️ Impossible de charger les données STOXX 600 (^STOXX).")
    st.stop()

# =====================
# Rebasage dynamique à 100 sur la période sélectionnée
# =====================
def build_index(series: pd.Series) -> pd.Series:
    series = series.dropna().squeeze()
    # Filtrer à partir de la date choisie
    series = series[series.index >= pd.Timestamp(start)]
    if series.empty:
        return series
    # Rebaser à 100 sur le premier point disponible
    return series / float(series.iloc[0]) * 100

stoxx_index = build_index(stoxx_raw)

if eleva_raw is not None:
    eleva_index = build_index(eleva_raw)
    common = eleva_index.index.intersection(stoxx_index.index)
    eleva_index = eleva_index.loc[common]
    stoxx_index_plot = stoxx_index.loc[common]
else:
    stoxx_index_plot = stoxx_index

# =====================
# Graphique performance cumulée (base 100)
# =====================
fig = go.Figure()

if eleva_raw is not None:
    fig.add_trace(go.Scatter(
        x=eleva_index.index, y=eleva_index,
        name="ELEVA European Selection I EUR Acc",
        line=dict(width=3, color="#1f77b4")
    ))

fig.add_trace(go.Scatter(
    x=stoxx_index_plot.index, y=stoxx_index_plot,
    name="STOXX Europe 600 Net Return (^STOXX)",
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
if eleva_raw is not None:
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
            "STOXX 600 NR (^STOXX)": fmt(s),
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
        st.markdown("**STOXX Europe 600 Net Return (^STOXX)**")
        for k, v in risk_stats(stoxx_index_plot).items():
            st.metric(k, v)

    # =====================
    # Graphique drawdown
    # =====================
    fig_dd = go.Figure()
    dd = lambda s: (s - s.cummax()) / s.cummax() * 100
    fig_dd.add_trace(go.Scatter(
        x=eleva_index.index, y=dd(eleva_index),
        name="ELEVA", fill="tozeroy", line=dict(color="#1f77b4", width=1.5)
    ))
    fig_dd.add_trace(go.Scatter(
        x=stoxx_index_plot.index, y=dd(stoxx_index_plot),
        name="STOXX 600 NR", fill="tozeroy", line=dict(color="#d62728", width=1.5, dash="dash")
    ))
    fig_dd.update_layout(
        height=350, template="plotly_white", title="Drawdown (%)",
        yaxis_title="Drawdown (%)", hovermode="x unified"
    )
    st.plotly_chart(fig_dd, use_container_width=True)

# =====================
# Notes méthodologiques
# =====================
st.subheader("ℹ️ Notes méthodologiques")
st.markdown("""
| Instrument | Ticker | Description |
|---|---|---|
| ELEVA European Selection I EUR Acc | `0P00015D09.F` | ISIN LU1111643042 — Lancement le 26/01/2015 |
| STOXX Europe 600 Net Return | `^STOXX` | Xtrackers ETF — Total Return Net en EUR |

- **Base 100** : les deux séries sont rebasées à 100 à la date de début sélectionnée dans la sidebar.
- Changer la date dans la sidebar **rebase automatiquement** les deux séries à 100 sur le nouveau point de départ.
- **Ratio de Sharpe** : calculé sans taux sans risque (approximation).
- **Drawdown** : par rapport au plus haut historique glissant sur la période sélectionnée.
""")

st.caption("Données : Yahoo Finance via yfinance — Mise à jour automatique toutes les heures")
