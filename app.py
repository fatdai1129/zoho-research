import streamlit as st
import pandas as pd
import os
from datetime import datetime
import urllib.request
import urllib.parse
from urllib.parse import urlparse
import ssl
import re
import requests

# ==========================================
# 0. ZOHO API 認証設定
# ==========================================
CLIENT_ID = "1000.O7CN0IQ5AQFYZAYAMM7HAJMLEAS99P"
CLIENT_SECRET = "c32bef6462a56deeda0b5af69daeb060f5b584bcdb"
REFRESH_TOKEN = "1000.890ffb665991551935349aa0d6f41049.092ada10746ae1e4edf605d35cd27fc9"

st.set_page_config(page_title="商談事前調査システム", layout="wide")

# ==========================================
# 1. ログイン画面（CSSで「絶対中央・サイズ固定」を強制）
# ==========================================
SYSTEM_PASSWORD = "Dai565656" 

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
        <style>
        /* 背景色と不要要素の非表示 */
        [data-testid="stSidebar"], [data-testid="stHeader"], header { display: none !important; }
        .stApp { background-color: #111827 !important; }

        /* ログインフォームを画面のど真ん中に「絶対」固定 */
        div[data-testid="stForm"] {
            position: fixed !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            background-color: white !important;
            padding: 50px 40px !important;
            border-radius: 20px !important;
            box-shadow: 0 25px 50px rgba(0,0,0,0.6) !important;
            width: 400px !important; /* 幅を400pxに固定 */
            height: 300px !important; /* 高さを300pxに固定（縦伸び防止） */
            border: none !important;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .login-header {
            color: #1f2937;
            font-size: 24px;
            font-weight: 800;
            margin-bottom: 25px;
            text-align: center;
        }
        
        .stButton button {
            background-color: #2563eb !important;
            color: white !important;
            width: 100% !important;
            height: 48px !important;
            font-weight: bold !important;
            border-radius: 10px !important;
            margin-top: 10px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # ログインフォーム
    with st.form("login_form"):
        st.markdown('<div class="login-header">商談事前調査システム</div>', unsafe_allow_html=True)
        pw_input = st.text_input("PASSWORD", type="password", placeholder="パスワード", label_visibility="collapsed")
        if st.form_submit_button("ログイン"):
            if pw_input == SYSTEM_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
    st.stop()

# ==========================================
# 2. メイン画面デザイン（ログイン後）
# ==========================================
st.markdown("""
    <style>
    html, body, [class*="ViewContainer"] { font-size: 14px; }
    h1 { font-size: 1.6rem !important; color: #0f172a; margin: 0; }
    h2 { font-size: 1.3rem !important; border-bottom: 2px solid #3b82f6; padding-bottom: 5px; margin-top: 15px !important; }
    .block-container { padding-top: 1.5rem !important; }
    img { border-radius: 8px; border: 1px solid #e2e8f0; max-height: 250px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. ZOHO API 通信関数
# ==========================================
def get_access_token():
    url = "https://accounts.zoho.jp/oauth/v2/token"
    params = {"refresh_token": REFRESH_TOKEN, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "refresh_token"}
    try:
        res = requests.post(url, params=params)
        return res.json().get("access_token")
    except: return None

def get_zoho_record_by_id(module, record_id):
    token = get_access_token()
    if not token or not record_id: return None
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    url = f"https://www.zohoapis.jp/crm/v6/{module}/{record_id}"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json().get("data")
            if data: return data[0]
    except: pass
    return None

def search_zoho_candidates(module, search_text):
    token = get_access_token()
    if not token or not search_text: return []
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    url = f"https://www.zohoapis.jp/crm/v6/{module}/search"
    clean_text = re.sub(r"(株式会社|有限会社|合同会社|（株）|\(株\))", "", search_text).strip()
    candidates = []
    seen = set()
    def add_candidates(data):
        for item in data:
            if item['id'] not in seen:
                seen.add(item['id']); candidates.append(item)
    try:
        res = requests.get(url, headers=headers, params={"word": clean_text})
        if res.status_code == 200:
            data = res.json().get("data")
            if data: add_candidates(data)
    except: pass
    field_name = "Account_Name" if module == "Accounts" else "Full_Name"
    try:
        params = {"criteria": f"({field_name}:starts_with:{clean_text})"}
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json().get("data")
            if data: add_candidates(data)
    except: pass
    return candidates

def get_zoho_photo(contact_id):
    token = get_access_token()
    if not token or not contact_id: return None
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/photo"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200 and len(res.content) > 100: return res.content
    except: pass
    return None

def get_zoho_attachment_image(contact_id):
    token = get_access_token()
    if not token or not contact_id: return None
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/Attachments"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json().get("data", [])
            for item in data:
                fname = item.get("File_Name", "").lower()
                if "名刺" in fname and fname.endswith(('.jpg', '.jpeg', '.png')):
                    dl_url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/Attachments/{item.get('id')}"
                    dl_res = requests.get(dl_url, headers=headers)
                    if dl_res.status_code == 200: return dl_res.content
            for item in data:
                if item.get("File_Name", "").lower().endswith(('.jpg', '.jpeg', '.png')):
                    dl_url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/Attachments/{item.get('id')}"
                    dl_res = requests.get(dl_url, headers=headers)
                    if dl_res.status_code == 200: return dl_res.content
    except: pass
    return None

def get_activity_notes_final(contact_id):
    token = get_access_token()
    if not token or not contact_id: return []
    url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/Notes"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200: return res.json().get("data", [])
    except: pass
    return []

def get_zoho_sub_data_simple(module, record_id, sub_module):
    token = get_access_token()
    if not token or not record_id: return "ー"
    url = f"https://www.zohoapis.jp/crm/v6/{module}/{record_id}/{sub_module}"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data: return f"{len(data)}件登録あり"
    except: pass
    return "ー"

def fetch_company_info(base_url):
    if not base_url or base_url == "ー": return {"address_list": [], "capital": "ー", "employees": "ー"}
    target_url = base_url.strip()
    if not target_url.startswith('http'): target_url = 'https://' + target_url
    info = {"address_list": [], "capital": "ー", "employees": "ー"}
    TARGET_PREFS = ["東京都", "神奈川県", "千葉県", "埼玉県", "茨城県", "栃木県", "群馬県", "大阪府", "京都府", "兵庫県", "滋賀県", "奈良県", "和歌山県", "愛知県", "静岡県", "岐阜県", "三重県"]
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    def get_html(u):
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=3) as response:
            return response.read().decode('utf-8', errors='ignore')
    try:
        html = get_html(target_url)
        links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)
        company_urls = [target_url]
        for link in links:
            if any(k in link.lower() for k in ['company', 'about', 'access']):
                full_url = urllib.parse.urljoin(target_url, link)
                if full_url not in company_urls: company_urls.append(full_url)
        for t_p in company_urls[:4]:
            try:
                t_html = get_html(t_p)
                parts = [p.strip() for p in re.split(r'<[^>]+>', t_html) if p.strip()]
                for i, p in enumerate(parts):
                    if any(pref in p for pref in TARGET_PREFS):
                        clean_addr = re.sub(r'〒?\s*\d{3}-\d{4}', '', p).strip()
                        if len(clean_addr) > 5 and clean_addr not in info["address_list"]: info["address_list"].append(clean_addr)
                    if info["employees"] == "ー" and any(k in p for k in ["従業員", "社員数"]):
                        match = re.search(r'(\d+[,，\d]*)\s*[名人]', p)
                        if match: info["employees"] = match.group(0)
                    if info["capital"] == "ー" and "資本金" in p:
                        for offset in range(0, 3):
                            if i+offset < len(parts) and "円" in parts[i+offset]: info["capital"] = parts[i+offset]; break
            except: continue
    except: pass
    return info

# ==========================================
# 4. 検索・レポート表示（全Enter対応）
# ==========================================
if 'acc_cands' not in st.session_state: st.session_state.acc_cands = []
if 'con_cands' not in st.session_state: st.session_state.con_cands = []
if 'searched' not in st.session_state: st.session_state.searched = False
if 'show_report' not in st.session_state: st.session_state.show_report = False

st.sidebar.markdown("### 🔍 調査対象検索")

# 1. 候補検索フォーム
with st.sidebar.form("search_form"):
    company_input = st.text_input("会社名", placeholder="株式会社抜きでOK")
    person_input = st.text_input("担当者名", placeholder="苗字のみでOK")
    if st.form_submit_button("候補を検索", use_container_width=True):
        with st.spinner("ZOHO通信中..."):
            st.session_state.acc_cands = search_zoho_candidates("Accounts", company_input) if company_input else []
            st.session_state.con_cands = search_zoho_candidates("Contacts", person_input) if person_input else []
            st.session_state.searched = True
            st.session_state.show_report = False

# 2. レポート作成フォーム
if st.session_state.searched:
    st.sidebar.markdown("---")
    with st.sidebar.form("report_generate_form"):
        f_acc = None
        f_con = None
        
        if company_input and st.session_state.acc_cands:
            opts = {"-- 会社選択 --": None}
            for a in st.session_state.acc_cands: opts[a['Account_Name']] = a
            f_acc = opts[st.selectbox("会社候補", list(opts.keys()))]
            
        if person_input and st.session_state.con_cands:
            c_opts = {"-- 担当者選択 --": None}
            for c in st.session_state.con_cands:
                c_acc_name = c.get('Account_Name', {}).get('name') if isinstance(c.get('Account_Name'), dict) else "不明"
                c_opts[f"{c.get('Full_Name')} ({c_acc_name})"] = c
            f_con = c_opts[st.selectbox("担当者候補", list(c_opts.keys()))]

        # 会社補完
        if f_con and not f_acc:
            a_info = f_con.get("Account_Name")
            if isinstance(a_info, dict) and a_info.get("id"): f_acc = get_zoho_record_by_id("Accounts", a_info["id"])

        # Enterキーでレポート作成を実行
        if st.form_submit_button("レポートを作成 🚀", use_container_width=True):
            if f_acc or f_con:
                st.session_state.final_acc = f_acc
                st.session_state.final_con = f_con
                st.session_state.show_report = True
            else:
                st.sidebar.error("対象を選択してください")

# 3. レポート表示本体
if st.session_state.show_report:
    acc = st.session_state.final_acc
    con = st.session_state.final_con
    name = acc.get("Account_Name") if acc else "調査対象"
    url = acc.get("Website") if acc else "ー"
    link = url if url.startswith('http') else 'https://' + url
    
    st.markdown(f"## 🏢 [{name}]({link if url != 'ー' else '#'}) 調査レポート")
    st.caption(f"📅 取得日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 会社情報
    st.subheader("📊 会社プロファイル")
    hp = fetch_company_info(url) if url != "ー" else {"address_list": [], "capital": "ー", "employees": "ー"}
    c1, c2 = st.columns(2)
    with c1:
        if hp["address_list"]:
            st.markdown(f'<div style="display:flex;"><b>📍 住所:&nbsp;</b><div>{"<br>".join(hp["address_list"])}</div></div>', unsafe_allow_html=True)
        else: st.write("**📍 住所:** ー")
    with c2: st.write(f"**👥 社員数:** {hp['employees']}")
    c3, c4 = st.columns(2)
    with c3: st.write(f"**💰 資本金:** {hp['capital']}")
    with c4: st.write(f"**📈 年商:** {acc.get('Revenue', 'ー') if acc else 'ー'}")

    # 担当者情報
    st.subheader("👤 担当者プロファイル")
    if con:
        card = get_zoho_attachment_image(con.get("id")); photo = get_zoho_photo(con.get("id"))
        im1, im2 = st.columns(2)
        with im1:
            if card: st.image(card, caption="名刺", width=350)
            else: st.info("名刺未登録")
        with im2:
            if photo: st.image(photo, caption="写真", width=180)
            else: st.info("写真未登録")
        st.markdown(f"### {con.get('Full_Name')} 様")
        st.markdown(f"<b>役職:</b> {con.get('Title', 'ー')}<br><b>電話:</b> {con.get('Mobile') or con.get('Phone') or 'ー'}<br><b>メール:</b> {con.get('Email', 'ー')}<br><b>人物メモ:</b> {con.get('Description', 'ー')}", unsafe_allow_html=True)
    
    # 活動履歴
    st.subheader("📈 活動状況・ニュース")
    c5, c6 = st.columns(2)
    with c5:
        notes = get_activity_notes_final(con.get("id")) if con else []
        if not notes: st.write("活動メモなし")
        else:
            for n in notes[:2]: st.warning(f"📅 {n.get('Modified_Time', '')[:10]}\n\n{n.get('Note_Content')}")
    with c6:
        st.write(f"商談登録: {get_zoho_sub_data_simple('Accounts', acc.get('id'), 'Deals') if acc else 'ー'}")
        st.write(f"キャンペーン: {get_zoho_sub_data_simple('Contacts', con.get('id'), 'Campaigns') if con else 'ー'}")
        if url != "ー":
            domain = urlparse(url).netloc
            st.markdown(f"🔗 [Googleニュース検索](https://www.google.com/search?q=site:{domain}+お知らせ+OR+ニュース)")
