import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="債券績效比較工具", layout="wide", page_icon="📊")

st.title("📊 債券績效比較工具")
st.markdown("上傳從 TradingView 匯出的兩檔債券 CSV，自動計算並比較各期間績效。")

# ==========================================
# 工具函數
# ==========================================

def load_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    df["date"] = pd.to_datetime(df["time"], unit="s")
    df = df[["date", "open", "high", "low", "close"]].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df

def calculate_mdd(prices: pd.Series) -> float:
    roll_max = prices.cummax()
    drawdown = (prices - roll_max) / roll_max
    return drawdown.min()

def calculate_cagr(start_price, end_price, coupon_rate, days) -> float:
    years = days / 365
    if years <= 0:
        return 0
    coupon_total = (coupon_rate / 100) * years
    total_return = (end_price - start_price) / start_price + coupon_total
    if total_return <= -1:
        return -1
    return (1 + total_return) ** (1 / years) - 1

def calculate_volatility(prices: pd.Series) -> float:
    return prices.pct_change().dropna().std() * np.sqrt(252)

def calculate_sharpe(prices: pd.Series, coupon_rate: float, risk_free: float) -> float:
    daily_ret = prices.pct_change().dropna()
    daily_coupon = (coupon_rate / 100) / 252
    total_daily = daily_ret + daily_coupon
    ann_ret = total_daily.mean() * 252
    ann_vol = total_daily.std() * np.sqrt(252)
    if ann_vol == 0:
        return 0
    return (ann_ret - risk_free) / ann_vol

def calculate_max_loss_days(prices: pd.Series) -> int:
    daily_ret = prices.pct_change().dropna()
    max_loss, current = 0, 0
    for r in daily_ret:
        if r < 0:
            current += 1
            max_loss = max(max_loss, current)
        else:
            current = 0
    return max_loss

def calculate_period_metrics(df, coupon_rate, days, rf_rate) -> dict:
    end_date = df["date"].max()
    start_date = end_date - timedelta(days=days)
    period_df = df[df["date"] >= start_date].copy()
    if len(period_df) < 10:
        return None
    prices = period_df["close"]
    sp, ep = prices.iloc[0], prices.iloc[-1]
    actual_days = (period_df["date"].iloc[-1] - period_df["date"].iloc[0]).days
    if actual_days == 0:
        return None
    price_ret = (ep - sp) / sp
    coupon_ret = (coupon_rate / 100) * (actual_days / 365)
    return {
        "起始日期": period_df["date"].iloc[0].strftime("%Y-%m-%d"),
        "結束日期": period_df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "起始價格": round(sp, 3),
        "結束價格": round(ep, 3),
        "價格漲跌": price_ret,
        "票息收益": coupon_ret,
        "總報酬": price_ret + coupon_ret,
        "年化報酬CAGR": calculate_cagr(sp, ep, coupon_rate, actual_days),
        "最大回撤MDD": calculate_mdd(prices),
        "年化波動率": calculate_volatility(prices),
        "夏普比率": calculate_sharpe(prices, coupon_rate, rf_rate),
        "最長虧損天數": calculate_max_loss_days(prices),
    }

def get_all_periods(df, coupon_rate, rf_rate) -> dict:
    periods = [("1個月",30),("3個月",90),("6個月",180),
               ("1年",365),("2年",730),("3年",1095),("5年",1825)]
    return {label: r for label, days in periods
            if (r := calculate_period_metrics(df, coupon_rate, days, rf_rate))}

def full_period_metrics(df, coupon_rate, rf_rate) -> dict:
    prices = df["close"]
    days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    return {
        "年化報酬CAGR": calculate_cagr(prices.iloc[0], prices.iloc[-1], coupon_rate, days),
        "最大回撤MDD": calculate_mdd(prices),
        "年化波動率": calculate_volatility(prices),
        "夏普比率": calculate_sharpe(prices, coupon_rate, rf_rate),
        "最長虧損天數": calculate_max_loss_days(prices),
    }

def calc_annual_returns(df, coupon_rate) -> pd.DataFrame:
    df = df.copy()
    df["year"] = df["date"].dt.year
    rows = []
    for year in sorted(df["year"].unique()):
        ydf = df[df["year"] == year]
        if len(ydf) < 2:
            continue
        sp, ep = ydf["close"].iloc[0], ydf["close"].iloc[-1]
        days = (ydf["date"].iloc[-1] - ydf["date"].iloc[0]).days
        price_ret = (ep - sp) / sp
        coupon_ret = (coupon_rate / 100) * (days / 365)
        rows.append({
            "年度": str(year),
            "價格漲跌": price_ret,
            "票息收益": coupon_ret,
            "總報酬": price_ret + coupon_ret,
            "MDD": calculate_mdd(ydf["close"]),
            "波動率": calculate_volatility(ydf["close"]),
        })
    return pd.DataFrame(rows)

