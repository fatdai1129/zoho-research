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

# --- ZOHO API 通信関数 ---
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
    """IDから単一のレコードを確実に取得する"""
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
    """【新機能】株式会社などを抜いても柔軟に検索し、候補リストを返す"""
    token = get_access_token()
    if not token or not search_text: return []
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    url = f"https://www.zohoapis.jp/crm/v6/{module}/search"
    
    # 検索の邪魔になる「株式会社」などを取り除く
    clean_text = re.sub(r"(株式会社|有限会社|合同会社|（株）|\(株\))", "", search_text).strip()
    
    candidates = []
    seen = set()

    def add_candidates(data):
        for item in data:
            if item['id'] not in seen:
                seen.add(item['id'])
                candidates.append(item)

    # 1. ワード検索 (最も柔軟な検索)
    try:
        res = requests.get(url, headers=headers, params={"word": clean_text})
        if res.status_code == 200:
            data = res.json().get("data")
            if data: add_candidates(data)
    except: pass

    # 2. 条件検索 (ワード検索で漏れたものを拾う)
    field_name = "Account_Name" if module == "Accounts" else "Full_Name"
    fields_to_search = [field_name]
    if module == "Contacts":
        fields_to_search.extend(["Last_Name", "First_Name"])
        
    for f in fields_to_search:
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
    """ZOHOのプロフィール写真を取得"""
    token = get_access_token()
    if not token or not contact_id: return None
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    photo_url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/photo"
    try:
        res = requests.get(photo_url, headers=headers)
        # プロフィール画像が存在すればバイナリデータを返す
        if res.status_code == 200 and len(res.content) > 100:
            return res.content
    except: pass
    return None

def get_zoho_attachment_image(contact_id):
    """ZOHOの添付ファイルから名刺等の画像を取得"""
    token = get_access_token()
    if not token or not contact_id: return None
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    attach_url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/Attachments"
    try:
        res = requests.get(attach_url, headers=headers)
        if res.status_code == 200:
            data = res.json().get("data", [])
            # 優先：「名刺」という文字が含まれる画像を探す
            for item in data:
                file_name = item.get("File_Name", "").lower()
                if "名刺" in file_name and file_name.endswith(('.jpg', '.jpeg', '.png')):
                    att_id = item.get("id")
                    dl_url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/Attachments/{att_id}"
                    dl_res = requests.get(dl_url, headers=headers)
                    if dl_res.status_code == 200: return dl_res.content
            # 無ければ：最初の画像ファイルを返す
            for item in data:
                file_name = item.get("File_Name", "").lower()
                if file_name.endswith(('.jpg', '.jpeg', '.png')):
                    att_id = item.get("id")
                    dl_url = f"https://www.zohoapis.jp/crm/v6/Contacts/{contact_id}/Attachments/{att_id}"
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

# --- スクレイピング関数 (以前の仕様を完全に維持) ---
def fetch_company_info(base_url):
    if not base_url or base_url == "ー": return {"address_list": [], "capital": "ー", "employees": "ー"}
    target_url = base_url.strip()
    if not target_url.startswith('http'): target_url = 'https://' + target_url
    
    info = {"address_list": [], "capital": "ー", "employees": "ー"}
    TARGET_PREFS = ["東京都", "神奈川県", "千葉県", "埼玉県", "茨城県", "栃木県", "群馬県", 
                    "大阪府", "京都府", "兵庫県", "滋賀県", "奈良県", "和歌山県", 
                    "愛知県", "静岡県", "岐阜県", "三重県"]
    
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
                        if len(clean_addr) > 5 and clean_addr not in info["address_list"]:
                            info["address_list"].append(clean_addr)
                    
                    if info["employees"] == "ー" and any(k in p for k in ["従業員", "社員数"]):
                        match = re.search(r'(\d+[,，\d]*)\s*[名人]', p)
                        if match: info["employees"] = match.group(0)
                        elif i + 1 < len(parts):
                            match_next = re.search(r'(\d+[,，\d]*)\s*[名人]', parts[i+1])
                            if match_next: info["employees"] = match_next.group(0)

                    if info["capital"] == "ー" and "資本金" in p:
                        for offset in range(0, 3):
                            if i+offset < len(parts) and "円" in parts[i+offset]:
                                info["capital"] = parts[i+offset]; break
            except: continue
    except: pass
    return info

