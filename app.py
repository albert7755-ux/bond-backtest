import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta

st.set_page_config(page_title="債券績效比較", layout="wide", page_icon="📊")

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
    font-size: 0.88rem;
}
.compare-table th {
    background: #1a2744;
    color: #fff;
    padding: 12px 16px;
    text-align: center;
    font-weight: 600;
    white-space: nowrap;
}
.compare-table th.period-col { text-align: left; }
.compare-table th.hl { background: #c8a84b; color: #1a2744; }
.compare-table th.divider { background: #0d1b33; width: 6px; padding: 0; }

.compare-table td {
    padding: 11px 16px;
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
    font-size: 0.95rem;
    border-left: 2px solid #c8a84b;
    border-right: 2px solid #c8a84b;
}
.compare-table td.divider { background: #e8ebf4; padding: 0; }
.compare-table td.winner {
    font-weight: 700;
    font-size: 0.92rem;
    min-width: 100px;
}
.compare-table tr:last-child td { border-bottom: none; }
.compare-table tr:hover td { background: #fafbff; }
.compare-table tr:hover td.period-col { background: #f0f2f8; }
.compare-table tr:hover td.hl { background: #fff8d6; }

.pos { color: #2e7d32; }
.neg { color: #c62828; }
.neu { color: #888; }
.win-a { color: #1565c0; }
.win-b { color: #c62828; }

.legend {
    display: flex; gap: 20px; margin-top: 10px;
    font-size: 0.78rem; color: #888;
}
.legend-item { display: flex; align-items: center; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display:inline-block; }
</style>
""", unsafe_allow_html=True)


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
    price_ret = (ep - sp) / sp
    coupon_ret = (coupon_rate / 100) * (actual_days / 365)
    return {"price": price_ret, "coupon": coupon_ret, "total": price_ret + coupon_ret}

def fmt(val, bold=False):
    if val is None:
        return '<span class="neu">—</span>'
    css = "pos" if val > 0.0005 else ("neg" if val < -0.0005 else "neu")
    text = f"{val:+.2%}"
    return f'<span class="{css}"><b>{text}</b></span>' if bold else f'<span class="{css}">{text}</span>'


# 上傳區
st.markdown("## 📊 債券績效比較工具")
st.markdown("上傳 TradingView 匯出的 CSV，自動計算各期間總報酬")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**📌 債券 A**")
    file_a = st.file_uploader("上傳 CSV", type="csv", key="fa")
    name_a = st.text_input("名稱", value="3M 4% 2048", key="na")
    coupon_a = st.number_input("票息率 (%)", value=4.00, step=0.01, key="ca")
with col2:
    st.markdown("**📌 債券 B**")
    file_b = st.file_uploader("上傳 CSV", type="csv", key="fb")
    name_b = st.text_input("名稱", value="Berkshire 4.2% 2048", key="nb")
    coupon_b = st.number_input("票息率 (%)", value=4.20, step=0.01, key="cb")

st.markdown("---")

if file_a or file_b:
    df_a = load_csv(file_a) if file_a else None
    df_b = load_csv(file_b) if file_b else None

    i1, i2 = st.columns(2)
    with i1:
        if df_a is not None:
            st.caption(f"✅ {name_a}：{df_a['date'].min().strftime('%Y-%m-%d')} ～ {df_a['date'].max().strftime('%Y-%m-%d')}（{len(df_a)} 筆）")
    with i2:
        if df_b is not None:
            st.caption(f"✅ {name_b}：{df_b['date'].min().strftime('%Y-%m-%d')} ～ {df_b['date'].max().strftime('%Y-%m-%d')}（{len(df_b)} 筆）")

    periods = [("1個月",30),("3個月",90),("6個月",180),
               ("1年",365),("2年",730),("3年",1095),("5年",1825)]
    data_a = {l: calc_period(df_a, coupon_a, d) for l,d in periods} if df_a is not None else {}
    data_b = {l: calc_period(df_b, coupon_b, d) for l,d in periods} if df_b is not None else {}
    has_both = df_a is not None and df_b is not None

    # 表頭
    na_short = name_a[:12] + ("…" if len(name_a) > 12 else "")
    nb_short = name_b[:12] + ("…" if len(name_b) > 12 else "")

    html = f"""<table class="compare-table"><thead><tr>
        <th class="period-col">期間</th>
        <th>A 價格漲跌<br><small style="font-weight:400;opacity:.8">{na_short}</small></th>
        <th>A 票息收益<br><small style="font-weight:400;opacity:.8">{na_short}</small></th>
        <th class="hl">A 總報酬 ★<br><small style="font-weight:600">{na_short}</small></th>
    """
    if has_both:
        html += f"""
        <th class="divider"></th>
        <th>B 價格漲跌<br><small style="font-weight:400;opacity:.8">{nb_short}</small></th>
        <th>B 票息收益<br><small style="font-weight:400;opacity:.8">{nb_short}</small></th>
        <th class="hl">B 總報酬 ★<br><small style="font-weight:600">{nb_short}</small></th>
        <th style="background:#1a2744;color:#ffd700;">勝出</th>
        """
    html += "</tr></thead><tbody>"

    wins_a, wins_b = 0, 0
    for label, _ in periods:
        ra = data_a.get(label)
        rb = data_b.get(label)

        winner_td = ""
        if has_both and ra and rb:
            if ra["total"] > rb["total"] + 0.0001:
                winner_td = '<td class="winner win-a">🏆 A</td>'
                wins_a += 1
            elif rb["total"] > ra["total"] + 0.0001:
                winner_td = '<td class="winner win-b">🏆 B</td>'
                wins_b += 1
            else:
                winner_td = '<td class="winner neu">平手</td>'
        elif has_both:
            winner_td = '<td class="winner neu">—</td>'

        html += f"""<tr>
            <td class="period-col">{label}</td>
            <td>{fmt(ra["price"]) if ra else "—"}</td>
            <td>{fmt(ra["coupon"]) if ra else "—"}</td>
            <td class="hl">{fmt(ra["total"], bold=True) if ra else "—"}</td>
        """
        if has_both:
            html += f"""
            <td class="divider"></td>
            <td>{fmt(rb["price"]) if rb else "—"}</td>
            <td>{fmt(rb["coupon"]) if rb else "—"}</td>
            <td class="hl">{fmt(rb["total"], bold=True) if rb else "—"}</td>
            {winner_td}
            """
        html += "</tr>"

    # 統計列
    if has_both:
        overall = "🏆 A 整體較佳" if wins_a > wins_b else ("🏆 B 整體較佳" if wins_b > wins_a else "勢均力敵")
        html += f"""<tr style="background:#1a2744;">
            <td class="period-col" style="background:#1a2744;color:#ffd700;font-weight:700;">統計</td>
            <td colspan="3" style="text-align:center;color:#90caf9;font-weight:700;">A 勝出 {wins_a} 個期間</td>
            <td class="divider" style="background:#0d1b33;"></td>
            <td colspan="3" style="text-align:center;color:#ef9a9a;font-weight:700;">B 勝出 {wins_b} 個期間</td>
            <td style="text-align:center;color:#ffd700;font-weight:700;">{overall}</td>
        </tr>"""

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

    st.markdown("""
    <div class="legend">
        <div class="legend-item"><span class="dot" style="background:#c8a84b;"></span>★ 總報酬 = 價格漲跌 + 票息（依實際持有天數）</div>
        <div class="legend-item"><span class="dot" style="background:#2e7d32;"></span>綠色 = 正報酬</div>
        <div class="legend-item"><span class="dot" style="background:#c62828;"></span>紅色 = 負報酬</div>
    </div>
    """, unsafe_allow_html=True)

else:
    st.info("👆 請上傳至少一檔債券的 CSV 開始分析")
    st.markdown("""
    **如何從 TradingView 取得 CSV？**
    1. 登入 TradingView（需 Plus 以上方案）
    2. 搜尋債券 ISIN（例如 `US084664CQ25`）
    3. 開啟圖表，時間軸往左捲到最左邊
    4. 右上角選單 → **匯出圖表資料...**
    5. 下載後上傳到這裡
    """)

st.markdown("---")
st.caption("資料來源：TradingView ｜ 僅供參考，不構成投資建議")
