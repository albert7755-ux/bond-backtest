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
    """讀取 TradingView 匯出的 CSV"""
    df = pd.read_csv(file)
    # 轉換 Unix Timestamp → 日期
    df["date"] = pd.to_datetime(df["time"], unit="s")
    df = df[["date", "open", "high", "low", "close"]].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df

def calculate_period_return(df: pd.DataFrame, coupon_rate: float, days: int) -> dict:
    """計算某段期間的總報酬（價格報酬 + 票息收益）"""
    end_date = df["date"].max()
    start_date = end_date - timedelta(days=days)
    
    period_df = df[df["date"] >= start_date].copy()
    
    if len(period_df) < 2:
        return None
    
    start_price = period_df["close"].iloc[0]
    end_price = period_df["close"].iloc[-1]
    
    # 實際持有天數
    actual_days = (period_df["date"].iloc[-1] - period_df["date"].iloc[0]).days
    if actual_days == 0:
        return None
    
    # 價格報酬
    price_return = (end_price - start_price) / start_price
    
    # 票息收益（年化票息 × 持有天數/365）
    coupon_return = (coupon_rate / 100) * (actual_days / 365)
    
    # 總報酬
    total_return = price_return + coupon_return
    
    return {
        "起始日期": period_df["date"].iloc[0].strftime("%Y-%m-%d"),
        "結束日期": period_df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "起始價格": round(start_price, 3),
        "結束價格": round(end_price, 3),
        "價格漲跌": price_return,
        "票息收益": coupon_return,
        "總報酬": total_return,
    }

def get_all_periods(df: pd.DataFrame, coupon_rate: float) -> pd.DataFrame:
    """計算所有期間的績效"""
    periods = [
        ("1個月", 30),
        ("3個月", 90),
        ("6個月", 180),
        ("1年", 365),
        ("2年", 730),
        ("3年", 1095),
        ("5年", 1825),
    ]
    
    rows = []
    for label, days in periods:
        r = calculate_period_return(df, coupon_rate, days)
        if r:
            rows.append({
                "期間": label,
                "起始日期": r["起始日期"],
                "結束日期": r["結束日期"],
                "起始價格": r["起始價格"],
                "結束價格": r["結束價格"],
                "價格漲跌": r["價格漲跌"],
                "票息收益": r["票息收益"],
                "總報酬": r["總報酬"],
            })
    
    return pd.DataFrame(rows)

# ==========================================
# 上傳區
# ==========================================
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("📌 債券 A")
    file_a = st.file_uploader("上傳 CSV（從TradingView匯出）", type="csv", key="file_a")
    name_a = st.text_input("債券名稱", value="3M 4% 2048", key="name_a")
    coupon_a = st.number_input("票息率 (%)", value=4.00, step=0.01, key="coupon_a",
                                help="年化票息率，例如 4% 就填 4.00")

with col2:
    st.subheader("📌 債券 B")
    file_b = st.file_uploader("上傳 CSV（從TradingView匯出）", type="csv", key="file_b")
    name_b = st.text_input("債券名稱", value="Berkshire 4.2% 2048", key="name_b")
    coupon_b = st.number_input("票息率 (%)", value=4.20, step=0.01, key="coupon_b")

st.markdown("---")

