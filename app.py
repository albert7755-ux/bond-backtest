import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json

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
</style>
""", unsafe_allow_html=True)


# ==========================================
# Google Drive 連線
# ==========================================
@st.cache_resource
def get_gspread_client():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def list_sheets_in_folder(folder_id):
    """列出資料夾中所有試算表"""
    client = get_gspread_client()
    drive = client.auth.authorized_session if hasattr(client, 'auth') else None
    
    # 用 gspread 列出資料夾中的檔案
    import requests
    from google.oauth2.service_account import Credentials
    
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    # 手動呼叫 Drive API
    from google.auth.transport.requests import Request
    creds.refresh(Request())
    
    headers = {"Authorization": f"Bearer {creds.token}"}
    url = f"https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        "fields": "files(id, name)",
    }
    resp = requests.get(url, headers=headers, params=params)
    files = resp.json().get("files", [])
    return files  # [{"id": "...", "name": "..."}]

@st.cache_data(ttl=300)
def read_sheet(sheet_id):
    """讀取試算表資料"""
    client = get_gspread_client()
    sh = client.open_by_key(sheet_id)
    ws = sh.get_worksheet(0)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["time"], unit="s")
    df = df[["date", "close"]].sort_values("date").reset_index(drop=True)
    return df

def parse_filename(name):
    """從檔名解析 ISIN"""
    import re
    isin_match = re.search(r'(US[A-Z0-9]{10})', name)
    isin = isin_match.group(1) if isin_match else ""
    return isin

@st.cache_data(ttl=86400)
def lookup_bond_info(isin):
    """用 ISIN 上網查債券基本資料（發行機構、票息、到期年）"""
    import requests, re
    try:
        url = f"https://bondblox.com/bond-market/{isin}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        text = resp.text

        # 抓票息
        coupon_match = re.search(r'"coupon"[:\s]+"?([\d.]+)%?"?', text)
        if not coupon_match:
            coupon_match = re.search(r'(\d+\.?\d+)%\s*\d{4}', text)
        coupon = float(coupon_match.group(1)) if coupon_match else 0.0

        # 抓到期年
        maturity_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
        if maturity_match:
            maturity = maturity_match.group(1).split("/")[-1]
        else:
            maturity_match = re.search(r'(20\d{2})', text)
            maturity = maturity_match.group(1) if maturity_match else ""

        # 抓發行機構（從 title）
        title_match = re.search(r'<title>(.*?)</title>', text)
        issuer = ""
        if title_match:
            title = title_match.group(1)
            issuer_match = re.match(r'^([\w\s\-\.]+?)\s+\d', title)
            if issuer_match:
                issuer = issuer_match.group(1).strip()

        if coupon > 0 and maturity:
            return {"issuer": issuer, "coupon": coupon, "maturity": maturity}
    except:
        pass

    # 備用：用 cbonds 抓
    try:
        url2 = f"https://cbonds.com/bonds/?search={isin}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp2 = requests.get(url2, headers=headers, timeout=8)
        text2 = resp2.text
        coupon_match = re.search(r'(\d+\.?\d+)%', text2)
        coupon = float(coupon_match.group(1)) if coupon_match else 0.0
        maturity_match = re.search(r'(20\d{2})', text2)
        maturity = maturity_match.group(1) if maturity_match else ""
        return {"issuer": isin, "coupon": coupon, "maturity": maturity}
    except:
        pass

    return {"issuer": isin, "coupon": 0.0, "maturity": ""}


# ==========================================
# 工具函數
# ==========================================
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

def total_return_index(df, coupon_rate):
    prices = df["close"].values
    daily_coupon = (coupon_rate / 100) / 365
    tri = [100.0]
    for i in range(1, len(prices)):
        price_ret = (prices[i] - prices[i-1]) / prices[i-1]
        tri.append(tri[-1] * (1 + price_ret + daily_coupon))
    return tri

def fmt(val, bold=False):
    if val is None:
        return '<span class="neu">—</span>'
    css = "pos" if val > 0.0005 else ("neg" if val < -0.0005 else "neu")
    text = f"{val:+.2%}"
    return f'<span class="{css}"><b>{text}</b></span>' if bold else f'<span class="{css}">{text}</span>'

def color_cell(val):
    if val is None: return ""
    if val > 0.0005: return "color:#2e7d32;font-weight:600;"
    elif val < -0.0005: return "color:#c62828;font-weight:600;"
    return "color:#888;"


# ==========================================
# 主介面
# ==========================================
st.markdown("## 📊 債券績效比較工具")
st.markdown("從 Google Drive `bond-data` 資料夾自動讀取，選擇債券後立即比較績效")
st.markdown("---")

# 讀取資料夾中的試算表清單
folder_id = st.secrets.get("FOLDER_ID", "")

try:
    with st.spinner("正在讀取 bond-data 資料夾..."):
        files = list_sheets_in_folder(folder_id)
    
    if not files:
        st.warning("⚠️ bond-data 資料夾中沒有試算表，請先上傳 CSV 並確認已轉換為 Google 試算表格式。")
        st.stop()
    
    # 建立選單選項
    file_options = {f["name"]: f["id"] for f in files}
    file_names = list(file_options.keys())

except Exception as e:
    st.error(f"❌ 無法連接 Google Drive：{e}")
    st.stop()

# 選檔數
n = st.radio("比較幾檔債券？", [2, 3, 4, 5, 6], horizontal=True)
st.markdown("---")

# 動態產生選單
bonds = []
cols = st.columns(n)
for i in range(n):
    with cols[i]:
        color = COLORS[i]
        label = LABELS[i]
        st.markdown(f'<span class="bond-tag" style="background:{color}">債券 {label}</span>', unsafe_allow_html=True)
        
        selected = st.selectbox(
            f"選擇債券",
            options=["（請選擇）"] + file_names,
            key=f"sel_{i}"
        )

        # 從檔名抓 ISIN，再自動查詢債券資訊
        if selected != "（請選擇）":
            isin = parse_filename(selected)
            if isin:
                with st.spinner(f"查詢 {isin} 基本資料..."):
                    info = lookup_bond_info(isin)
                issuer = info["issuer"]
                auto_coupon = info["coupon"]
                maturity = info["maturity"]
                default_name = f"{issuer} {auto_coupon}% {maturity}".strip() if issuer else selected
                default_coupon = auto_coupon
                if auto_coupon > 0:
                    st.success(f"✅ {isin}｜{issuer}｜票息 {auto_coupon}%｜到期 {maturity}")
            else:
                default_name = selected
                default_coupon = 0.0
        else:
            default_name = ""
            default_coupon = 0.0

        name = st.text_input("債券名稱（可修改）", value=default_name, placeholder="例：Apple 3% 2027", key=f"name_{i}")
        coupon = st.number_input("票息率 % （可修改）", value=default_coupon, step=0.01, min_value=0.0, max_value=20.0, key=f"coupon_{i}")
        
        sheet_id = file_options.get(selected) if selected != "（請選擇）" else None
        bonds.append({
            "sheet_id": sheet_id,
            "name": name or f"債券{label}",
            "coupon": coupon,
            "color": color,
            "label": label,
            "selected": selected
        })

st.markdown("---")

# 讀取選中的試算表
loaded = []
for b in bonds:
    if b["sheet_id"]:
        try:
            with st.spinner(f"讀取 {b['selected']}..."):
                df = read_sheet(b["sheet_id"])
            loaded.append((b, df))
        except Exception as e:
            st.error(f"❌ 讀取 {b['selected']} 失敗：{e}")

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
        valid = [(i, all_data[i][1].get(period_label)) for i in range(len(all_data))]
        valid = [(i, r) for i, r in valid if r]
        if valid:
            best = max(r["total"] for _, r in valid)
            for i, r in valid:
                if r["total"] >= best - 0.0001:
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
    tab1, tab2, tab3 = st.tabs(["📊 標準化（不含息）", "📊 標準化（含息）", "💰 實際價格"])

    with tab1:
        st.info("📌 純價格走勢，**不含票息**。起始=100，僅反映債券市價漲跌。")
        fig = go.Figure()
        for b, df in loaded:
            norm = df["close"] / df["close"].iloc[0] * 100
            fig.add_trace(go.Scatter(x=df["date"], y=norm, name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)))
        fig.update_layout(yaxis_title="相對價格（起始=100，不含息）", hovermode="x unified", height=430,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.info("📌 **含票息**的總報酬指數。起始=100，每日將票息（年票息率 ÷ 365）累積計入，完整反映持有人實際拿到的報酬。")
        fig2 = go.Figure()
        for b, df in loaded:
            tri = total_return_index(df, b["coupon"])
            fig2.add_trace(go.Scatter(x=df["date"], y=tri, name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)))
        fig2.update_layout(yaxis_title="總報酬指數（起始=100，含息）", hovermode="x unified", height=430,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.info("📌 TradingView 原始收盤價，面值100為基準，**不含票息**。")
        fig3 = go.Figure()
        for b, df in loaded:
            fig3.add_trace(go.Scatter(x=df["date"], y=df["close"], name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)))
        fig3.update_layout(yaxis_title="價格（面值100）", hovermode="x unified", height=430,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig3, use_container_width=True)

    # ==========================================
    # 三、年度報酬表
    # ==========================================
    st.markdown("---")
    st.subheader("📅 年度報酬回顧")

    all_annual = [(b, calc_annual(df, b["coupon"])) for b, df in loaded]
    all_years = sorted(set(r["year"] for _, rows in all_annual for r in rows), reverse=True)

    ann_html = '<table style="width:100%;border-collapse:collapse;font-size:0.84rem;border-radius:8px;overflow:hidden;">'
    ann_html += '<thead><tr><th style="background:#1a2744;color:white;padding:8px 12px;text-align:left;">年度</th>'
    for b, _ in all_annual:
        short = b["name"][:12] + ("…" if len(b["name"]) > 12 else "")
        ann_html += f'<th style="background:{b["color"]};color:white;padding:8px 12px;text-align:center;">{b["label"]}. {short}<br><small style="font-weight:400;">價格漲跌</small></th>'
        ann_html += f'<th style="background:{b["color"]};color:white;padding:8px 12px;text-align:center;">票息收益</th>'
        ann_html += f'<th style="background:{b["color"]};color:white;padding:8px 12px;text-align:center;">總報酬 ★</th>'
    ann_html += "</tr></thead><tbody>"

    for year in all_years:
        ann_html += f'<tr><td style="padding:7px 12px;font-weight:700;color:#1a2744;border-bottom:1px solid #f0f0f0;">{year}</td>'
        for b, rows in all_annual:
            row = next((r for r in rows if r["year"] == year), None)
            if row:
                ann_html += f'<td style="padding:7px 12px;text-align:center;border-bottom:1px solid #f0f0f0;{color_cell(row["price"])}">{row["price"]:+.2%}</td>'
                ann_html += f'<td style="padding:7px 12px;text-align:center;border-bottom:1px solid #f0f0f0;color:#2e7d32;">{row["coupon"]:+.2%}</td>'
                ann_html += f'<td style="padding:7px 12px;text-align:center;border-bottom:1px solid #f0f0f0;{color_cell(row["total"])}font-weight:700;">{row["total"]:+.2%}</td>'
            else:
                ann_html += '<td colspan="3" style="text-align:center;color:#ccc;border-bottom:1px solid #f0f0f0;">無資料</td>'
        ann_html += "</tr>"

    ann_html += "</tbody></table>"
    st.markdown(ann_html, unsafe_allow_html=True)

else:
    st.info("👆 請在上方選擇至少一檔債券開始分析")
    st.markdown("""
    **如何新增債券資料？**
    1. 在 TradingView 搜尋債券 ISIN（需 Plus 以上方案）
    2. 開啟圖表，時間軸往左捲到最左邊
    3. 右上角選單 → **匯出圖表資料...**
    4. 上傳 CSV 到 Google 雲端硬碟的 `bond-data` 資料夾
    5. 重新整理此頁面，下拉選單會自動更新！
    """)

st.markdown("---")
st.caption("資料來源：TradingView ｜ 總報酬 = 價格漲跌 + 票息（依實際持有天數）｜ 僅供參考，不構成投資建議")
