import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="ELEVA vs STOXX Europe 600", layout="wide")
st.title("📊 ELEVA European Selection I EUR Acc vs STOXX Europe 600 Net Return")

# =====================
# Sidebar — date de départ
# =====================
start = st.sidebar.date_input("Date de début", datetime(2020, 1, 1))

# =====================
# Tickers à tester dans l'ordre pour ELEVA
# =====================
ELEVA_TICKERS_CANDIDATES = [
    "0P00015D09.F",   # Frankfurt — le plus probable
    "0P00015D09.L",   # London
    "0P00015D09.PA",  # Paris
]
STOXX600_TICKER = "DX2X.DE"  # Xtrackers STOXX Europe 600 ETF — Total Return Net EUR

# =====================
# Chargement avec fallback automatique
# =====================
@st.cache_data(ttl=3600)
def find_eleva_ticker(candidates, start):
    for ticker in candidates:
        try:
            tmp = yf.download(ticker, start=start, auto_adjust=True, progress=False)
            if not tmp.empty and len(tmp) > 10:
                col = "Close" if "Close" in tmp.columns else tmp.columns[0]
                return ticker, tmp[col]
        except Exception:
            continue
    return None, None

@st.cache_data(ttl=3600)
def load_ticker(ticker, start):
    try:
        tmp = yf.download(ticker, start=start, auto_adjust=True, progress=False)
        if tmp.empty:
            return None
        col = "Close" if "Close" in tmp.columns else tmp.columns[0]
        return tmp[col]
    except Exception:
        return None

# =====================
# Chargement des données
# =====================
with st.spinner("Chargement des données ELEVA…"):
    eleva_ticker_found, eleva_raw = find_eleva_ticker(ELEVA_TICKERS_CANDIDATES, start)

with st.spinner("Chargement des données STOXX 600…"):
    stoxx_raw = load_ticker(STOXX600_TICKER, start)

# =====================
# Gestion des erreurs
# =====================
if eleva_raw is None:
    st.error(
        "⚠️ Impossible de charger les données ELEVA via Yahoo Finance. "
        "Ce fonds (LU1111643042) n'est pas disponible directement sur Yahoo Finance. "
        "**Solution** : uploadez un fichier CSV avec les VL historiques (colonne Date + VL)."
    )

    uploaded = st.file_uploader(
        "📂 Uploader un fichier CSV (colonnes : Date, VL)", type=["csv"]
    )
    if uploaded is not None:
        df_upload = pd.read_csv(uploaded, parse_dates=["Date"], index_col="Date")
        df_upload = df_upload.sort_index()
        eleva_raw = df_upload.iloc[:, 0]
        eleva_ticker_found = "CSV uploadé"
    else:
        st.info("En attendant, seul le benchmark STOXX 600 sera affiché.")

if stoxx_raw is None:
    st.error("⚠️ Impossible de charger les données STOXX 600 (DX2X.DE).")
    st.stop()

# =====================
# Calcul des indices (base 100)
# =====================
def build_index(series: pd.Series) -> pd.Series:
    series = series.dropna()
    ret = series.pct_change().fillna(0)
    return (1 + ret).cumprod() * 100

stoxx_index = build_index(stoxx_raw)

# =====================
# Graphique
# =====================
fig = go.Figure()

if eleva_raw is not None:
    eleva_index = build_index(eleva_raw)
    common = eleva_index.index.intersection(stoxx_index.index)
    eleva_index = eleva_index.loc[common]
    stoxx_index_plot = stoxx_index.loc[common]

    fig.add_trace(go.Scatter(
        x=eleva_index.index,
        y=eleva_index,
        name=f"ELEVA European Selection I EUR Acc ({eleva_ticker_found})",
        line=dict(width=3, color="#1f77b4")
    ))
else:
    stoxx_index_plot = stoxx_index

fig.add_trace(go.Scatter(
    x=stoxx_index_plot.index,
    y=stoxx_index_plot,
    name="STOXX Europe 600 Net Return (DX2X.DE)",
    line=dict(width=3, color="#d62728", dash="dash")
))

