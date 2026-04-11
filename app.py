import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

# ==========================================
# 設定
# ==========================================
st.set_page_config(page_title="債券績效比較工具", layout="wide", page_icon="📊")

# 從 Streamlit Secrets 讀取 API Key
FINNHUB_KEY = st.secrets.get("FINNHUB_KEY", "")

# ==========================================
# 核心函數
# ==========================================

def get_bond_profile(isin: str) -> dict:
    """抓取債券基本資料"""
    url = f"https://finnhub.io/api/v1/bond/profile?isin={isin}&token={FINNHUB_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        st.error(f"無法抓取債券資料: {e}")
    return {}

def get_bond_price_history(isin: str, from_date: str, to_date: str) -> pd.DataFrame:
    """抓取債券歷史價格（用 bond/tick endpoint）"""
    # Finnhub bond tick: 每次只能抓一天，需要逐日抓
    # 改用 bond/price 端點
    url = f"https://finnhub.io/api/v1/bond/price?isin={isin}&token={FINNHUB_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data
    except Exception as e:
        st.error(f"抓取價格失敗: {e}")
    return {}

def get_bond_candles(isin: str, days_back: int) -> pd.DataFrame:
    """
    用 Finnhub bond/tick 抓歷史成交資料
    每次抓一天，累積成歷史序列
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days_back)
    
    all_data = []
    current = end_date
    
    progress = st.progress(0)
    total_days = min(days_back, 365)  # 免費版最多1年
    checked = 0
    
    # 每週抓一次（減少 API 呼叫次數）
    while current >= start_date:
        date_str = current.strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/bond/tick?isin={isin}&date={date_str}&limit=10&token={FINNHUB_KEY}"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data and "p" in data and len(data["p"]) > 0:
                    # 取當天最後一筆成交價
                    prices = data["p"]
                    all_data.append({
                        "date": date_str,
                        "price": prices[-1]
                    })
        except:
            pass
        
        current -= timedelta(days=7)  # 每次往前跳一週
        checked += 7
        progress.progress(min(checked / total_days, 1.0))
    
    progress.empty()
    
    if not all_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def calculate_performance(df: pd.DataFrame, coupon_rate: float, period_label: str, days: int) -> dict:
    """計算某段期間的總報酬"""
    if df.empty or len(df) < 2:
        return None
    
    end_date = df["date"].max()
    start_date = end_date - timedelta(days=days)
    
    period_df = df[df["date"] >= start_date]
    if len(period_df) < 2:
        return None
    
    start_price = period_df["price"].iloc[0]
    end_price = period_df["price"].iloc[-1]
    
    # 價格報酬（以面值100為基準）
    price_return = (end_price - start_price) / start_price
    
    # 票息收益（年化票息 × 持有天數/365）
    actual_days = (period_df["date"].iloc[-1] - period_df["date"].iloc[0]).days
    coupon_return = coupon_rate / 100 * actual_days / 365
    
    # 總報酬
    total_return = price_return + coupon_return
    
    return {
        "期間": period_label,
        "起始價格": round(start_price, 3),
        "結束價格": round(end_price, 3),
        "價格漲跌": f"{price_return:.2%}",
        "票息收益": f"{coupon_return:.2%}",
        "總報酬": f"{total_return:.2%}",
        "total_return_num": total_return
    }


# ==========================================
# 主介面
# ==========================================
st.title("📊 債券績效比較工具")
st.markdown("輸入兩檔債券的 ISIN，自動比較各期間績效表現。")

if not FINNHUB_KEY:
    st.error("⚠️ 尚未設定 Finnhub API Key！請在 Streamlit Secrets 加入 FINNHUB_KEY。")
    st.code("""
