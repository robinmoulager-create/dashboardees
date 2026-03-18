import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="ELEVA vs STOXX Europe 600", layout="wide")
st.title("📊 ELEVA European Selection I EUR Acc vs STOXX Europe 600 Net Return")

# =====================
# Sidebar — date de départ
# =====================
start = st.sidebar.date_input("Date de début", datetime(2020, 1, 1))

# =====================
# Tickers
# =====================
ELEVA_TICKER = "0P00015D09"          # ELEVA European Selection I EUR Acc (LU1111643042)
STOXX600_TICKER = "DX2X.DE"          # Xtrackers STOXX Europe 600 UCITS ETF 1C — Total Return Net EUR

# =====================
# Chargement des données
# =====================
@st.cache_data(ttl=3600)
def load_prices(tickers: list, start) -> pd.DataFrame:
    prices = pd.DataFrame()
    failed = []
    for t in tickers:
        try:
            tmp = yf.download(t, start=start, auto_adjust=True)
            if tmp.empty:
                failed.append(t)
                continue
            col = "Close" if "Close" in tmp.columns else tmp.columns[0]
            prices[t] = tmp[col]
        except Exception as e:
            st.warning(f"Erreur pour {t} : {e}")
            failed.append(t)
    if failed:
        st.warning(f"Impossible de télécharger : {', '.join(failed)}")
    return prices

with st.spinner("Chargement des données…"):
    prices = load_prices([ELEVA_TICKER, STOXX600_TICKER], start)

if prices.empty or ELEVA_TICKER not in prices.columns or STOXX600_TICKER not in prices.columns:
    st.error("Les données n'ont pas pu être chargées. Vérifiez votre connexion ou les tickers.")
    st.stop()

# =====================
# Calcul des indices de performance (base 100)
# =====================
prices = prices.dropna()

def build_index(series: pd.Series) -> pd.Series:
    ret = series.pct_change().fillna(0)
    return (1 + ret).cumprod() * 100

eleva_index   = build_index(prices[ELEVA_TICKER])
stoxx_index   = build_index(prices[STOXX600_TICKER])

# Aligner sur un index commun
common = eleva_index.index.intersection(stoxx_index.index)
eleva_index = eleva_index.loc[common]
stoxx_index = stoxx_index.loc[common]

# =====================
# Graphique principal
# =====================
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=eleva_index.index,
    y=eleva_index,
    name="ELEVA European Selection I EUR Acc",
    line=dict(width=3, color="#1f77b4")
))