fig.update_layout(
    height=550,
    template="plotly_white",
    title="Performance cumulée (base 100)",
    yaxis_title="Valeur de l'indice (base 100)",
    xaxis_title="Date",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# =====================
# Performances
# =====================
if eleva_raw is not None:

    def perf(series, days):
        if len(series) < 2:
            return float("nan")
        cutoff = series.index[-1] - timedelta(days=days)
        if cutoff < series.index[0]:
            cutoff = series.index[0]
        start_val = series[series.index >= cutoff].iloc[0]
        return (series.iloc[-1] / start_val - 1) * 100

    def perf_ytd(series):
        year_start = pd.Timestamp(series.index[-1].year, 1, 1)
        sub = series[series.index >= year_start]
        if sub.empty:
            return float("nan")
        return (sub.iloc[-1] / sub.iloc[0] - 1) * 100

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
            e = (eleva_index.iloc[-1] / eleva_index.iloc[0] - 1) * 100
            s = (stoxx_index_plot.iloc[-1] / stoxx_index_plot.iloc[0] - 1) * 100
        elif days is None:
            e = perf_ytd(eleva_index)
            s = perf_ytd(stoxx_index_plot)
        else:
            e = perf(eleva_index, days)
            s = perf(stoxx_index_plot, days)
        def fmt(v):
            return f"{v:+.2f}%" if v == v else "N/A"  # v == v is False for NaN

        rows.append({
            "Période": label,
            "ELEVA I EUR Acc": fmt(e),
            "STOXX 600 NR (DX2X.DE)": fmt(s),
            "Surperformance ELEVA": fmt(e - s),
        })

    st.subheader("📈 Tableau des performances")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # =====================
    # Statistiques de risque
    # =====================
    st.subheader("📉 Statistiques de risque (annualisées)")

    def risk_stats(series):
        ret = series.pct_change().dropna()
        vol = ret.std() * (252 ** 0.5) * 100
        sharpe = (ret.mean() * 252) / (ret.std() * (252 ** 0.5)) if ret.std() > 0 else float("nan")
        roll_max = series.cummax()
        max_dd = ((series - roll_max) / roll_max).min() * 100
        return {"Volatilité annualisée": f"{vol:.2f}%",
                "Ratio de Sharpe (approx.)": f"{sharpe:.2f}",
                "Drawdown max": f"{max_dd:.2f}%"}

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**ELEVA European Selection I EUR Acc**")
        for k, v in risk_stats(eleva_index).items():
            st.metric(k, v)
    with col2:
        st.markdown("**STOXX Europe 600 Net Return (DX2X.DE)**")
        for k, v in risk_stats(stoxx_index_plot).items():
            st.metric(k, v)

    # =====================
    # Graphique drawdown
    # =====================
    def drawdown_series(s):
        return (s - s.cummax()) / s.cummax() * 100

    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(
        x=eleva_index.index, y=drawdown_series(eleva_index),
        name="ELEVA", fill="tozeroy", line=dict(color="#1f77b4", width=1.5)
    ))
    fig_dd.add_trace(go.Scatter(
        x=stoxx_index_plot.index, y=drawdown_series(stoxx_index_plot),
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
st.markdown(f"""
| Instrument | Ticker | Description |
|---|---|---|
| ELEVA European Selection I EUR Acc | `{eleva_ticker_found or 'non trouvé'}` | ISIN LU1111643042 — VL quotidiennes |
| STOXX Europe 600 Net Return | `DX2X.DE` | Xtrackers ETF — Total Return Net (dividendes réinvestis) en EUR |

- **Base 100** : les deux séries sont rebasées à la même date de départ.
- **Ratio de Sharpe** : calculé sans taux sans risque (approximation).
- **Drawdown** : calculé par rapport au plus haut historique glissant.
- Si le fonds ELEVA n'est pas disponible sur Yahoo Finance, un **upload CSV** est proposé (colonnes : `Date`, `VL`).
""")

st.caption("Données : Yahoo Finance via yfinance — Mise à jour automatique toutes les heures")