# .streamlit/secrets.toml 內容：
FINNHUB_KEY = "你的API Key"
    """)
    st.stop()

# 輸入區
col1, col2 = st.columns(2)
with col1:
    st.subheader("📌 債券 A")
    isin_a = st.text_input("ISIN", value="US88579YBD22", key="isin_a").upper().strip()
    coupon_a = st.number_input("票息率 (%)", value=4.00, step=0.01, key="coupon_a")

with col2:
    st.subheader("📌 債券 B")
    isin_b = st.text_input("ISIN", value="US084664CQ25", key="isin_b").upper().strip()
    coupon_b = st.number_input("票息率 (%)", value=4.20, step=0.01, key="coupon_b")

st.markdown("---")

# 執行按鈕
if st.button("🚀 開始比較", type="primary"):
    
    if not isin_a or not isin_b:
        st.error("請輸入兩檔債券的 ISIN！")
        st.stop()

    # ---- 抓取債券資料 ----
    with st.spinner("正在抓取債券 A 基本資料..."):
        profile_a = get_bond_profile(isin_a)
    
    with st.spinner("正在抓取債券 B 基本資料..."):
        profile_b = get_bond_profile(isin_b)

    # 顯示基本資料
    st.subheader("📋 債券基本資料")
    
    info_col1, info_col2 = st.columns(2)
    
    with info_col1:
        st.markdown(f"**債券 A：{isin_a}**")
        if profile_a:
            st.json(profile_a)
        else:
            st.warning("找不到債券 A 的基本資料，但仍會嘗試抓取價格。")
    
    with info_col2:
        st.markdown(f"**債券 B：{isin_b}**")
        if profile_b:
            st.json(profile_b)
        else:
            st.warning("找不到債券 B 的基本資料，但仍會嘗試抓取價格。")

    st.markdown("---")

    # ---- 抓取歷史價格（最多365天）----
    st.subheader("📈 抓取歷史價格中...")
    
    with st.spinner(f"正在抓取 {isin_a} 過去一年價格（每週一筆，約需30秒）..."):
        df_a = get_bond_candles(isin_a, days_back=365)
    
    with st.spinner(f"正在抓取 {isin_b} 過去一年價格（每週一筆，約需30秒）..."):
        df_b = get_bond_candles(isin_b, days_back=365)

    # 檢查有無資料
    has_data_a = not df_a.empty
    has_data_b = not df_b.empty

    if not has_data_a and not has_data_b:
        st.error("""
        ❌ 兩檔債券都抓不到歷史成交資料。
        
        可能原因：
        1. Finnhub 免費版不支援這兩檔債券的 tick 資料
        2. 這兩檔債券在 TRACE 的成交量太低
        3. API Key 額度用完
        
        建議：請確認你的 Finnhub API Key 是否正確，或嘗試其他 ISIN。
        """)
        st.stop()

    # ---- 顯示資料筆數 ----
    data_col1, data_col2 = st.columns(2)
    with data_col1:
        if has_data_a:
            st.success(f"✅ 債券 A：抓到 {len(df_a)} 筆歷史價格")
            st.dataframe(df_a.tail(10), use_container_width=True)
        else:
            st.error("❌ 債券 A：無歷史成交資料")
    
    with data_col2:
        if has_data_b:
            st.success(f"✅ 債券 B：抓到 {len(df_b)} 筆歷史價格")
            st.dataframe(df_b.tail(10), use_container_width=True)
        else:
            st.error("❌ 債券 B：無歷史成交資料")

    # ---- 績效比較 ----
    if has_data_a or has_data_b:
        st.markdown("---")
        st.subheader("🏆 各期間績效比較")

        periods = [
            ("1個月", 30),
            ("3個月", 90),
            ("6個月", 180),
            ("1年", 365),
        ]

        results_a = []
        results_b = []

        for label, days in periods:
            if has_data_a:
                r = calculate_performance(df_a, coupon_a, label, days)
                if r:
                    results_a.append(r)
            if has_data_b:
                r = calculate_performance(df_b, coupon_b, label, days)
                if r:
                    results_b.append(r)

        # 製作比較表
        if results_a or results_b:
            compare_rows = []
            for label, days in periods:
                row = {"期間": label}
                ra = next((r for r in results_a if r["期間"] == label), None)
                rb = next((r for r in results_b if r["期間"] == label), None)
                
                if ra:
                    row[f"A 總報酬"] = ra["總報酬"]
                    row[f"A 價格漲跌"] = ra["價格漲跌"]
                    row[f"A 票息"] = ra["票息收益"]
                if rb:
                    row[f"B 總報酬"] = rb["總報酬"]
                    row[f"B 價格漲跌"] = rb["價格漲跌"]
                    row[f"B 票息"] = rb["票息收益"]
                
                if ra and rb:
                    winner = "A 勝 🏆" if ra["total_return_num"] > rb["total_return_num"] else "B 勝 🏆"
                    row["勝負"] = winner
                
                compare_rows.append(row)
            
            df_compare = pd.DataFrame(compare_rows)
            st.dataframe(df_compare, use_container_width=True)

        # ---- 走勢圖 ----
        st.markdown("---")
        st.subheader("📉 價格走勢圖")
        
        fig = go.Figure()
        
        if has_data_a and not df_a.empty:
            # 標準化為起始100
            df_a_norm = df_a.copy()
            df_a_norm["normalized"] = df_a_norm["price"] / df_a_norm["price"].iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=df_a_norm["date"],
                y=df_a_norm["normalized"],
                mode="lines+markers",
                name=f"債券A ({isin_a[:12]})",
                line=dict(color="#1f77b4", width=2)
            ))
        
        if has_data_b and not df_b.empty:
            df_b_norm = df_b.copy()
            df_b_norm["normalized"] = df_b_norm["price"] / df_b_norm["price"].iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=df_b_norm["date"],
                y=df_b_norm["normalized"],
                mode="lines+markers",
                name=f"債券B ({isin_b[:12]})",
                line=dict(color="#ff7f0e", width=2)
            ))
        
        fig.update_layout(
            title="債券價格走勢（標準化，起始=100）",
            yaxis_title="相對價格",
            xaxis_title="日期",
            hovermode="x unified",
            height=450
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.caption("⚠️ 注意：Finnhub 免費版每分鐘限制60次請求，若資料不完整請稍後再試。")

st.markdown("---")
st.markdown("*資料來源：Finnhub.io（FINRA TRACE）｜僅供參考，不構成投資建議*")
