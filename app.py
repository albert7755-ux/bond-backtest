import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io
from datetime import timedelta
import plotly.graph_objects as go

# ==========================================
# 頁面設定與樣式
# ==========================================
st.set_page_config(page_title="專業債券輔銷工具", layout="wide", page_icon="🏦")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
* { font-family: 'Noto Sans TC', sans-serif; }
.compare-table { width: 100%; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin: 10px 0; }
.compare-table th { background: #1a2744; color: white; padding: 12px; text-align: center; }
.compare-table td { padding: 10px; text-align: center; border-bottom: 1px solid #eee; }
.hl-gold { background: #fffbe6; font-weight: bold; border-left: 2px solid #c8a84b; border-right: 2px solid #c8a84b; }
.pos { color: #2e7d32; } .neg { color: #c62828; }
.bond-tag { display: inline-block; padding: 2px 10px; border-radius: 4px; color: white; font-weight: bold; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 工具函數
# ==========================================
@st.cache_data
def load_csv(file):
    df = pd.read_csv(file)
    # 相容 TradingView 不同格式的 time 欄位
    time_col = [c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()][0]
    if df[time_col].dtype == 'int64':
        df["date"] = pd.to_datetime(df[time_col], unit="s")
    else:
        df["date"] = pd.to_datetime(df[time_col])
    return df[["date", "close"]].sort_values("date").reset_index(drop=True)

@st.cache_data
def get_benchmark_data(start, end):
    """抓取美國 10 年期公債殖利率作為基準"""
    try:
        data = yf.download("^TNX", start=start, end=end)
        if data.empty: return None
        df = data['Close'].reset_index()
        df.columns = ['date', 'yield']
        # 將殖利率轉為價格指數走勢 (模擬公債價格)
        df['close'] = (1 - (df['yield'] / 100)).cumprod() * 100 
        return df
    except:
        return None

def calc_duration(coupon_rate, years_to_maturity, yield_to_maturity):
    """簡易麥考利存續期間計算"""
    if years_to_maturity <= 0: return 0
    y = yield_to_maturity / 100
    c = coupon_rate / 100
    m = years_to_maturity
    # 簡化公式：計算現金流加權平均時間
    num = (c/y)*(1-(1+y)**-m) + m*(1-c/y)*(1+y)**-m
    den = (c/y)*(1-(1+y)**-m) + (1+y)**-m
    return num / den

def calc_performance(df, coupon, days):
    end_date = df["date"].max()
    sub = df[df["date"] >= end_date - timedelta(days=days)]
    if len(sub) < 2: return None
    sp, ep = sub["close"].iloc[0], sub["close"].iloc[-1]
    price_ret = (ep - sp) / sp
    coupon_ret = (coupon / 100) * (days / 365)
    return {"price": price_ret, "coupon": coupon_ret, "total": price_ret + coupon_ret}

# ==========================================
# 側邊欄與輸入
# ==========================================
st.sidebar.header("⚙️ 設定參數")
n = st.sidebar.selectbox("比較債券數量", [2, 3, 4, 5, 6], index=0)
benchmark_yield = st.sidebar.number_input("當前市場基準利率 (%)", 3.5, 5.5, 4.2)

bonds = []
cols = st.columns(n)
for i in range(n):
    with cols[i]:
        color = ["#1565c0", "#c62828", "#2e7d32", "#6a1b9a", "#e65100", "#00838f"][i]
        st.markdown(f'<div class="bond-tag" style="background:{color}">債券 {chr(65+i)}</div>', unsafe_allow_html=True)
        file = st.file_uploader(f"CSV {i+1}", type="csv", key=f"f{i}")
        name = st.text_input("名稱", value=f"債券 {chr(65+i)}", key=f"n{i}")
        coupon = st.number_input("票息 (%)", 0.0, 15.0, 4.5, key=f"c{i}")
        years = st.number_input("剩餘年期", 1.0, 30.0, 5.0, key=f"y{i}")
        
        # 自動計算存續期間
        dur = calc_duration(coupon, years, benchmark_yield)
        st.caption(f"估計存續期間: {dur:.2f} 年")
        bonds.append({"file": file, "name": name, "coupon": coupon, "color": color, "duration": dur})

# ==========================================
# 主畫面邏輯
# ==========================================
loaded = [(b, load_csv(b["file"])) for b in bonds if b["file"]]

if loaded:
    start_dt = min(df['date'].min() for b, df in loaded)
    end_dt = max(df['date'].max() for b, df in loaded)
    
    # 抓取對標公債資料
    bench_df = get_benchmark_data(start_dt, end_dt)

    st.subheader("📈 總報酬比較走勢 (含息)")
    fig = go.Figure()
    
    # 畫出每一檔債券的含息曲線
    for b, df in loaded:
        daily_c = (b["coupon"] / 100) / 365
        prices = df["close"].values
        tri = [100.0]
        for j in range(1, len(prices)):
            r = (prices[j] - prices[j-1]) / prices[j-1]
            tri.append(tri[-1] * (1 + r + daily_c))
        
        fig.add_trace(go.Scatter(x=df["date"], y=tri, name=b["name"], line=dict(color=b["color"], width=3)))

    # 畫出公債基準線 (如有資料)
    if bench_df is not None:
        fig.add_trace(go.Scatter(x=bench_df['date'], y=bench_df['close']/bench_df['close'].iloc[0]*100, 
                                 name="美國 10Y 公債 (基準)", line=dict(color="#9e9e9e", dash='dash')))

    fig.update_layout(hovermode="x unified", height=500, yaxis_title="總報酬指數 (起始=100)")
    st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # 績效摘要表 (含導出功能)
    # ==========================================
    st.subheader("📊 績效摘要與利差分析")
    
    periods = [("1個月", 30), ("3個月", 90), ("1年", 365), ("3年", 1095)]
    summary_rows = []
    
    for label, days in periods:
        row = {"期間": label}
        for b, df in loaded:
            res = calc_performance(df, b["coupon"], days)
            row[f"{b['name']}_總報酬"] = f"{res['total']:.2%}" if res else "—"
        summary_rows.append(row)
    
    df_summary = pd.DataFrame(summary_rows)
    st.table(df_summary)

    # 匯出報告
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_summary.to_excel(writer, sheet_name='績效比較')
        # 這裡可以加入更多分頁內容
    
    st.download_button(
        label="📥 下載 Excel 分析報告",
        data=output.getvalue(),
        file_name="債券輔銷分析報告.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ==========================================
    # 輔銷話術自動生成
    # ==========================================
    st.info("💡 **輔銷觀察建議：**")
    for b in bonds:
        sens = b['duration'] * 0.01
        st.write(f"- **{b['name']}**: 存續期間約為 {b['duration']:.2f} 年。若市場利率下降 1%，價格預計反彈約 {sens:.2%}")

else:
    st.warning("請先上傳 TradingView 匯出的 CSV 檔案。")
