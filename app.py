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
    """從檔名解析 ISIN（支援 US 和 XS 開頭）"""
    import re
    isin_match = re.search(r'([A-Z]{2}[A-Z0-9]{10})', name)
    isin = isin_match.group(1) if isin_match else ""
    return isin

LOCAL_DB = {
    "US02079KBP12": {"issuer": "Alphabet 公司債6", "coupon": 5.65, "maturity": "2056"},
    "US30303MAE21": {"issuer": "Meta平台公司債9", "coupon": 5.625, "maturity": "2055"},
    "US64110LBA35": {"issuer": "網飛公司債3", "coupon": 5.4, "maturity": "2054"},
    "US03769MAC01": {"issuer": "阿波羅全球公司債1", "coupon": 5.8, "maturity": "2054"},
    "US191216DS69": {"issuer": "可口可樂公司債5", "coupon": 5.3, "maturity": "2054"},
    "US92343VGW81": {"issuer": "威瑞森電信公司債12", "coupon": 5.5, "maturity": "2054"},
    "XS2747599509": {"issuer": "沙烏地阿拉伯債7", "coupon": 5.75, "maturity": "2054"},
    "US29736RAU41": {"issuer": "雅詩蘭黛公司債3", "coupon": 5.15, "maturity": "2053"},
    "US037833EW60": {"issuer": "蘋果公司債14", "coupon": 4.85, "maturity": "2053"},
    "US91324PEW86": {"issuer": "聯合健康集團債9", "coupon": 5.05, "maturity": "2053"},
    "US532457CG18": {"issuer": "禮來公司債1", "coupon": 4.875, "maturity": "2053"},
    "US91324PES74": {"issuer": "聯合健康集團債5", "coupon": 5.875, "maturity": "2053"},
    "US459200KZ37": {"issuer": "國際商業機器債4", "coupon": 5.1, "maturity": "2053"},
    "US459200KV23": {"issuer": "國際商業機器公司債1", "coupon": 4.9, "maturity": "2052"},
    "US45866FAX24": {"issuer": "洲際交易所公司債1", "coupon": 4.95, "maturity": "2052"},
    "US872898AJ06": {"issuer": "TSMC公司債 4", "coupon": 4.5, "maturity": "2052"},
    "US084664DB47": {"issuer": "波克夏金融公司債2", "coupon": 3.85, "maturity": "2052"},
    "US92343VGP31": {"issuer": "威瑞森電信公司債11", "coupon": 3.875, "maturity": "2052"},
    "US828807DJ39": {"issuer": "賽門房地產集團債1", "coupon": 3.8, "maturity": "2050"},
    "US191216CQ13": {"issuer": "可口可樂公司債2", "coupon": 4.2, "maturity": "2050"},
    "US92343VFD10": {"issuer": "威瑞森電信公司債9", "coupon": 4.0, "maturity": "2050"},
    "US254687FM36": {"issuer": "迪士尼公司債2", "coupon": 2.75, "maturity": "2049"},
    "XS1982116136": {"issuer": "沙烏地阿拉伯石油公司債4", "coupon": 4.375, "maturity": "2049"},
    "US58933YAW57": {"issuer": "默克藥廠公司債1", "coupon": 4.0, "maturity": "2049"},
    "US125523AK66": {"issuer": "信諾公司債1", "coupon": 4.9, "maturity": "2048"},
    "US88579YBD22": {"issuer": "3M 公司債1", "coupon": 4.0, "maturity": "2048"},
    "US084664CQ25": {"issuer": "波克夏海瑟威金融公司債1", "coupon": 4.2, "maturity": "2048"},
    "XS1807174559": {"issuer": "卡達政府國際債1", "coupon": 5.103, "maturity": "2048"},
    "US023135BJ40": {"issuer": "亞馬遜公司債1", "coupon": 4.05, "maturity": "2047"},
    "US375558BK80": {"issuer": "吉利德科學公司債1", "coupon": 4.15, "maturity": "2047"},
    "US037833CH12": {"issuer": "蘋果公司債6", "coupon": 4.25, "maturity": "2047"},
    "US002824BH26": {"issuer": "亞培公司債2", "coupon": 4.9, "maturity": "2046"},
    "XS1508675508": {"issuer": "沙烏地阿拉伯政府國際債券5", "coupon": 4.5, "maturity": "2046"},
    "US02209SAV51": {"issuer": "高特利集團公司債1", "coupon": 3.875, "maturity": "2046"},
    "US92343VCK89": {"issuer": "威瑞森電信公司債1", "coupon": 4.862, "maturity": "2046"},
    "US594918BT09": {"issuer": "微軟公司債2", "coupon": 3.7, "maturity": "2046"},
    "US125523CF53": {"issuer": "信諾公司債2", "coupon": 4.8, "maturity": "2046"},
    "US20030NBU46": {"issuer": "康卡斯特公司債1", "coupon": 3.4, "maturity": "2046"},
    "US375558BD48": {"issuer": "吉利德科學公司債2", "coupon": 4.75, "maturity": "2046"},
    "US02079KBN63": {"issuer": "Alphabet 公司債5", "coupon": 5.5, "maturity": "2046"},
    "US30303M8X35": {"issuer": "Meta平台公司債10", "coupon": 5.5, "maturity": "2045"},
    "US747525AK99": {"issuer": "高通公司債3", "coupon": 4.8, "maturity": "2045"},
    "US25468PDB94": {"issuer": "華德迪士尼公司債1", "coupon": 4.125, "maturity": "2044"},
    "US717081DK61": {"issuer": "輝瑞藥廠公司債2", "coupon": 4.4, "maturity": "2044"},
    "US449276AF17": {"issuer": "IBM金融公司債1", "coupon": 5.25, "maturity": "2044"},
    "US02209SAR40": {"issuer": "高特利集團公司債2", "coupon": 5.375, "maturity": "2044"},
    "US12572QAF28": {"issuer": "芝加哥期交所債1", "coupon": 5.3, "maturity": "2043"},
    "US037833AL42": {"issuer": "蘋果公司債2", "coupon": 3.85, "maturity": "2043"},
    "US084670BK32": {"issuer": "波克夏公司債1", "coupon": 4.5, "maturity": "2043"},
    "US594918BZ68": {"issuer": "微軟公司債7", "coupon": 4.1, "maturity": "2037"},
    "US717081EC37": {"issuer": "輝瑞藥廠公司債1", "coupon": 4.0, "maturity": "2036"},
    "US035242AM81": {"issuer": "百威英博(金融)公司債2", "coupon": 4.7, "maturity": "2036"},
    "US91159HJN17": {"issuer": "美國合眾銀公司債2", "coupon": 5.836, "maturity": "2034"},
    "US55608KBG94": {"issuer": "麥格理集團公司債10", "coupon": 5.491, "maturity": "2033"},
    "US686330AR22": {"issuer": "歐力士公司債2", "coupon": 5.2, "maturity": "2032"},
    "USG91139AL26": {"issuer": "TSMC全球公司債6", "coupon": 4.625, "maturity": "2032"},
    "US92556HAC16": {"issuer": "維康公司債3", "coupon": 4.95, "maturity": "2050"},
    "US31428XCA28": {"issuer": "聯邦快遞公司債1", "coupon": 5.25, "maturity": "2050"},
    "US09062XAG88": {"issuer": "生物基因公司債2", "coupon": 3.15, "maturity": "2050"},
    "US37045VAT70": {"issuer": "通用汽車公司債7", "coupon": 5.95, "maturity": "2049"},
    "US854502AJ02": {"issuer": "史丹利百得公司債3", "coupon": 4.85, "maturity": "2048"},
    "US00206RCU41": {"issuer": "AT&T公司債12", "coupon": 5.65, "maturity": "2047"},
    "US94974BGU89": {"issuer": "富國銀行公司債10", "coupon": 4.75, "maturity": "2046"},
    "US172967KR13": {"issuer": "花旗集團公司債14", "coupon": 4.75, "maturity": "2046"},
    "US00206RCQ39": {"issuer": "AT&T公司債5", "coupon": 4.75, "maturity": "2046"},
    "US58013MFA71": {"issuer": "麥當勞公司債2", "coupon": 4.875, "maturity": "2045"},
    "US42824CAY57": {"issuer": "慧與公司債1", "coupon": 6.35, "maturity": "2045"},
    "US09062XAD57": {"issuer": "生物基因公司債1", "coupon": 5.2, "maturity": "2045"},
    "US37045VAJ98": {"issuer": "通用汽車公司債4", "coupon": 5.2, "maturity": "2045"},
    "US61747YDY86": {"issuer": "摩根士丹利債20", "coupon": 4.3, "maturity": "2045"},
    "US94974BGE48": {"issuer": "富國銀行債9", "coupon": 4.65, "maturity": "2044"},
    "US172967HS33": {"issuer": "花旗集團債12", "coupon": 5.3, "maturity": "2044"},
    "XS1049699926": {"issuer": "渣打集團債6", "coupon": 5.7, "maturity": "2044"},
    "US404280AQ21": {"issuer": "匯豐控股公司債8", "coupon": 5.25, "maturity": "2044"},
    "US37045VAF76": {"issuer": "通用汽車公司債3", "coupon": 6.25, "maturity": "2043"},
    "US92553PAP71": {"issuer": "維康公司債2", "coupon": 4.375, "maturity": "2043"},
    "US00206RBH49": {"issuer": "AT&T公司債1", "coupon": 4.3, "maturity": "2042"},
    "US71568QAB32": {"issuer": "印尼國家電力債2", "coupon": 5.25, "maturity": "2042"},
    "US854502AA92": {"issuer": "史丹利百得公司債2", "coupon": 5.2, "maturity": "2040"},
    "US50076QAN60": {"issuer": "卡夫亨氏公司債1", "coupon": 6.5, "maturity": "2040"},
    "XS2885079702": {"issuer": "國泰人壽公司債2", "coupon": 5.3, "maturity": "2039"},
    "US46625HHF01": {"issuer": "摩根大通銀行債3", "coupon": 6.4, "maturity": "2038"},
    "US37045VAP58": {"issuer": "通用汽車公司債2", "coupon": 5.15, "maturity": "2038"},
    "US126650CY46": {"issuer": "CVS公司債1", "coupon": 4.78, "maturity": "2038"},
    "US38141GFD16": {"issuer": "美高盛公司債14", "coupon": 6.75, "maturity": "2037"},
    "US00206RDR03": {"issuer": "AT&T公司債3", "coupon": 5.25, "maturity": "2037"},
    "US404280AG49": {"issuer": "匯豐銀行公司債4", "coupon": 6.5, "maturity": "2036"},
    "US38143YAC75": {"issuer": "美商高盛證券公司債16", "coupon": 6.45, "maturity": "2036"},
    "US925524AX89": {"issuer": "維康公司債1", "coupon": 6.875, "maturity": "2036"},
    "US37045VAK61": {"issuer": "通用汽車公司債1", "coupon": 6.6, "maturity": "2036"},
    "XS3151416727": {"issuer": "富邦人壽(新加坡)1", "coupon": 5.45, "maturity": "2035"},
    "US06051GLU12": {"issuer": "美國銀行公司債6", "coupon": 5.872, "maturity": "2034"},
    "XS2852920342": {"issuer": "國泰人壽公司債1", "coupon": 5.95, "maturity": "2034"},
    "US458140CA64": {"issuer": "英特爾公司債5", "coupon": 4.15, "maturity": "2032"},
}