# ==========================================
# 3. メイン画面レイアウトと検索ロジック
# ==========================================

# 状態管理の初期化
if 'acc_cands' not in st.session_state: st.session_state.acc_cands = []
if 'con_cands' not in st.session_state: st.session_state.con_cands = []
if 'searched' not in st.session_state: st.session_state.searched = False
if 'show_report' not in st.session_state: st.session_state.show_report = False

st.sidebar.header("調査対象検索")
st.sidebar.caption("※片方だけの入力でも検索できます")
company_input = st.sidebar.text_input("会社名 (株式会社抜きでOK)", value="")
person_input = st.sidebar.text_input("担当者名", value="")

# 検索ボタン
if st.sidebar.button("候補を検索"):
    with st.spinner("ZOHOから候補を取得中..."):
        st.session_state.acc_cands = search_zoho_candidates("Accounts", company_input) if company_input else []
        st.session_state.con_cands = search_zoho_candidates("Contacts", person_input) if person_input else []
        st.session_state.searched = True
        st.session_state.show_report = False # 検索し直したらレポートを隠す

selected_acc = None
selected_con = None

# 候補リストの表示
if st.session_state.searched:
    st.sidebar.markdown("---")
    st.sidebar.write("**▼ 候補から対象を選んでください**")
    
    # 会社候補のドロップダウン
    if company_input:
        if st.session_state.acc_cands:
            acc_options = {"-- 選択してください --": None}
            for a in st.session_state.acc_cands:
                acc_options[a['Account_Name']] = a
            sel_acc_label = st.sidebar.selectbox("会社候補", list(acc_options.keys()))
            selected_acc = acc_options[sel_acc_label]
        else:
            st.sidebar.warning("該当する会社が見つかりません")

    # 担当者候補のドロップダウン
    if person_input:
        if st.session_state.con_cands:
            con_options = {"-- 選択してください --": None}
            for c in st.session_state.con_cands:
                c_acc = c.get('Account_Name')
                c_acc_name = c_acc.get('name') if isinstance(c_acc, dict) else (c_acc or "会社未登録")
                label = f"{c.get('Full_Name')} ({c_acc_name})"
                con_options[label] = c
            sel_con_label = st.sidebar.selectbox("担当者候補", list(con_options.keys()))
            selected_con = con_options[sel_con_label]
        else:
            st.sidebar.warning("該当する担当者が見つかりません")
            
    # 【親切機能】担当者だけ選ばれた場合、会社情報をZOHOから自動で引き直す
    if selected_con and not selected_acc:
        acc_info = selected_con.get("Account_Name")
        if isinstance(acc_info, dict) and acc_info.get("id"):
            selected_acc = get_zoho_record_by_id("Accounts", acc_info["id"])

    # どちらか選ばれたらレポート表示ボタンを出す
    if selected_acc or selected_con:
        if st.sidebar.button("レポートを作成"):
            st.session_state.final_acc = selected_acc
            st.session_state.final_con = selected_con
            st.session_state.show_report = True

