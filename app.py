import streamlit as st
import pandas as pd
from datetime import timedelta

st.set_page_config(page_title="債券績效比較", layout="wide", page_icon="📊")

# 每檔對應顏色
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
    padding: 2px 8px;
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

def fmt(val, bold=False):
    if val is None:
        return '<span class="neu">—</span>'
    css = "pos" if val > 0.0005 else ("neg" if val < -0.0005 else "neu")
    text = f"{val:+.2%}"
    return f'<span class="{css}"><b>{text}</b></span>' if bold else f'<span class="{css}">{text}</span>'


# ==========================================
# 主介面
# ==========================================
st.markdown("## 📊 債券績效比較工具")
st.markdown("上傳 TradingView 匯出的 CSV，自動計算並比較各期間總報酬")
st.markdown("---")

# 選檔數
n = st.radio("比較幾檔債券？", [2, 3, 4, 5, 6], horizontal=True)

st.markdown("---")

# 動態產生上傳欄位
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

# ==========================================
# 計算與顯示
# ==========================================
loaded = [(b, load_csv(b["file"])) for b in bonds if b["file"] is not None]

if loaded:
    periods = [("1個月",30),("3個月",90),("6個月",180),
               ("1年",365),("2年",730),("3年",1095),("5年",1825)]

    # 資料期間顯示
    info_cols = st.columns(len(loaded))
    for idx, (b, df) in enumerate(loaded):
        with info_cols[idx]:
            st.markdown(f'<span class="bond-tag" style="background:{b["color"]}">{b["label"]}</span> **{b["name"]}**', unsafe_allow_html=True)
            st.caption(f"{df['date'].min().strftime('%Y-%m-%d')} ～ {df['date'].max().strftime('%Y-%m-%d')}（{len(df)} 筆）")

    st.markdown("")

    # 計算所有期間數據
    all_data = []
    for b, df in loaded:
        period_data = {label: calc_period(df, b["coupon"], days) for label, days in periods}
        all_data.append((b, period_data))

    # ==========================================
    # 建立 HTML 表格
    # ==========================================

    # 表頭第一行：期間 + 每檔標題（含分隔）
    html = '<table class="compare-table"><thead>'
    html += '<tr><th class="period-col" rowspan="2">期間</th>'
    for idx, (b, _) in enumerate(all_data):
        if idx > 0:
            html += '<th class="divider" rowspan="2"></th>'
        short_name = b["name"][:14] + ("…" if len(b["name"]) > 14 else "")
        html += f'<th colspan="3" style="background:{b["color"]};color:white;">{b["label"]}. {short_name}</th>'
    html += "</tr>"

    # 表頭第二行：價格漲跌 / 票息收益 / 總報酬
    html += "<tr>"
    for idx, (b, _) in enumerate(all_data):
        if idx > 0:
            html += ""  # rowspan 已處理
        html += f'<th class="sub-header">價格漲跌</th>'
        html += f'<th class="sub-header">票息收益</th>'
        html += f'<th class="hl">總報酬 ★</th>'
    html += "</tr></thead><tbody>"

    # 表身
    for period_label, _ in periods:
        html += f'<tr><td class="period-col">{period_label}</td>'

        row_totals = []
        for idx, (b, period_data) in enumerate(all_data):
            if idx > 0:
                html += '<td class="divider"></td>'
            r = period_data.get(period_label)
            html += f'<td>{fmt(r["price"]) if r else "—"}</td>'
            html += f'<td>{fmt(r["coupon"]) if r else "—"}</td>'
            html += f'<td class="hl">{fmt(r["total"], bold=True) if r else "—"}</td>'
            row_totals.append(r["total"] if r else None)

        html += "</tr>"

    # 統計列（勝出次數）
    if len(all_data) > 1:
        # 計算每期勝者
        wins = [0] * len(all_data)
        for period_label, _ in periods:
            totals = []
            for idx, (b, period_data) in enumerate(all_data):
                r = period_data.get(period_label)
                totals.append(r["total"] if r else None)
            
            valid = [(i, t) for i, t in enumerate(totals) if t is not None]
            if valid:
                best_val = max(t for _, t in valid)
                for i, t in valid:
                    if t >= best_val - 0.0001:
                        wins[i] += 1

        html += '<tr style="background:#1a2744;">'
        html += '<td class="period-col" style="background:#1a2744;color:#ffd700;font-weight:700;">🏆 勝出</td>'
        for idx, (b, _) in enumerate(all_data):
            if idx > 0:
                html += '<td class="divider" style="background:#0d1b33;"></td>'
            html += f'<td colspan="2" style="text-align:center;color:#ccc;font-size:0.82rem;">{b["label"]}. {b["name"][:10]}</td>'
            html += f'<td style="text-align:center;color:#ffd700;font-weight:700;">{wins[idx]} 期間</td>'
        html += "</tr>"

        # 整體勝者
        max_wins = max(wins)
        winners = [all_data[i][0] for i, w in enumerate(wins) if w == max_wins]
        if len(winners) == 1:
            w = winners[0]
            overall_text = f'🏆 整體較佳：{w["label"]}. {w["name"]}'
            overall_color = w["color"]
        else:
            overall_text = "🤝 勢均力敵：" + "、".join(f'{w["label"]}.{w["name"][:6]}' for w in winners)
            overall_color = "#888"

        total_cols = len(all_data) * 3 + (len(all_data) - 1)
        html += f'<tr><td colspan="{total_cols + 1}" style="text-align:center;background:{overall_color}15;color:{overall_color};font-weight:700;padding:14px;font-size:0.95rem;">{overall_text}</td></tr>'

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

    # 圖例
    legend_html = '<div class="legend">'
    legend_html += '<div class="legend-item"><span class="dot" style="background:#c8a84b;"></span>★ 總報酬 = 價格漲跌 + 票息（依實際持有天數）</div>'
    legend_html += '<div class="legend-item"><span class="dot" style="background:#2e7d32;"></span>綠色 = 正報酬</div>'
    legend_html += '<div class="legend-item"><span class="dot" style="background:#c62828;"></span>紅色 = 負報酬</div>'
    legend_html += '</div>'
    st.markdown(legend_html, unsafe_allow_html=True)

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
st.caption("資料來源：TradingView ｜ 僅供參考，不構成投資建議")
