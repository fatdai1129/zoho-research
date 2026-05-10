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
# 1. ログイン機能（中央配置デザイン・完全版）
# ==========================================
SYSTEM_PASSWORD = "Dai565656" 

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
        <style>
        /* 背景とサイドバー等の非表示 */
        [data-testid="stSidebar"], header { display: none; }
        .stApp { background-color: #1e2130; }
        
        /* 画面中央に固定するコンテナ */
        .login-outer {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        
        /* ログインカードのデザイン */
        .login-card {
            background-color: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            width: 400px;
            text-align: center;
        }
        
        /* ボタンの色調整 */
        div.stButton > button {
            background-color: #3b82f6 !important;
            color: white !important;
            border: none !important;
            height: 45px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # ログインフォームの構築
    st.markdown('<div class="login-outer">', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown("<h2 style='color:#333; margin-top:0;'>商談事前調査システム</h2>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            # ラベルを非表示にし、プレースホルダーのみに
            pw = st.text_input("パスワード", type="password", placeholder="パスワードを入力", label_visibility="collapsed")
            submit_login = st.form_submit_button("ログイン", use_container_width=True)
            
            if submit_login:
                if pw == SYSTEM_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("パスワードが正しくありません")
        
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ==========================================
# 2. メイン画面のデザイン（タイトに調整）
# ==========================================
st.markdown("""
    <style>
    html, body, [class*="ViewContainer"] { font-size: 14px; }
    h1 { font-size: 1.6rem !important; padding-top: 0rem; color: #1e293b; }
    h2 { font-size: 1.3rem !important; margin-top: 0.8rem !important; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px; }
    h3 { font-size: 1.1rem !important; margin-top: 0.5rem !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    div[data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
    img { max-height: 240px; object-fit: contain; border: 1px solid #eee; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. ZOHO API / 通信関連（変更なし）
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
    for op in ["equals", "starts_with", "contains"]:
        try:
            params = {"criteria": f"({field_name}:starts_with:{clean_text})"}
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 200:
                data = res.json().get("data")
                if data: add_candidates(data)
        except: continue
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

def get_zoho_sub_data_simple(module, record_id, sub_module):
    token = get_access_token()
    if not token or not record_id: return "ー"
    url = f"https://www.zohoapis.jp/crm/v6/{module}/{record_id}/{sub_module}"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data: return f"{len(data)}件の登録があります"
    except: pass
    return "ー"

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
# 4. 検索とレポート表示
# ==========================================
if 'acc_cands' not in st.session_state: st.session_state.acc_cands = []
if 'con_cands' not in st.session_state: st.session_state.con_cands = []
if 'searched' not in st.session_state: st.session_state.searched = False
if 'show_report' not in st.session_state: st.session_state.show_report = False

st.sidebar.subheader("🔍 調査対象を検索")

# 検索フォーム（Enterキー対応）
with st.sidebar.form("search_form"):
    company_input = st.text_input("会社名", placeholder="株式会社抜きで検索可")
    person_input = st.text_input("担当者名", placeholder="苗字のみで検索可")
    search_btn = st.form_submit_button("候補を検索", use_container_width=True)

if search_btn:
    with st.spinner("取得中..."):
        st.session_state.acc_cands = search_zoho_candidates("Accounts", company_input) if company_input else []
        st.session_state.con_cands = search_zoho_candidates("Contacts", person_input) if person_input else []
        st.session_state.searched = True
        st.session_state.show_report = False

selected_acc = None
selected_con = None

if st.session_state.searched:
    st.sidebar.markdown("---")
    if company_input:
        if st.session_state.acc_cands:
            acc_options = {"-- 会社を選んでください --": None}
            for a in st.session_state.acc_cands: acc_options[a['Account_Name']] = a
            sel_acc_label = st.sidebar.selectbox("会社候補", list(acc_options.keys()))
            selected_acc = acc_options[sel_acc_label]
        else: st.sidebar.warning("該当する会社なし")
    
    if person_input:
        if st.session_state.con_cands:
            con_options = {"-- 担当者を選んでください --": None}
            for c in st.session_state.con_cands:
                c_acc = c.get('Account_Name')
                c_acc_name = c_acc.get('name') if isinstance(c_acc, dict) else (c_acc or "会社未登録")
                con_options[f"{c.get('Full_Name')} ({c_acc_name})"] = c
            sel_con_label = st.sidebar.selectbox("担当者候補", list(con_options.keys()))
            selected_con = con_options[sel_con_label]
        else: st.sidebar.warning("該当する担当者なし")
    
    if selected_con and not selected_acc:
        acc_info = selected_con.get("Account_Name")
        if isinstance(acc_info, dict) and acc_info.get("id"): selected_acc = get_zoho_record_by_id("Accounts", acc_info["id"])
    
    if selected_acc or selected_con:
        if st.sidebar.button("レポートを作成 🚀", use_container_width=True):
            st.session_state.final_acc = selected_acc
            st.session_state.final_con = selected_con
            st.session_state.show_report = True

if st.session_state.show_report:
    acc = st.session_state.final_acc
    con = st.session_state.final_con
    display_company = acc.get("Account_Name") if acc else "会社情報なし"
    auto_url = acc.get("Website") if acc else "ー"
    link_url = auto_url if auto_url.startswith('http') else 'https://' + auto_url
    
    st.markdown(f"## 🏢 [{display_company}]({link_url if auto_url != 'ー' else '#'}) 調査レポート")
    st.caption(f"📅 調査日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 会社情報
    st.subheader("📊 会社プロファイル")
    hp_data = fetch_company_info(auto_url) if auto_url != "ー" else {"address_list": [], "capital": "ー", "employees": "ー"}
    c1, c2 = st.columns(2)
    with c1:
        if hp_data["address_list"]:
            first = hp_data["address_list"][0]; others = "".join([f'<div style="margin-top:0px;">{a}</div>' for a in hp_data["address_list"][1:]])
            st.markdown(f'<div style="display:flex;line-height:1.4;"><b>📍 住所:&nbsp;</b><div>{first}{others}</div></div>', unsafe_allow_html=True)
        else: st.markdown("**📍 住所:** ー")
    with c2: st.markdown(f"**👥 社員数:** {hp_data['employees']}")
    c3, c4 = st.columns(2)
    with c3: st.markdown(f"**💰 資本金:** {hp_data['capital']}")
    with c4: st.markdown(f"**📈 売上/年度:** {acc.get('Revenue', 'ー') if acc else 'ー'}")

    # 担当者情報
    st.subheader("👤 担当者プロファイル")
    if con:
        card_img = get_zoho_attachment_image(con.get("id")); photo_img = get_zoho_photo(con.get("id"))
        im1, im2 = st.columns(2)
        with im1:
            if card_img: st.image(card_img, caption="名刺", use_container_width=False, width=320)
            else: st.info("名刺未登録")
        with im2:
            if photo_img: st.image(photo_img, caption="写真", use_container_width=False, width=180)
            else: st.info("写真未登録")
        
        st.write(f"### {con.get('Full_Name', '不明')} 様")
        st.markdown(f"<b>部署・役職:</b> {con.get('Department', 'ー')} {con.get('Title', 'ー')}<br><b>連絡先:</b> {con.get('Mobile') or con.get('Phone') or 'ー'} / {con.get('Email', 'ー')}<br><b>人物メモ:</b> {con.get('Description', 'ー')}", unsafe_allow_html=True)
    
    # 履歴等
    st.subheader("📈 活動状況・ニュース")
    c5, c6 = st.columns(2)
    with c5:
        notes = get_activity_notes_final(con.get("id")) if con else []
        if not notes: st.info("ZOHO活動メモなし")
        else:
            for n in notes[:2]: st.warning(f"📅 {n.get('Modified_Time', '')[:10]}\n\n{n.get('Note_Content')}")
    with c6:
        st.write("**【ZOHO 関連状況】**")
        st.write(f"商談登録: {get_zoho_sub_data_simple('Accounts', acc.get('id'), 'Deals') if acc else 'ー'}")
        st.write(f"キャンペーン履歴: {get_zoho_sub_data_simple('Contacts', con.get('id'), 'Campaigns') if con else 'ー'}")
        if auto_url != "ー":
            domain = urlparse(auto_url).netloc
            st.markdown(f"🔗 [HP内ニュースを検索](https://www.google.com/search?q=site:{domain}+お知らせ+OR+ニュース)")
