import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="債券績效比較", layout="wide", page_icon="📊")

COLORS = ["#1565c0", "#c62828", "#2e7d32", "#6a1b9a", "#e65100", "#00838f"]
LABELS = ["A", "B", "C", "D", "E", "F"]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
* { font-family: 'Noto Sans TC', sans-serif; }

.compare-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 16px rgba(0,0,0,0.08);
    font-size: 0.86rem;
}
.compare-table th {
    background: #1a2744;
    color: #fff;
    padding: 11px 14px;
    text-align: center;
    font-weight: 600;
    white-space: nowrap;
}
.compare-table th.period-col { text-align: left; min-width: 60px; }
.compare-table th.hl { background: #c8a84b; color: #1a2744; font-weight: 700; }
.compare-table th.sub-header { background: #2d3d6b; font-size: 0.78rem; font-weight: 400; }
.compare-table th.divider { background: #0d1b33; width: 5px; padding: 0; }

.compare-table td {
    padding: 10px 14px;
    text-align: center;
    border-bottom: 1px solid #f0f0f0;
    white-space: nowrap;
}
.compare-table td.period-col {
    text-align: left;
    font-weight: 700;
    color: #1a2744;
    background: #f8f9fc;
}
.compare-table td.hl {
    background: #fffbe6;
    font-weight: 700;
    font-size: 0.92rem;
    border-left: 2px solid #c8a84b;
    border-right: 2px solid #c8a84b;
}
.compare-table td.divider { background: #e8ebf4; padding: 0; width: 5px; }
.compare-table tr:last-child td { border-bottom: none; }
.compare-table tr:hover td { background: #fafbff; }
.compare-table tr:hover td.period-col { background: #f0f2f8; }
.compare-table tr:hover td.hl { background: #fff8d6; }

.pos { color: #2e7d32; }
.neg { color: #c62828; }
.neu { color: #888; }

.bond-tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    color: white;
    margin-bottom: 4px;
}
.legend {
    display: flex; gap: 20px; margin-top: 10px;
    font-size: 0.78rem; color: #888; flex-wrap: wrap;
}
.legend-item { display: flex; align-items: center; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display:inline-block; }

.annual-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
    border-radius: 8px;
    overflow: hidden;
}
.annual-table th {
    background: #1a2744;
    color: white;
    padding: 8px 12px;
    text-align: center;
}
.annual-table th.left { text-align: left; }
.annual-table td {
    padding: 7px 12px;
    text-align: center;
    border-bottom: 1px solid #f0f0f0;
}
.annual-table td.year-col { text-align: left; font-weight: 700; color: #1a2744; }
.annual-table tr:last-child td { border-bottom: none; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 工具函數
# ==========================================
def load_csv(file):
    df = pd.read_csv(file)
    df["date"] = pd.to_datetime(df["time"], unit="s")
    return df[["date", "close"]].sort_values("date").reset_index(drop=True)

def calc_period(df, coupon_rate, days):
    end_date = df["date"].max()
    sub = df[df["date"] >= end_date - timedelta(days=days)]
    if len(sub) < 5:
        return None
    sp, ep = sub["close"].iloc[0], sub["close"].iloc[-1]
    actual_days = (sub["date"].iloc[-1] - sub["date"].iloc[0]).days
    if actual_days == 0:
        return None
    price_ret = (ep - sp) / sp
    coupon_ret = (coupon_rate / 100) * (actual_days / 365)
    return {"price": price_ret, "coupon": coupon_ret, "total": price_ret + coupon_ret}

def calc_annual(df, coupon_rate):
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
        coupon_ret = (coupon_rate / 100) * (days / 365) if days > 0 else 0
        rows.append({"year": str(year), "price": price_ret,
                     "coupon": coupon_ret, "total": price_ret + coupon_ret})
    return rows

def fmt(val, bold=False):
    if val is None:
        return '<span class="neu">—</span>'
    css = "pos" if val > 0.0005 else ("neg" if val < -0.0005 else "neu")
    text = f"{val:+.2%}"
    return f'<span class="{css}"><b>{text}</b></span>' if bold else f'<span class="{css}">{text}</span>'

def color_cell(val):
    if val is None:
        return ""
    if val > 0.0005:
        return "color:#2e7d32;font-weight:600;"
    elif val < -0.0005:
        return "color:#c62828;font-weight:600;"
    return "color:#888;"


# ==========================================
# 介面
# ==========================================
st.markdown("## 📊 債券績效比較工具")
st.markdown("上傳 TradingView 匯出的 CSV，自動計算並比較各期間總報酬")
st.markdown("---")

n = st.radio("比較幾檔債券？", [2, 3, 4, 5, 6], horizontal=True)
st.markdown("---")

bonds = []
cols = st.columns(n)
for i in range(n):
    with cols[i]:
        color = COLORS[i]
        label = LABELS[i]
        st.markdown(f'<span class="bond-tag" style="background:{color}">債券 {label}</span>', unsafe_allow_html=True)
        file = st.file_uploader(f"上傳 CSV", type="csv", key=f"file_{i}")
        name = st.text_input("債券名稱", value="", placeholder="例：Apple 3% 2027", key=f"name_{i}")
        coupon = st.number_input("票息率 (%)", value=0.0, step=0.01, min_value=0.0, max_value=20.0, key=f"coupon_{i}")
        bonds.append({"file": file, "name": name or f"債券{label}", "coupon": coupon, "color": color, "label": label})

st.markdown("---")

loaded = [(b, load_csv(b["file"])) for b in bonds if b["file"] is not None]

if loaded:
    periods = [("1個月",30),("3個月",90),("6個月",180),
               ("1年",365),("2年",730),("3年",1095),("5年",1825)]

    # 資料期間
    info_cols = st.columns(len(loaded))
    for idx, (b, df) in enumerate(loaded):
        with info_cols[idx]:
            st.markdown(f'<span class="bond-tag" style="background:{b["color"]}">{b["label"]}</span> **{b["name"]}**', unsafe_allow_html=True)
            st.caption(f"{df['date'].min().strftime('%Y-%m-%d')} ～ {df['date'].max().strftime('%Y-%m-%d')}（{len(df)} 筆）")

    all_data = [(b, {label: calc_period(df, b["coupon"], days) for label, days in periods}) for b, df in loaded]

    # ==========================================
    # 一、各期間績效比較表
    # ==========================================
    st.subheader("🏆 各期間績效比較")

    html = '<table class="compare-table"><thead><tr>'
    html += '<th class="period-col" rowspan="2">期間</th>'
    for idx, (b, _) in enumerate(all_data):
        if idx > 0:
            html += '<th class="divider" rowspan="2"></th>'
        short = b["name"][:14] + ("…" if len(b["name"]) > 14 else "")
        html += f'<th colspan="3" style="background:{b["color"]};color:white;">{b["label"]}. {short}</th>'
    html += "</tr><tr>"
    for idx in range(len(all_data)):
        html += '<th class="sub-header">價格漲跌</th><th class="sub-header">票息收益</th><th class="hl">總報酬 ★</th>'
    html += "</tr></thead><tbody>"

    for period_label, _ in periods:
        html += f'<tr><td class="period-col">{period_label}</td>'
        for idx, (b, period_data) in enumerate(all_data):
            if idx > 0:
                html += '<td class="divider"></td>'
            r = period_data.get(period_label)
            html += f'<td>{fmt(r["price"]) if r else "—"}</td>'
            html += f'<td>{fmt(r["coupon"]) if r else "—"}</td>'
            html += f'<td class="hl">{fmt(r["total"], bold=True) if r else "—"}</td>'
        html += "</tr>"

    # 勝出統計
    wins = [0] * len(all_data)
    for period_label, _ in periods:
        totals = [all_data[i][1].get(period_label) for i in range(len(all_data))]
        valid = [(i, r["total"]) for i, r in enumerate(totals) if r]
        if valid:
            best = max(t for _, t in valid)
            for i, t in valid:
                if t >= best - 0.0001:
                    wins[i] += 1

    html += '<tr style="background:#1a2744;"><td class="period-col" style="background:#1a2744;color:#ffd700;font-weight:700;">🏆 勝出</td>'
    for idx, (b, _) in enumerate(all_data):
        if idx > 0:
            html += '<td class="divider" style="background:#0d1b33;"></td>'
        html += f'<td colspan="2" style="text-align:center;color:#ccc;font-size:0.8rem;">{b["label"]}. {b["name"][:8]}</td>'
        html += f'<td style="text-align:center;color:#ffd700;font-weight:700;">{wins[idx]} 期間</td>'
    html += "</tr>"

    max_wins = max(wins)
    winners = [all_data[i][0] for i, w in enumerate(wins) if w == max_wins]
    if len(winners) == 1:
        w = winners[0]
        overall = f'🏆 整體較佳：{w["label"]}. {w["name"]}'
        oc = w["color"]
    else:
        overall = "🤝 勢均力敵：" + "、".join(f'{w["label"]}.{w["name"][:6]}' for w in winners)
        oc = "#888"

    total_cols = len(all_data) * 3 + (len(all_data) - 1) + 1
    html += f'<tr><td colspan="{total_cols}" style="text-align:center;background:{oc}18;color:{oc};font-weight:700;padding:14px;font-size:0.95rem;">{overall}</td></tr>'
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

    st.markdown("""
    <div class="legend">
        <div class="legend-item"><span class="dot" style="background:#c8a84b;"></span>★ 總報酬 = 價格漲跌 + 票息（依實際持有天數）</div>
        <div class="legend-item"><span class="dot" style="background:#2e7d32;"></span>綠色 = 正報酬</div>
        <div class="legend-item"><span class="dot" style="background:#c62828;"></span>紅色 = 負報酬</div>
    </div>
    """, unsafe_allow_html=True)

    # ==========================================
    # 二、走勢圖
    # ==========================================
    st.markdown("---")
    st.subheader("📈 價格走勢圖")

    tab1, tab2, tab3 = st.tabs([
        "📊 標準化（不含息）",
        "📊 標準化（含息）",
        "💰 實際價格",
    ])

    def total_return_index(df, coupon_rate):
        """計算含息總報酬指數（起始=100）"""
        prices = df["close"].values
        daily_coupon = (coupon_rate / 100) / 365
        tri = [100.0]
        for i in range(1, len(prices)):
            price_ret = (prices[i] - prices[i-1]) / prices[i-1]
            tri.append(tri[-1] * (1 + price_ret + daily_coupon))
        return tri

    with tab1:
        st.info("📌 此圖為純價格走勢，**不含票息**。起始日設為100，僅反映債券市價的漲跌幅度。若要看含票息的真實報酬，請切換至「標準化（含息）」。")
        fig = go.Figure()
        for b, df in loaded:
            norm = df["close"] / df["close"].iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=df["date"], y=norm,
                name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)
            ))
        fig.update_layout(
            yaxis_title="相對價格（起始=100，不含息）",
            hovermode="x unified", height=430,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.info("📌 此圖為**含票息**的總報酬指數（Total Return Index）。起始=100，每日將票息（年票息率 ÷ 365）累積計入，完整反映持有人實際拿到的報酬，包含每天滴入的利息收益。")
        fig2 = go.Figure()
        for b, df in loaded:
            tri = total_return_index(df, b["coupon"])
            fig2.add_trace(go.Scatter(
                x=df["date"], y=tri,
                name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)
            ))
        fig2.update_layout(
            yaxis_title="總報酬指數（起始=100，含息）",
            hovermode="x unified", height=430,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.info("📌 此圖為 TradingView 的原始收盤價，以面值 100 為基準。**不含票息**，直接反映市場對該債券的定價。")
        fig3 = go.Figure()
        for b, df in loaded:
            fig3.add_trace(go.Scatter(
                x=df["date"], y=df["close"],
                name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)
            ))
        fig3.update_layout(
            yaxis_title="價格（面值100）",
            hovermode="x unified", height=430,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ==========================================
    # 三、年度報酬表
    # ==========================================
    st.markdown("---")
    st.subheader("📅 年度報酬回顧")

    # 收集所有年份
    all_annual = [(b, calc_annual(df, b["coupon"])) for b, df in loaded]
    all_years = sorted(set(r["year"] for _, rows in all_annual for r in rows), reverse=True)

    ann_html = '<table class="annual-table"><thead><tr><th class="left">年度</th>'
    for b, _ in all_annual:
        short = b["name"][:12] + ("…" if len(b["name"]) > 12 else "")
        ann_html += f'<th style="background:{b["color"]};">{b["label"]}. {short}<br><small style="font-weight:400;opacity:.85">價格漲跌</small></th>'
        ann_html += f'<th style="background:{b["color"]};">票息收益</th>'
        ann_html += f'<th style="background:{b["color"]};">總報酬 ★</th>'
    ann_html += "</tr></thead><tbody>"

    for year in all_years:
        ann_html += f'<tr><td class="year-col">{year}</td>'
        for b, rows in all_annual:
            row = next((r for r in rows if r["year"] == year), None)
            if row:
                ann_html += f'<td style="{color_cell(row["price"])}">{row["price"]:+.2%}</td>'
                ann_html += f'<td style="color:#2e7d32;">{row["coupon"]:+.2%}</td>'
                ann_html += f'<td style="{color_cell(row["total"])};font-weight:700;">{row["total"]:+.2%}</td>'
            else:
                ann_html += '<td colspan="3" style="color:#ccc;">無資料</td>'
        ann_html += "</tr>"

    ann_html += "</tbody></table>"
    st.markdown(ann_html, unsafe_allow_html=True)

else:
    st.info("👆 請至少上傳一檔債券的 CSV 開始分析")
    st.markdown("""
    **如何從 TradingView 取得 CSV？**
    1. 登入 TradingView（需 Plus 以上方案）
    2. 搜尋債券 ISIN（例如 `US084664CQ25`）
    3. 開啟圖表，時間軸往左捲到最左邊（取得最長歷史）
    4. 右上角選單 → **匯出圖表資料...**
    5. 下載後上傳到這裡
    """)

st.markdown("---")
st.caption("資料來源：TradingView ｜ 總報酬 = 價格漲跌 + 票息（依實際持有天數）｜ 僅供參考，不構成投資建議")