# --- レポート表示エリア ---
if st.session_state.show_report:
    acc = st.session_state.final_acc
    con = st.session_state.final_con
    
    display_company = acc.get("Account_Name") if acc else "会社情報なし"
    auto_url = acc.get("Website") if acc else "ー"
    
    if auto_url != "ー":
        link_url = auto_url if auto_url.startswith('http') else 'https://' + auto_url
        st.markdown(f"## 🏢 [{display_company}]({link_url}) 商談調査レポート")
    else:
        st.markdown(f"## 🏢 {display_company} 商談調査レポート")
    st.caption(f"レポート作成日: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ===== ① 会社プロファイル =====
    st.subheader("📊 会社プロファイル")
    if auto_url == "ー":
        hp_data = {"address_list": [], "capital": "ー", "employees": "ー"}
    else:
        with st.spinner(f"HP調査中..."):
            hp_data = fetch_company_info(auto_url)
    
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        # 📍 住所の頭揃えレイアウト維持
        if hp_data["address_list"]:
            first_addr = hp_data["address_list"][0]
            other_addrs = "".join([f'<div style="margin-top: 0px;">{a}</div>' for a in hp_data["address_list"][1:]])
            st.markdown(f"""
            <div style="display: flex; flex-direction: row; line-height: 1.5; margin-bottom: 1rem;">
                <div style="font-weight: bold; white-space: nowrap;">📍 住所:&nbsp;</div>
                <div>
                    <div>{first_addr}</div>
                    {other_addrs}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("**📍 住所:** ー")
    with row1_col2:
        st.markdown(f"**👥 社員数:** {hp_data['employees']}")

    # 資本金と売上の高さ揃え維持
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        cap_val = hp_data['capital'] if hp_data['capital'] != "ー" else "ー"
        st.markdown(f"**💰 資本金:** {cap_val}")
    with row2_col2:
        st.markdown(f"**📈 売上/年度:** {acc.get('Revenue', 'ー') if acc else 'ー'}")

    st.divider()

    # ===== ② 担当者プロファイル =====
    st.subheader("👤 担当者プロファイル")
    if con:
        card_img = get_zoho_attachment_image(con.get("id"))
        photo_img = get_zoho_photo(con.get("id"))
        
        # 指示通り、画像を左と右に配置
        img_col1, img_col2 = st.columns(2)
        with img_col1:
            if card_img:
                st.image(card_img, caption="名刺 (ZOHOより取得)", use_column_width=True)
            else:
                st.info("ZOHOに名刺画像(添付ファイル)が登録されていません")
        with img_col2:
            if photo_img:
                st.image(photo_img, caption="写真 (ZOHOより取得)", use_column_width=True)
            else:
                st.info("ZOHOにプロフィール写真が登録されていません")
        
        # 指示通り、画像の下にプロファイルを配置
        st.markdown("<br>", unsafe_allow_html=True) # 少し余白をあける
        cid = con.get("id")
        st.write(f"### [{con.get('Full_Name', '名称不明')} 様](https://crm.zoho.jp/crm/tab/Contacts/{cid})")
        st.markdown(f"""
        <b>部署:</b> {con.get('Department', 'ー')}<br>
        <b>役職:</b> {con.get('Title', 'ー')}<br>
        <b>電話:</b> {con.get('Mobile') or con.get('Phone') or 'ー'}<br>
        <b>メール:</b> {con.get('Email', 'ー')}<br>
        <b>人物メモ:</b><br>{con.get('Description', 'ー')}
        """, unsafe_allow_html=True)
    else:
        st.warning("担当者が選択されていません。")
        
    st.divider()

    # ===== ④ ZOHO活動状況 =====
    st.subheader("📈 ZOHO活動状況")
    if con:
        notes = get_activity_notes_final(con.get("id"))
        if not notes: st.info("ー")
        else:
            for n in notes[:3]:
                st.warning(f"📅 **({n.get('Modified_Time', '')[:10]})**\n\n{n.get('Note_Content')}")
    else: st.info("ー")

    st.markdown("<hr style='border: none; border-top: 1px dashed #cccccc; margin: 1.5rem 0;'>", unsafe_allow_html=True)

    # ===== ③ 商談・キャンペーン =====
    col3, col4 = st.columns(2)
    with col3:
        st.write("**【関連する商談】**")
        st.info(get_zoho_sub_data_simple("Accounts", acc.get("id"), "Deals") if acc else "ー")
    with col4:
        st.write("**【キャンペーン履歴】**")
        st.success(get_zoho_sub_data_simple("Contacts", con.get("id"), "Campaigns") if con else "ー")
    st.divider()

    # ===== 最新ニュース =====
    st.subheader("📰 最新ニュース (自社HP限定)")
    if auto_url != "ー":
        domain = urlparse(auto_url).netloc
        comp_name_for_search = display_company.replace("株式会社", "").strip()
        st.markdown(f"### 👉 [{display_company} の公式ニュースを検索する](https://www.google.com/search?q=site:{domain}+{comp_name_for_search}+お知らせ+OR+ニュース)")