# ==========================================
# 主邏輯
# ==========================================
if file_a or file_b:

    df_a = load_csv(file_a) if file_a else None
    df_b = load_csv(file_b) if file_b else None

    # 資料基本資訊
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        if df_a is not None:
            st.success(f"✅ {name_a}：{len(df_a)} 筆資料")
            st.caption(f"資料期間：{df_a['date'].min().strftime('%Y-%m-%d')} ～ {df_a['date'].max().strftime('%Y-%m-%d')}")
    with info_col2:
        if df_b is not None:
            st.success(f"✅ {name_b}：{len(df_b)} 筆資料")
            st.caption(f"資料期間：{df_b['date'].min().strftime('%Y-%m-%d')} ～ {df_b['date'].max().strftime('%Y-%m-%d')}")

    # ==========================================
    # 績效比較表
    # ==========================================
    st.subheader("🏆 各期間績效比較")

    perf_a = get_all_periods(df_a, coupon_a) if df_a is not None else pd.DataFrame()
    perf_b = get_all_periods(df_b, coupon_b) if df_b is not None else pd.DataFrame()

    if not perf_a.empty or not perf_b.empty:
        # 合併比較表
        periods_order = ["1個月", "3個月", "6個月", "1年", "2年", "3年", "5年"]
        rows = []
        for period in periods_order:
            row = {"期間": period}

            ra = perf_a[perf_a["期間"] == period].iloc[0] if not perf_a.empty and period in perf_a["期間"].values else None
            rb = perf_b[perf_b["期間"] == period].iloc[0] if not perf_b.empty and period in perf_b["期間"].values else None

            if ra is not None:
                row[f"A 價格漲跌"] = f"{ra['價格漲跌']:.2%}"
                row[f"A 票息收益"] = f"{ra['票息收益']:.2%}"
                row[f"A 總報酬"] = f"{ra['總報酬']:.2%}"
                row["_a_total"] = ra["總報酬"]
            else:
                row[f"A 價格漲跌"] = "資料不足"
                row[f"A 票息收益"] = "-"
                row[f"A 總報酬"] = "-"
                row["_a_total"] = None

            if rb is not None:
                row[f"B 價格漲跌"] = f"{rb['價格漲跌']:.2%}"
                row[f"B 票息收益"] = f"{rb['票息收益']:.2%}"
                row[f"B 總報酬"] = f"{rb['總報酬']:.2%}"
                row["_b_total"] = rb["總報酬"]
            else:
                row[f"B 價格漲跌"] = "資料不足"
                row[f"B 票息收益"] = "-"
                row[f"B 總報酬"] = "-"
                row["_b_total"] = None

            # 勝負判斷
            if row["_a_total"] is not None and row["_b_total"] is not None:
                if row["_a_total"] > row["_b_total"]:
                    row["勝出"] = f"🏆 A ({name_a})"
                elif row["_b_total"] > row["_a_total"]:
                    row["勝出"] = f"🏆 B ({name_b})"
                else:
                    row["勝出"] = "平手"
            else:
                row["勝出"] = "-"

            rows.append(row)

        df_compare = pd.DataFrame(rows)
        display_cols = ["期間", "A 價格漲跌", "A 票息收益", "A 總報酬", "B 價格漲跌", "B 票息收益", "B 總報酬", "勝出"]
        
        # 改欄位名稱顯示
        df_display = df_compare[display_cols].copy()
        df_display.columns = [
            "期間",
            f"A 價格漲跌\n({name_a})", f"A 票息收益\n({name_a})", f"A 總報酬\n({name_a})",
            f"B 價格漲跌\n({name_b})", f"B 票息收益\n({name_b})", f"B 總報酬\n({name_b})",
            "勝出"
        ]
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # ==========================================
    # 勝負統計
    # ==========================================
    if not perf_a.empty and not perf_b.empty:
        wins_a = sum(1 for r in rows if r["勝出"].startswith("🏆 A"))
        wins_b = sum(1 for r in rows if r["勝出"].startswith("🏆 B"))
        
        st.markdown("---")
        wc1, wc2, wc3 = st.columns(3)
        wc1.metric(f"🏆 {name_a} 勝出期間", f"{wins_a} 個")
        wc2.metric(f"🏆 {name_b} 勝出期間", f"{wins_b} 個")
        if wins_a > wins_b:
            wc3.metric("整體較佳", name_a, "勝出較多期間")
        elif wins_b > wins_a:
            wc3.metric("整體較佳", name_b, "勝出較多期間")
        else:
            wc3.metric("整體較佳", "平手", "")

    # ==========================================
    # 走勢圖
    # ==========================================
    st.markdown("---")
    st.subheader("📈 價格走勢圖")

    tab1, tab2 = st.tabs(["標準化走勢（起始=100）", "實際價格"])

    with tab1:
        fig = go.Figure()
        if df_a is not None:
            norm_a = df_a["close"] / df_a["close"].iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=df_a["date"], y=norm_a,
                name=name_a, line=dict(color="#1f77b4", width=2)
            ))
        if df_b is not None:
            norm_b = df_b["close"] / df_b["close"].iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=df_b["date"], y=norm_b,
                name=name_b, line=dict(color="#ff7f0e", width=2)
            ))
        fig.update_layout(
            yaxis_title="相對價格（起始=100）",
            xaxis_title="日期",
            hovermode="x unified",
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        if df_a is not None:
            fig2.add_trace(go.Scatter(
                x=df_a["date"], y=df_a["close"],
                name=name_a, line=dict(color="#1f77b4", width=2)
            ))
        if df_b is not None:
            fig2.add_trace(go.Scatter(
                x=df_b["date"], y=df_b["close"],
                name=name_b, line=dict(color="#ff7f0e", width=2)
            ))
        fig2.update_layout(
            yaxis_title="價格（面值100）",
            xaxis_title="日期",
            hovermode="x unified",
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ==========================================
    # 年度報酬表
    # ==========================================
    st.markdown("---")
    st.subheader("📅 年度報酬回顧")

    def calc_annual_returns(df: pd.DataFrame, coupon_rate: float) -> pd.DataFrame:
        df = df.copy()
        df["year"] = df["date"].dt.year
        years = sorted(df["year"].unique())
        rows = []
        for year in years:
            year_df = df[df["year"] == year]
            if len(year_df) < 2:
                continue
            start_p = year_df["close"].iloc[0]
            end_p = year_df["close"].iloc[-1]
            days = (year_df["date"].iloc[-1] - year_df["date"].iloc[0]).days
            price_ret = (end_p - start_p) / start_p
            coupon_ret = (coupon_rate / 100) * (days / 365)
            total_ret = price_ret + coupon_ret
            rows.append({
                "年度": str(year),
                "價格漲跌": price_ret,
                "票息收益": coupon_ret,
                "總報酬": total_ret,
            })
        return pd.DataFrame(rows)

    ann_col1, ann_col2 = st.columns(2)
    with ann_col1:
        if df_a is not None:
            st.markdown(f"**{name_a}**")
            ann_a = calc_annual_returns(df_a, coupon_a)
            if not ann_a.empty:
                st.dataframe(
                    ann_a.style.format({
                        "價格漲跌": "{:.2%}",
                        "票息收益": "{:.2%}",
                        "總報酬": "{:.2%}"
                    }).background_gradient(subset=["總報酬"], cmap="RdYlGn", vmin=-0.15, vmax=0.15),
                    use_container_width=True,
                    hide_index=True
                )
    with ann_col2:
        if df_b is not None:
            st.markdown(f"**{name_b}**")
            ann_b = calc_annual_returns(df_b, coupon_b)
            if not ann_b.empty:
                st.dataframe(
                    ann_b.style.format({
                        "價格漲跌": "{:.2%}",
                        "票息收益": "{:.2%}",
                        "總報酬": "{:.2%}"
                    }).background_gradient(subset=["總報酬"], cmap="RdYlGn", vmin=-0.15, vmax=0.15),
                    use_container_width=True,
                    hide_index=True
                )

else:
    st.info("👆 請上傳至少一檔債券的 CSV 檔案開始分析。")
    st.markdown("""
    **如何取得 CSV？**
    1. 登入 TradingView（需 Plus 以上方案）
    2. 搜尋債券 ISIN（例如 `US084664CQ25`）
    3. 開啟圖表後，把時間軸往左捲到最左邊
    4. 點右上角選單 → **匯出圖表資料...**
    5. 下載 CSV 後上傳到這裡
    """)

st.markdown("---")
st.caption("資料來源：TradingView | 總報酬 = 價格漲跌 + 票息收益（依實際持有天數計算）| 僅供參考，不構成投資建議")