def batch_lookup_bond_info(isin_list):
    """從本地對照表查詢（94檔完整資料）"""
    return {isin: LOCAL_DB.get(isin, {"issuer": isin, "coupon": 0.0, "maturity": ""}) for isin in isin_list}

def lookup_bond_info(isin):
    """單一 ISIN 查詢"""
    return LOCAL_DB.get(isin, {"issuer": isin, "coupon": 0.0, "maturity": ""})


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

    # 預載所有 ISIN 資訊（批次查詢，一次搞定）
    all_isins = [parse_filename(name) for name in file_names]
    all_isins = [isin for isin in all_isins if isin]
    if all_isins:
        with st.spinner(f"正在查詢 {len(all_isins)} 檔債券基本資料..."):
            bond_info_cache = batch_lookup_bond_info(tuple(all_isins))
    else:
        bond_info_cache = {}

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

        # 從預載快取取債券資訊
        if selected != "（請選擇）":
            isin = parse_filename(selected)
            if isin and isin in bond_info_cache:
                info = bond_info_cache[isin]
                issuer = info["issuer"]
                auto_coupon = info["coupon"]
                maturity = info["maturity"]
                default_name = f"{issuer} {auto_coupon}% {maturity}".strip() if issuer != isin else selected
                default_coupon = auto_coupon
                if st.session_state.get(f"last_sel_{i}") != selected:
                    st.session_state[f"name_{i}"] = default_name
                    st.session_state[f"coupon_{i}"] = default_coupon
                    st.session_state[f"last_sel_{i}"] = selected
                if auto_coupon > 0:
                    st.success(f"✅ {isin}｜{issuer}｜票息 {auto_coupon}%｜到期 {maturity}")
            else:
                if st.session_state.get(f"last_sel_{i}") != selected:
                    st.session_state[f"name_{i}"] = selected
                    st.session_state[f"coupon_{i}"] = 0.0
                    st.session_state[f"last_sel_{i}"] = selected
        else:
            if st.session_state.get(f"last_sel_{i}") != selected:
                st.session_state[f"name_{i}"] = ""
                st.session_state[f"coupon_{i}"] = 0.0
                st.session_state[f"last_sel_{i}"] = selected

        name = st.text_input("債券名稱（可修改）", placeholder="例：Apple 3% 2027", key=f"name_{i}")
        coupon = st.number_input("票息率 % （可修改）", step=0.01, min_value=0.0, max_value=20.0, key=f"coupon_{i}")
        
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

    # 找出所有已載入債券的最早和最晚日期
    all_min_date = min(df["date"].min() for _, df in loaded).date()
    all_max_date = max(df["date"].max() for _, df in loaded).date()

    from datetime import date, timedelta
    today = all_max_date

    # 初始化 session_state
    if "chart_start" not in st.session_state:
        st.session_state["chart_start"] = all_min_date
    if "chart_end" not in st.session_state:
        st.session_state["chart_end"] = all_max_date

    # 快速選擇按鈕
    st.markdown("**快速選擇區間：**")
    qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
    if qcol1.button("1年"):
        st.session_state["chart_start"] = max(today - timedelta(days=365), all_min_date)
        st.rerun()
    if qcol2.button("2年"):
        st.session_state["chart_start"] = max(today - timedelta(days=730), all_min_date)
        st.rerun()
    if qcol3.button("3年"):
        st.session_state["chart_start"] = max(today - timedelta(days=1095), all_min_date)
        st.rerun()
    if qcol4.button("5年"):
        st.session_state["chart_start"] = max(today - timedelta(days=1825), all_min_date)
        st.rerun()
    if qcol5.button("全部"):
        st.session_state["chart_start"] = all_min_date
        st.rerun()

    date_col1, date_col2 = st.columns(2)
    with date_col1:
        chart_start = st.date_input(
            "📅 圖表起始日",
            value=st.session_state["chart_start"],
            min_value=all_min_date,
            max_value=all_max_date,
        )
        st.session_state["chart_start"] = chart_start
    with date_col2:
        chart_end = st.date_input(
            "📅 圖表結束日",
            value=st.session_state["chart_end"],
            min_value=all_min_date,
            max_value=all_max_date,
        )
        st.session_state["chart_end"] = chart_end

    # 篩選後的 loaded
    chart_start_ts = pd.Timestamp(chart_start)
    chart_end_ts = pd.Timestamp(chart_end)
    loaded_filtered = [
        (b, df[(df["date"] >= chart_start_ts) & (df["date"] <= chart_end_ts)].copy())
        for b, df in loaded
    ]

    tab1, tab2, tab3 = st.tabs(["📊 標準化（不含息）", "📊 標準化（含息）", "💰 實際價格"])

    with tab1:
        st.info("📌 純價格走勢，**不含票息**。起始=100，僅反映債券市價漲跌。")
        fig = go.Figure()
        for b, df in loaded_filtered:
            if df.empty: continue
            norm = df["close"] / df["close"].iloc[0] * 100
            fig.add_trace(go.Scatter(x=df["date"], y=norm, name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)))
        fig.update_layout(yaxis_title="相對價格（起始=100，不含息）", hovermode="x unified", height=430,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.info("📌 **含票息**的總報酬指數。起始=100，每日將票息（年票息率 ÷ 365）累積計入，完整反映持有人實際拿到的報酬。")
        fig2 = go.Figure()
        for b, df in loaded_filtered:
            if df.empty: continue
            tri = total_return_index(df, b["coupon"])
            fig2.add_trace(go.Scatter(x=df["date"], y=tri, name=f'{b["label"]}. {b["name"]}',
                line=dict(color=b["color"], width=2)))
        fig2.update_layout(yaxis_title="總報酬指數（起始=100，含息）", hovermode="x unified", height=430,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.info("📌 TradingView 原始收盤價，面值100為基準，**不含票息**。")
        fig3 = go.Figure()
        for b, df in loaded_filtered:
            if df.empty: continue
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
