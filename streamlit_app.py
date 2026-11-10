import streamlit as st
import requests
import yfinance as yf
import akshare as ak
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="金价实时看板", layout="wide")

# ========== 1. 数据采集部分 ==========
CMB_URL = "https://mbmodule-openapi.paas.cmbchina.com/product/v1/func/market-center"

def fetch_cmb_gold():
    try:
        resp = requests.post(CMB_URL, json=[{"prdType": "H", "prdCode": ""}], timeout=5, headers={"Content-Type": "application/json"})
        data = resp.json()
        item = data[0] if isinstance(data, list) else data
        return {"source": "cmb_live", "buy": float(item["zBuyPrc"]), "sell": float(item["zSelPrc"]), "timestamp": datetime.now().strftime("%H:%M:%S")}
    except Exception:
        return None

def fetch_sge_au9999():
    try:
        df = ak.spot_quotations_sge(symbol="Au99.99")
        latest = df.iloc[-1]
        return {"price": float(latest["现价"]), "time": str(latest["时间"])}
    except Exception:
        return None

def get_cmb_gold_with_fallback():
    live = fetch_cmb_gold()
    if live:
        return live
    sge = fetch_sge_au9999()
    if sge:
        mid = sge["price"]
        return {"source": "sge_estimated", "buy": round(mid + 2.5, 2), "sell": round(mid - 2.5, 2), "timestamp": sge["time"], "note": "招行接口不可用，基于 AU9999 估算"}
    return {"source": "unavailable", "buy": None, "sell": None, "timestamp": None}

def fetch_us_etf(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = info.get("last_price")
        prev_close = info.get("previous_close")
        if price is None:
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        return {"ticker": ticker, "price": round(float(price), 2) if price else None, "prev_close": round(float(prev_close), 2) if prev_close else None, "timestamp": datetime.now().strftime("%H:%M:%S")}
    except Exception:
        return {"ticker": ticker, "price": None, "prev_close": None, "timestamp": None}

# ========== 2. 页面缓存 ==========
@st.cache_data(ttl=30)
def load_cmb(): return get_cmb_gold_with_fallback()
@st.cache_data(ttl=30)
def load_etf(ticker): return fetch_us_etf(ticker)
@st.cache_data(ttl=30)
def load_sge(): return fetch_sge_au9999()

# ========== 3. 状态判断 ==========
def us_market_status():
    hour_min = datetime.now().hour * 60 + datetime.now().minute
    if hour_min >= 21 * 60 + 30 or hour_min < 4 * 60: return "交易中", "green"
    return "休市/盘前盘后", "gray"

def cmb_market_status():
    hour_min = datetime.now().hour * 60 + datetime.now().minute
    if hour_min >= 9 * 60 + 10 or hour_min < 2 * 60: return "交易中", "green"
    return "非交易时段", "gray"

# ========== 4. 页面展示 ==========
def render_price_card(title, subtitle, price_main, price_sub=None, change_pct=None, status=None, status_color="gray", timestamp=None, note=None, warning=None):
    with st.container(border=True):
        st.markdown(f"#### {title}")
        if subtitle: st.caption(subtitle)
        if status:
            color_map = {"green": "🟢", "gray": "⚪", "red": "🔴"}
            st.markdown(f"{color_map.get(status_color, '⚪')} **{status}**")
        if price_main is not None: st.metric(label="价格", value=price_main, delta=change_pct)
        else: st.warning("数据不可用")
        if price_sub: st.markdown(price_sub)
        if timestamp: st.caption(f"数据时间：{timestamp}")
        if note: st.caption(f"ℹ️ {note}")
        if warning: st.warning(warning, icon="⚠️")

st.title("🥇 金价实时看板")
st.caption("IAU · GLD · 招商银行积存金")

if st.button("🔄 立即刷新"):
    st.cache_data.clear()
    st.rerun()

st.divider()

cmb = load_cmb()
iau = load_etf("IAU")
gld = load_etf("GLD")
sge = load_sge()

col1, col2, col3 = st.columns(3)

with col1:
    cmb_status, cmb_color = cmb_market_status()
    if cmb.get("buy") is not None:
        mid = (cmb["buy"] + cmb["sell"]) / 2
        sub = f"客户买入价：**{cmb['buy']:.2f}** 元/克\n\n客户卖出价：**{cmb['sell']:.2f}** 元/克"
        warning = "招行接口不可用，当前为估算值" if cmb["source"] == "sge_estimated" else None
        render_price_card("招商银行积存金", "黄金账户 · 元/克", f"{mid:.2f} 元/克", price_sub=sub, status=cmb_status, status_color=cmb_color, timestamp=cmb.get("timestamp"), warning=warning)
    else:
        render_price_card("招商银行积存金", "黄金账户 · 元/克", None, status=cmb_status, status_color=cmb_color)

with col2:
    us_status, us_color = us_market_status()
    if iau["price"] is not None:
        chg = f"{(iau['price'] - iau['prev_close']) / iau['prev_close'] * 100:+.2f}%" if iau["prev_close"] else None
        render_price_card("IAU", "iShares 黄金信托 · 美元/股", f"${iau['price']:.2f}", change_pct=chg, status=us_status, status_color=us_color, timestamp=iau.get("timestamp"), warning=None if us_status == "交易中" else "当前非美股交易时段")
    else:
        render_price_card("IAU", "iShares 黄金信托 · 美元/股", None, status=us_status, status_color=us_color)

with col3:
    us_status, us_color = us_market_status()
    if gld["price"] is not None:
        chg = f"{(gld['price'] - gld['prev_close']) / gld['prev_close'] * 100:+.2f}%" if gld["prev_close"] else None
        render_price_card("GLD", "SPDR 黄金信托 · 美元/股", f"${gld['price']:.2f}", change_pct=chg, status=us_status, status_color=us_color, timestamp=gld.get("timestamp"), warning=None if us_status == "交易中" else "当前非美股交易时段")
    else:
        render_price_card("GLD", "SPDR 黄金信托 · 美元/股", None, status=us_status, status_color=us_color)

st.divider()
st.subheader("📌 参考基准：上海黄金交易所 AU9999")
if sge:
    st.metric(label="AU9999 最新价", value=f"{sge['price']:.2f} 元/克")
    st.caption(f"数据时间：{sge['time']}")
else:
    st.warning("AU9999 数据获取失败")