fig.add_trace(go.Scatter(
    x=stoxx_index.index,
    y=stoxx_index,
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
# Calcul des performances sur différentes périodes
# =====================
def perf(series: pd.Series, days: int) -> float:
    if len(series) < 2:
        return float("nan")
    cutoff = series.index[-1] - timedelta(days=days)
    if cutoff < series.index[0]:
        cutoff = series.index[0]
    start_val = series[series.index >= cutoff].iloc[0]
    return (series.iloc[-1] / start_val - 1) * 100

def perf_ytd(series: pd.Series) -> float:
    year_start = pd.Timestamp(series.index[-1].year, 1, 1)
    sub = series[series.index >= year_start]
    if sub.empty:
        return float("nan")
    return (sub.iloc[-1] / sub.iloc[0] - 1) * 100

periods = {
    "Hier (J-1)":       1,
    "1 semaine":        7,
    "1 mois":           30,
    "3 mois":           90,
    "6 mois":           180,
    "1 an":             365,
    "3 ans":            3 * 365,
    "Depuis le début":  None,
}

rows = []
for label, days in periods.items():
    if days is None:
        e = (eleva_index.iloc[-1] / eleva_index.iloc[0] - 1) * 100
        s = (stoxx_index.iloc[-1] / stoxx_index.iloc[0] - 1) * 100
    else:
        e = perf(eleva_index, days)
        s = perf(stoxx_index, days)
    rows.append({
        "Période": label,
        "ELEVA I EUR Acc": f"{e:+.2f}%",
        "STOXX 600 NR (DX2X.DE)": f"{s:+.2f}%",
        "Surperformance ELEVA": f"{e - s:+.2f}%",
    })

ytd_e = perf_ytd(eleva_index)
ytd_s = perf_ytd(stoxx_index)
rows.insert(4, {   # insertion après "3 mois"
    "Période": "YTD",
    "ELEVA I EUR Acc": f"{ytd_e:+.2f}%",
    "STOXX 600 NR (DX2X.DE)": f"{ytd_s:+.2f}%",
    "Surperformance ELEVA": f"{ytd_e - ytd_s:+.2f}%",
})

df_perf = pd.DataFrame(rows)

st.subheader("📈 Tableau des performances")
st.dataframe(df_perf, use_container_width=True, hide_index=True)

# =====================
# Métriques de risque
# =====================
st.subheader("📉 Statistiques de risque (annualisées)")

def risk_stats(series: pd.Series) -> dict:
    ret = series.pct_change().dropna()
    vol   = ret.std() * (252 ** 0.5) * 100
    sharpe = (ret.mean() * 252) / (ret.std() * (252 ** 0.5)) if ret.std() > 0 else float("nan")
    roll_max = series.cummax()
    drawdown = (series - roll_max) / roll_max
    max_dd = drawdown.min() * 100
    return {"Volatilité annualisée": f"{vol:.2f}%",
            "Ratio de Sharpe (approx.)": f"{sharpe:.2f}",
            "Drawdown max": f"{max_dd:.2f}%"}

stats_e = risk_stats(eleva_index)
stats_s = risk_stats(stoxx_index)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**ELEVA European Selection I EUR Acc**")
    for k, v in stats_e.items():
        st.metric(k, v)
with col2:
    st.markdown("**STOXX Europe 600 Net Return (DX2X.DE)**")
    for k, v in stats_s.items():
        st.metric(k, v)

# =====================
# Graphique drawdown
# =====================
def drawdown_series(series: pd.Series) -> pd.Series:
    roll_max = series.cummax()
    return (series - roll_max) / roll_max * 100

fig_dd = go.Figure()
fig_dd.add_trace(go.Scatter(
    x=eleva_index.index,
    y=drawdown_series(eleva_index),
    name="ELEVA",
    fill="tozeroy",
    line=dict(color="#1f77b4", width=1.5)
))
fig_dd.add_trace(go.Scatter(
    x=stoxx_index.index,
    y=drawdown_series(stoxx_index),
    name="STOXX 600 NR",
    fill="tozeroy",
    line=dict(color="#d62728", width=1.5, dash="dash")
))
fig_dd.update_layout(
    height=350,
    template="plotly_white",
    title="Drawdown (%)",
    yaxis_title="Drawdown (%)",
    hovermode="x unified"
)
st.plotly_chart(fig_dd, use_container_width=True)

# =====================
# Notes méthodologiques
# =====================
st.subheader("ℹ️ Notes méthodologiques")
st.markdown("""
| Instrument | Ticker Yahoo Finance | Description |
|---|---|---|
| ELEVA European Selection I EUR Acc | `0P00015D09` | Part I EUR Acc, ISIN LU1111643042, données VL quotidiennes |
| STOXX Europe 600 Net Return | `DX2X.DE` | Xtrackers STOXX Europe 600 UCITS ETF 1C — réplique le Total Return Net (dividendes réinvestis après retenue à la source) en EUR |

- **Base 100** : les deux séries sont rebasées au même point de départ pour une comparaison visuelle équitable.  
- **Ratio de Sharpe** : calculé sans taux sans risque (approx.).  
- **Drawdown** : calculé par rapport au plus haut historique glissant.  
- Mise à jour automatique toutes les heures (cache Streamlit).
""")

st.caption("Données : Yahoo Finance via yfinance — Mise à jour automatique toutes les heures")