# ==========================================
# 側邊欄
# ==========================================
st.sidebar.header("⚙️ 設定")
rf_rate = st.sidebar.number_input("無風險利率 (%) — 夏普比率用", value=4.0, step=0.1) / 100
st.sidebar.caption("建議填當前美國3個月國庫券殖利率")

# ==========================================
# 上傳區
# ==========================================
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("📌 債券 A")
    file_a = st.file_uploader("上傳 CSV（TradingView匯出）", type="csv", key="file_a")
    name_a = st.text_input("債券名稱", value="3M 4% 2048", key="name_a")
    coupon_a = st.number_input("票息率 (%)", value=4.00, step=0.01, key="coupon_a")
with col2:
    st.subheader("📌 債券 B")
    file_b = st.file_uploader("上傳 CSV（TradingView匯出）", type="csv", key="file_b")
    name_b = st.text_input("債券名稱", value="Berkshire 4.2% 2048", key="name_b")
    coupon_b = st.number_input("票息率 (%)", value=4.20, step=0.01, key="coupon_b")

st.markdown("---")

# ==========================================
# 主邏輯
# ==========================================
if file_a or file_b:
    df_a = load_csv(file_a) if file_a else None
    df_b = load_csv(file_b) if file_b else None

    info_col1, info_col2 = st.columns(2)
    with info_col1:
        if df_a is not None:
            st.success(f"✅ {name_a}：{len(df_a)} 筆資料")
            st.caption(f"{df_a['date'].min().strftime('%Y-%m-%d')} ～ {df_a['date'].max().strftime('%Y-%m-%d')}")
    with info_col2:
        if df_b is not None:
            st.success(f"✅ {name_b}：{len(df_b)} 筆資料")
            st.caption(f"{df_b['date'].min().strftime('%Y-%m-%d')} ～ {df_b['date'].max().strftime('%Y-%m-%d')}")

    perf_a = get_all_periods(df_a, coupon_a, rf_rate) if df_a is not None else {}
    perf_b = get_all_periods(df_b, coupon_b, rf_rate) if df_b is not None else {}

    # ==========================================
    # 全期間核心指標卡
    # ==========================================
    st.subheader("🎯 全期間核心指標")
    metrics_labels = ["年化報酬CAGR", "最大回撤MDD", "年化波動率", "夏普比率", "最長虧損天數"]
    metric_formats = ["{:.2%}", "{:.2%}", "{:.2%}", "{:.2f}", "{:.0f} 天"]
    lower_is_better = {"最大回撤MDD", "年化波動率", "最長虧損天數"}

    metric_cols = st.columns(5)
    if df_a is not None and df_b is not None:
        full_a = full_period_metrics(df_a, coupon_a, rf_rate)
        full_b = full_period_metrics(df_b, coupon_b, rf_rate)
        for i, (label, fmt) in enumerate(zip(metrics_labels, metric_formats)):
            va, vb = full_a[label], full_b[label]
            with metric_cols[i]:
                st.markdown(f"**{label}**")
                if label in lower_is_better:
                    a_better = va >= vb
                else:
                    a_better = va <= vb
                ca = "🔴" if a_better else "🟢"
                cb = "🟢" if a_better else "🔴"
                st.markdown(f"{ca} **A** {fmt.format(va)}")
                st.markdown(f"{cb} **B** {fmt.format(vb)}")
    elif df_a is not None:
        full_a = full_period_metrics(df_a, coupon_a, rf_rate)
        for i, (label, fmt) in enumerate(zip(metrics_labels, metric_formats)):
            metric_cols[i].metric(label, fmt.format(full_a[label]))
    elif df_b is not None:
        full_b = full_period_metrics(df_b, coupon_b, rf_rate)
        for i, (label, fmt) in enumerate(zip(metrics_labels, metric_formats)):
            metric_cols[i].metric(label, fmt.format(full_b[label]))

    # ==========================================
    # 各期間績效比較
    # ==========================================
    st.markdown("---")
    st.subheader("🏆 各期間績效比較")

    period_order = ["1個月","3個月","6個月","1年","2年","3年","5年"]
    metrics_to_show = [
        ("總報酬", "{:.2%}", False),
        ("年化報酬CAGR", "{:.2%}", False),
        ("最大回撤MDD", "{:.2%}", True),
        ("年化波動率", "{:.2%}", True),
        ("夏普比率", "{:.2f}", False),
    ]

    for metric_name, fmt, lower_better in metrics_to_show:
        with st.expander(f"📊 {metric_name}", expanded=(metric_name == "總報酬")):
            rows = []
            wins_a, wins_b = 0, 0
            for period in period_order:
                row = {"期間": period}
                ra = perf_a.get(period)
                rb = perf_b.get(period)
                val_a = ra[metric_name] if ra else None
                val_b = rb[metric_name] if rb else None
                row[f"A ({name_a})"] = fmt.format(val_a) if val_a is not None else "資料不足"
                row[f"B ({name_b})"] = fmt.format(val_b) if val_b is not None else "資料不足"
                if val_a is not None and val_b is not None:
                    if lower_better:
                        a_wins = val_a > val_b
                    else:
                        a_wins = val_a < val_b
                    row["勝出"] = "🏆 B" if a_wins else "🏆 A"
                    if a_wins:
                        wins_b += 1
                    else:
                        wins_a += 1
                else:
                    row["勝出"] = "-"
                rows.append(row)
            df_table = pd.DataFrame(rows)
            st.dataframe(df_table, use_container_width=True, hide_index=True)
            if df_a is not None and df_b is not None:
                st.caption(f"A 勝出：{wins_a} 期間 ｜ B 勝出：{wins_b} 期間")

    # ==========================================
    # 走勢圖
    # ==========================================
    st.markdown("---")
    st.subheader("📈 走勢圖")
    tab1, tab2, tab3 = st.tabs(["標準化走勢（起始=100）", "實際價格", "回撤圖"])

    with tab1:
        fig = go.Figure()
        if df_a is not None:
            fig.add_trace(go.Scatter(x=df_a["date"], y=df_a["close"]/df_a["close"].iloc[0]*100,
                name=name_a, line=dict(color="#1f77b4", width=2)))
        if df_b is not None:
            fig.add_trace(go.Scatter(x=df_b["date"], y=df_b["close"]/df_b["close"].iloc[0]*100,
                name=name_b, line=dict(color="#ff7f0e", width=2)))
        fig.update_layout(yaxis_title="相對價格（起始=100）", hovermode="x unified", height=420,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        if df_a is not None:
            fig2.add_trace(go.Scatter(x=df_a["date"], y=df_a["close"],
                name=name_a, line=dict(color="#1f77b4", width=2)))
        if df_b is not None:
            fig2.add_trace(go.Scatter(x=df_b["date"], y=df_b["close"],
                name=name_b, line=dict(color="#ff7f0e", width=2)))
        fig2.update_layout(yaxis_title="價格（面值100）", hovermode="x unified", height=420,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        fig3 = go.Figure()
        if df_a is not None:
            p = df_a["close"]
            dd = (p - p.cummax()) / p.cummax() * 100
            fig3.add_trace(go.Scatter(x=df_a["date"], y=dd, name=name_a,
                fill="tozeroy", line=dict(color="#1f77b4", width=1),
                fillcolor="rgba(31,119,180,0.2)"))
        if df_b is not None:
            p = df_b["close"]
            dd = (p - p.cummax()) / p.cummax() * 100
            fig3.add_trace(go.Scatter(x=df_b["date"], y=dd, name=name_b,
                fill="tozeroy", line=dict(color="#ff7f0e", width=1),
                fillcolor="rgba(255,127,14,0.2)"))
        fig3.update_layout(yaxis_title="回撤幅度 (%)", hovermode="x unified", height=420,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig3, use_container_width=True)

    # ==========================================
    # 年度報酬表
    # ==========================================
    st.markdown("---")
    st.subheader("📅 年度報酬回顧")
    ann_col1, ann_col2 = st.columns(2)
    with ann_col1:
        if df_a is not None:
            st.markdown(f"**{name_a}**")
            ann_a = calc_annual_returns(df_a, coupon_a)
            if not ann_a.empty:
                st.dataframe(ann_a.style.format({
                    "價格漲跌":"{:.2%}","票息收益":"{:.2%}",
                    "總報酬":"{:.2%}","MDD":"{:.2%}","波動率":"{:.2%}"
                }), use_container_width=True, hide_index=True)
    with ann_col2:
        if df_b is not None:
            st.markdown(f"**{name_b}**")
            ann_b = calc_annual_returns(df_b, coupon_b)
            if not ann_b.empty:
                st.dataframe(ann_b.style.format({
                    "價格漲跌":"{:.2%}","票息收益":"{:.2%}",
                    "總報酬":"{:.2%}","MDD":"{:.2%}","波動率":"{:.2%}"
                }), use_container_width=True, hide_index=True)

else:
    st.info("👆 請上傳至少一檔債券的 CSV 檔案開始分析。")
    st.markdown("""
    **如何從 TradingView 取得 CSV？**
    1. 登入 TradingView（需 Plus 以上方案）
    2. 搜尋債券 ISIN（例如 `US084664CQ25`）
    3. 開啟圖表後，把時間軸往左捲到最左邊（取得最長歷史）
    4. 點右上角選單 → **匯出圖表資料...**
    5. 下載 CSV 後上傳到這裡
    """)

st.markdown("---")
st.caption("資料來源：TradingView ｜ 總報酬 = 價格漲跌 + 票息（依實際持有天數）｜ 夏普比率無風險利率可在左側調整 ｜ 僅供參考，不構成投資建議")
