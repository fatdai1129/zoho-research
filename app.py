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

# --- デザイン調整（全体的に小さく、タイトにする） ---
st.markdown("""
    <style>
    /* 全体のフォントサイズを小さく */
    html, body, [class*="ViewContainer"] {
        font-size: 14px;
    }
    /* 見出し（H1, H2, H3）を小さく */
    h1 { font-size: 1.8rem !important; padding-top: 0rem; }
    h2 { font-size: 1.4rem !important; margin-top: 1rem !important; border-bottom: 1px solid #ddd; }
    h3 { font-size: 1.1rem !important; margin-top: 0.5rem !important; }
    
    /* サイドバーのフォントサイズ */
    section[data-testid="stSidebar"] {
        width: 250px !important;
    }
    section[data-testid="stSidebar"] .stText { font-size: 13px; }

    /* 余白を詰める */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }
    
    /* 画像の最大サイズを制限して巨大化を防ぐ */
    img {
        max-height: 250px;
        object-fit: contain;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. パスワード管理機能
# ==========================================
SYSTEM_PASSWORD = "Dai565656" 

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("### 🔒 ログイン")
    with st.form("login_form"):
        password_input = st.text_input("パスワード", type="password")
        submit_login = st.form_submit_button("ログイン")
        if submit_login:
            if password_input == SYSTEM_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います")
    st.stop()

# ==========================================
# 2. ZOHO API 通信関数
# ==========================================
def get_access_token():
    url = "https://accounts.zoho.jp/oauth/v2/token"
    params = {
        "refresh_token": REFRESH_TOKEN, "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET, "grant_type": "refresh_token"
    }
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
    for f in [field_name]:
        for pattern in [search_text, clean_text]:
            if not pattern: continue
            for op in ["equals", "starts_with", "contains"]:
                try:
                    res = requests.get(url, headers=headers, params={"criteria": f"({f}:{op}:{pattern})"})
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

# --- スクレイピング関数 ---
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
# 3. メイン画面レイアウトと検索ロジック
# ==========================================
if 'acc_cands' not in st.session_state: st.session_state.acc_cands = []
if 'con_cands' not in st.session_state: st.session_state.con_cands = []
if 'searched' not in st.session_state: st.session_state.searched = False
if 'show_report' not in st.session_state: st.session_state.show_report = False

st.sidebar.subheader("🔍 検索")
with st.sidebar.form("search_form"):
    company_input = st.text_input("会社名", value="")
    person_input = st.text_input("担当者名", value="")
    search_btn = st.form_submit_button("候補検索 (Enter可)")

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
            acc_options = {"-- 会社選択 --": None}
            for a in st.session_state.acc_cands: acc_options[a['Account_Name']] = a
            sel_acc_label = st.sidebar.selectbox("会社候補", list(acc_options.keys()))
            selected_acc = acc_options[sel_acc_label]
        else: st.sidebar.warning("会社なし")
    if person_input:
        if st.session_state.con_cands:
            con_options = {"-- 担当者選択 --": None}
            for c in st.session_state.con_cands:
                c_acc = c.get('Account_Name')
                c_acc_name = c_acc.get('name') if isinstance(c_acc, dict) else (c_acc or "会社未登録")
                con_options[f"{c.get('Full_Name')} ({c_acc_name})"] = c
            sel_con_label = st.sidebar.selectbox("担当者候補", list(con_options.keys()))
            selected_con = con_options[sel_con_label]
        else: st.sidebar.warning("担当者なし")
    if selected_con and not selected_acc:
        acc_info = selected_con.get("Account_Name")
        if isinstance(acc_info, dict) and acc_info.get("id"): selected_acc = get_zoho_record_by_id("Accounts", acc_info["id"])
    if selected_acc or selected_con:
        if st.sidebar.button("レポート作成"):
            st.session_state.final_acc = selected_acc
            st.session_state.final_con = selected_con
            st.session_state.show_report = True

if st.session_state.show_report:
    acc = st.session_state.final_acc
    con = st.session_state.final_con
    display_company = acc.get("Account_Name") if acc else "会社情報なし"
    auto_url = acc.get("Website") if acc else "ー"
    link_url = auto_url if auto_url.startswith('http') else 'https://' + auto_url
    
    st.markdown(f"## 🏢 [{display_company}]({link_url if auto_url != 'ー' else '#'}) 調査結果")
    st.caption(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ===== ① 会社情報 =====
    st.subheader("📊 会社概要")
    hp_data = fetch_company_info(auto_url) if auto_url != "ー" else {"address_list": [], "capital": "ー", "employees": "ー"}
    c1, c2 = st.columns(2)
    with c1:
        if hp_data["address_list"]:
            first = hp_data["address_list"][0]
            others = "".join([f'<div style="margin-top:0px;">{a}</div>' for a in hp_data["address_list"][1:]])
            st.markdown(f'<div style="display:flex;line-height:1.4;"><b>📍 住所:&nbsp;</b><div>{first}{others}</div></div>', unsafe_allow_html=True)
        else: st.markdown("**📍 住所:** ー")
    with c2: st.markdown(f"**👥 社員数:** {hp_data['employees']}")
    c3, c4 = st.columns(2)
    with c3: st.markdown(f"**💰 資本金:** {hp_data['capital']}")
    with c4: st.markdown(f"**📈 売上/年度:** {acc.get('Revenue', 'ー') if acc else 'ー'}")

    # ===== ② 担当者情報 =====
    st.subheader("👤 担当者")
    if con:
        card_img = get_zoho_attachment_image(con.get("id"))
        photo_img = get_zoho_photo(con.get("id"))
        im1, im2 = st.columns(2)
        with im1:
            if card_img: st.image(card_img, caption="名刺", use_column_width=False, width=350)
            else: st.info("名刺なし")
        with im2:
            if photo_img: st.image(photo_img, caption="写真", use_column_width=False, width=200)
            else: st.info("写真なし")
        
        st.write(f"### {con.get('Full_Name', '不明')} 様")
        st.markdown(f"<b>部署・役職:</b> {con.get('Department', 'ー')} {con.get('Title', 'ー')}<br><b>連絡先:</b> {con.get('Mobile') or con.get('Phone') or 'ー'} / {con.get('Email', 'ー')}<br><b>メモ:</b> {con.get('Description', 'ー')}", unsafe_allow_html=True)
    
    # ===== ③ ZOHO履歴・ニュース =====
    st.subheader("📈 ZOHO活動・ニュース")
    c5, c6 = st.columns(2)
    with c5:
        notes = get_activity_notes_final(con.get("id")) if con else []
        if not notes: st.info("活動メモなし")
        else:
            for n in notes[:2]: st.warning(f"📅 {n.get('Modified_Time', '')[:10]}\n\n{n.get('Note_Content')}")
    with c6:
        st.write("**【関連状況】**")
        st.write(f"商談: {get_zoho_sub_data_simple('Accounts', acc.get('id'), 'Deals') if acc else 'ー'}")
        st.write(f"キャンペーン: {get_zoho_sub_data_simple('Contacts', con.get('id'), 'Campaigns') if con else 'ー'}")
        if auto_url != "ー":
            domain = urlparse(auto_url).netloc
            st.markdown(f"🔗 [Googleニュース検索](https://www.google.com/search?q=site:{domain}+お知らせ+OR+ニュース)")
