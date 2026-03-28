import streamlit as st
import os
import io
import re
import json
import tempfile
from PIL import Image
import anthropic
import google.generativeai as genai
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

# ════════════════════════════════════════
# 設定
# ════════════════════════════════════════
st.set_page_config(
    page_title="PRESSLAB",
    page_icon="🎙️",
    layout="centered"
)

# ── 寫作規範
WRITING_TEMPLATE = """
# Role: 台灣財經科技資深編輯 (Business Insider Taiwan Style) v32

## 00. 強制輸出前核查協議
在輸出任何內容前，必須逐條核查以下清單，全部確認後才能開始輸出。

## 0. 最高指導原則：抗疲勞機制
- 全程高張力：無論文章長度，必須確保從首段到末段維持 100% 一致的「敘事重組」力度。
- 嚴禁虎頭蛇尾：AI 容易在長文後半段退化為字面直譯，這是絕對禁止的。
- 結尾檢核：在輸出最後一段前，必須自我質問：「這一段是否像第一段一樣精彩？」若否，請重寫。

## 1. 核心角色與敘事邏輯
- 角色定位：具備深厚產業洞察的商業財經編輯，風格對標《Business Insider》或《今周刊》。
- 商業說書人：拒絕流水帳，善用具畫面感的詞彙。
- 直接以台灣財經口語重組。
- 主詞連貫性：動作連續時必用逗號連接，嚴禁句點切斷後用代名詞（它、他、這）重啟。
- 嚴禁憑空加戲：原文無語氣、情緒、神態描述時，嚴禁自行為當事人添加任何詮釋性修飾。
- 嚴禁自行腦補前因脈絡：原文未交代的行為動機、背景前因，嚴禁自行添加。
- 嚴禁不必要的過渡語：直接切入事實即可。
- 嚴禁重複時地資訊：已在前文交代的時間、地點細節，後文嚴禁重複出現。

## 2. 視覺與格式鐵律
- 視覺潔癖：禁 Emoji、禁粗體斜體、嚴禁破折號（改用逗號或括號）。
- 標點節奏（一逗到底）：段落內用逗號連接，句點只能出現在段落最後一字。
- 標點符號使用全形：，。！？；：「」『』（）【】，嚴禁使用半形標點符號。
- 排版規範：中英數需半形空格，數字需加千分位逗號。
- 中英文混排規範：中文與英文字母或數字之間必須加一個半形空格。
- 輕薄短小：每隔 150-200 字，必須插入一個無標點的段落標題。
- 段落標題風格：逆襲、突圍、破局、決勝、翻轉、重塑、顛覆、護城河、典範轉移、決勝時刻、韌性升級、雙軌並進

## 3. 新聞寫作鐵律
- 痛點先行：開篇直接切入最關鍵的發現或衝突，絕不鋪墊。
- 事實就是事實：嚴禁「值得注意的是」、「這才是關鍵」等引導語。
- 結尾讓數據說話：結尾段落以數據或事實收束，嚴禁說教。

## 4. 台灣在地化與禁語
- 絕對禁止中國用語與香港用語。
- 嚴禁引述強化詞：「直言」、「坦言」，統一以「說」、「表示」、「指出」代替。
- 視頻→影片、質量→品質、項目→計畫、優化→最佳化、信息→資訊

## 5. 段落結構
- 第一段：開場（點出活動名稱與講者身份，帶入核心結論）
- 第二段：核心結論
- 中間段落：依主題展開，加入具體案例和數據佐證
- 最後段：結尾前瞻（必須來自演講內容，嚴禁瞎掰）
- 引述金句格式：講者表示：「金句內容。」

## 6. 強制輸出前再次核查協議
在輸出任何內容前，必須逐條核查以上清單，全部確認後才能開始輸出。
"""

# ════════════════════════════════════════
# Google Drive 工具函式
# ════════════════════════════════════════
def get_drive_service():
    """用 Service Account 建立 Docs 服務（建立 Google Doc 用）"""
    creds_info = st.secrets["google_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=[
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/documents'
        ]
    )
    return build('drive', 'v3', credentials=creds), build('docs', 'v1', credentials=creds)

def get_oauth_drive_service():
    """用 OAuth 建立 Drive + Docs 服務"""
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GOOGLE_REFRESH_TOKEN"],
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token"
    )
    drive = build('drive', 'v3', credentials=creds)
    docs = build('docs', 'v1', credentials=creds)
    return drive, docs

def create_drive_folder(drive_service, folder_name, parent_folder_id):
    """在指定資料夾下建立子資料夾"""
    meta = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id]
    }
    folder = drive_service.files().create(body=meta, fields='id').execute()
    return folder['id']

def upload_to_drive(drive_service, file_bytes, filename, mimetype, folder_id):
    """上傳檔案到 Drive 資料夾"""
    meta = {'name': filename, 'parents': [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype)
    f = drive_service.files().create(body=meta, media_body=media, fields='id').execute()
    return f['id']

def make_file_public(drive_service, file_id):
    drive_service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'},
        fields='id'
    ).execute()
    return f'https://drive.google.com/uc?export=download&id={file_id}'

def check_transcript_exists(drive_service, folder_id):
    """檢查資料夾內是否已有 transcript.txt"""
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and name='transcript.txt' and trashed=false",
        fields='files(id)'
    ).execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None

def read_transcript_from_drive(drive_service, file_id):
    """從 Drive 讀取逐字稿"""
    content = drive_service.files().get_media(fileId=file_id).execute()
    return content.decode('utf-8')

def save_transcript_to_drive(drive_service, folder_id, transcript_text):
    """把逐字稿存成 transcript.txt"""
    meta = {'name': 'transcript.txt', 'parents': [folder_id]}
    media = MediaIoBaseUpload(
        io.BytesIO(transcript_text.encode('utf-8')),
        mimetype='text/plain'
    )
    drive_service.files().create(body=meta, media_body=media, fields='id').execute()

def extract_pdf_text(pdf_bytes, gemini_model):
    """解析 PDF，掃描版改用 Gemini Vision"""
    import PyPDF2
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = ''
        for page in reader.pages:
            text += page.extract_text() or ''
        if len(text.strip()) > 100:
            return text
        raise ValueError('掃描圖檔')
    except Exception:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            pdf_file = genai.upload_file(tmp_path, mime_type='application/pdf')
            response = gemini_model.generate_content([pdf_file, '請將這份 PDF 的所有文字內容完整轉錄出來。'])
            return response.text
        finally:
            os.unlink(tmp_path)

# ════════════════════════════════════════
# 密碼保護
# ════════════════════════════════════════
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🎙️ PRESSLAB")
    st.caption("請輸入密碼以繼續")
    password = st.text_input("密碼", type="password", placeholder="輸入密碼")
    if st.button("登入", type="primary"):
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤")
    return False

if not check_password():
    st.stop()

# ════════════════════════════════════════
# 主介面
# ════════════════════════════════════════
st.title("🎙️ PRESSLAB")
st.caption("AI 演講出稿系統 · Gemini × Claude Sonnet")
st.divider()

# ── 講者資訊
st.subheader("講者資訊")
col1, col2 = st.columns(2)
with col1:
    speaker_name = st.text_input("講者姓名 *", placeholder="簡立峰")
    speaker_title = st.text_input("講者職稱 *", placeholder="台灣董事總經理")
with col2:
    speaker_company = st.text_input("講者公司（選填）", placeholder="Google")
    topic = st.text_input("演講題目 *", placeholder="AI Agent 時代的台灣機會")

event_name = st.text_input("活動名稱", value="AI 創新百強趨勢年會")

st.divider()

# ── 上傳檔案
st.subheader("上傳檔案")
col1, col2, col3 = st.columns(3)
with col1:
    audio_file = st.file_uploader("🎙️ 錄音檔案 *", type=['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac'])
with col2:
    photo_file = st.file_uploader("📷 講者照片（選填）", type=['jpg', 'jpeg', 'png', 'webp'])
with col3:
    pdf_file = st.file_uploader("📄 演講簡報（選填）", type=['pdf'])

st.divider()

# ── 指定主題
st.subheader("指定主題（選填）")
col1, col2, col3 = st.columns(3)
with col1:
    t1 = st.text_input("主題一", placeholder="例：AI 人才培育")
with col2:
    t2 = st.text_input("主題二", placeholder="例：數據驅動決策")
with col3:
    t3 = st.text_input("主題三", placeholder="例：供應鏈韌性")

st.divider()

# ── 生成按鈕
if st.button("⚡ 開始生成報導稿", type="primary", use_container_width=True):

    # 驗證必填
    if not speaker_name:
        st.error("請填入講者姓名")
        st.stop()
    if not speaker_title:
        st.error("請填入講者職稱")
        st.stop()
    if not topic:
        st.error("請填入演講題目")
        st.stop()
    if not audio_file:
        st.error("請上傳錄音檔案")
        st.stop()

    # ── 取得 API Keys
    gemini_key = st.secrets["GEMINI_API_KEY"]
    claude_key = st.secrets["CLAUDE_API_KEY"]
    parent_folder_id = st.secrets["DRIVE_FOLDER_ID"]

    # ── 建立資料夾名稱
    if speaker_company:
        folder_name = f"{speaker_name}_{speaker_company}_{speaker_title}_{topic}"
    else:
        folder_name = f"{speaker_name}_{speaker_title}_{topic}"

    try:
        oauth_drive, docs_service = get_oauth_drive_service()

        # ── 建立 Drive 資料夾
        with st.status("📁 建立 Google Drive 資料夾...", expanded=True) as status:
            folder_id = create_drive_folder(oauth_drive, folder_name, parent_folder_id)
            st.write(f"✅ 資料夾已建立：{folder_name}")

            # 上傳音檔
            audio_bytes = audio_file.read()
            audio_ext = audio_file.name.split('.')[-1].lower()
            mime_map = {'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'm4a': 'audio/mp4',
                       'aac': 'audio/aac', 'ogg': 'audio/ogg', 'flac': 'audio/flac'}
            audio_mime = mime_map.get(audio_ext, 'audio/mpeg')
            audio_drive_id = upload_to_drive(oauth_drive, audio_bytes, audio_file.name, audio_mime, folder_id)
            st.write(f"✅ 音檔上傳完成：{audio_file.name}")

            # 上傳照片
            photo_public_url = None
            if photo_file:
                photo_bytes = photo_file.read()
                img = Image.open(io.BytesIO(photo_bytes))
                img.thumbnail((800, 600), Image.LANCZOS)
                compressed_buf = io.BytesIO()
                img.save(compressed_buf, 'JPEG', quality=85)
                compressed_bytes = compressed_buf.getvalue()
                photo_id = upload_to_drive(oauth_drive, compressed_bytes, 'photo.jpg', 'image/jpeg', folder_id)
                photo_public_url = make_file_public(oauth_drive, photo_id)
                st.write("✅ 照片上傳完成")

            # 上傳 PDF
            pdf_bytes_data = None
            if pdf_file:
                pdf_bytes_data = pdf_file.read()
                upload_to_drive(oauth_drive, pdf_bytes_data, pdf_file.name, 'application/pdf', folder_id)
                st.write("✅ PDF 上傳完成")

            status.update(label="📁 檔案上傳完成", state="complete")

        # ── STEP 1: 逐字稿
        genai.configure(api_key=gemini_key)
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')

        with st.status("📝 STEP 1：處理逐字稿...", expanded=True) as status:
            transcript_id = check_transcript_exists(oauth_drive, folder_id)
            if transcript_id:
                st.write("⚡ 發現快取逐字稿，跳過 Gemini（節省費用）")
                transcript = read_transcript_from_drive(oauth_drive, transcript_id)
                st.write(f"✅ 逐字稿讀取完成（{len(transcript)} 字）")
            else:
                st.write("🎙️ Gemini 轉錄中（需要幾分鐘）...")
                with tempfile.NamedTemporaryFile(suffix=f'.{audio_ext}', delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                try:
                    audio_upload = genai.upload_file(tmp_path, mime_type=audio_mime)
                    transcript = gemini_model.generate_content([
                        audio_upload,
                        '請將這段演講音檔完整轉錄成繁體中文逐字稿，保留所有內容，包括數據、案例、金句，不要摘要也不要省略。'
                    ]).text
                finally:
                    os.unlink(tmp_path)
                st.write(f"✅ 逐字稿完成（{len(transcript)} 字）")
                save_transcript_to_drive(oauth_drive, folder_id, transcript)
                st.write("✅ 逐字稿已存檔（下次跳過 Gemini）")
            status.update(label="📝 逐字稿完成", state="complete")

        # ── STEP 2: PDF
        pdf_text = ''
        if pdf_bytes_data:
            with st.status("📄 STEP 2：解析 PDF...", expanded=True) as status:
                pdf_text = extract_pdf_text(pdf_bytes_data, gemini_model)
                if len(pdf_text) > 100000:
                    pdf_text = gemini_model.generate_content([
                        f'請將以下文字摘要成 5,000 字以內的重點：\n\n{pdf_text}'
                    ]).text
                st.write(f"✅ PDF 解析完成（{len(pdf_text)} 字）")
                status.update(label="📄 PDF 完成", state="complete")

        # ── STEP 3: Claude 寫稿
        topics = [t for t in [t1, t2, t3] if t.strip()]
        num_topics = len(topics)
        if num_topics == 3:
            topic_guide = f'主題一「{topics[0]}」佔 30%，主題二「{topics[1]}」佔 30%，主題三「{topics[2]}」佔 30%'
            topic_body = f'主題一「{topics[0]}」（30%）\n主題二「{topics[1]}」（30%）\n主題三「{topics[2]}」（30%）'
        elif num_topics == 2:
            topic_guide = f'主題一「{topics[0]}」佔 50%，主題二「{topics[1]}」佔 40%'
            topic_body = f'主題一「{topics[0]}」（50%）\n主題二「{topics[1]}」（40%）'
        elif num_topics == 1:
            topic_guide = f'主題一「{topics[0]}」佔 90%'
            topic_body = f'主題一「{topics[0]}」（90%）'
        else:
            topic_guide = '依演講內容自行判斷結構'
            topic_body = '依演講內容自行判斷'

        speaker_info = speaker_name
        if speaker_company or speaker_title:
            speaker_info += '/' + (speaker_company or '') + (speaker_title or '')

        with st.status("✍️ STEP 3：Claude 撰寫報導稿...", expanded=True) as status:
            st.write("🤖 Claude Sonnet 寫作中...")
            claude_client = anthropic.Anthropic(api_key=claude_key)

            claude_prompt = f"""活動：{event_name}
講者：{speaker_info}
講題：{topic}
主題分配：{topic_guide}

請根據以下資料，撰寫一篇報導稿，輸出格式為 JSON：

{{
  "title_line1": "標題第一行（嚴禁標點符號，嚴禁任何英文單字，全部繁體中文，10-15字以內）",
  "title_line2": "標題第二行（嚴禁標點符號，嚴禁任何英文單字，全部繁體中文，10-15字以內）",
  "photo_caption": "格式：{speaker_title}{speaker_company}{speaker_name}表示：「最震撼的金句」",
  "bullets": [
    "重點一（20字以內）",
    "重點二（20字以內）",
    "重點三（20字以內）"
  ],
  "body": "正文（1,400-1,500字，必須寫滿，結構：開場→核心結論→{topic_body}→結尾前瞻，每150-200字插入段落小標題）"
}}

{WRITING_TEMPLATE}

{'【講者簡報資料】\\n' + pdf_text if pdf_text else ''}

【演講逐字稿】
{transcript}

只輸出 JSON，不要其他文字。"""

            response = claude_client.messages.create(
                model='claude-sonnet-4-5',
                max_tokens=4096,
                temperature=0.3,
                messages=[{'role': 'user', 'content': claude_prompt}]
            )

            raw = response.content[0].text.strip()
            if raw.startswith('```'):
                raw = re.sub(r'^```[a-z]*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw).strip()

            data = json.loads(raw)
            title_line1 = data.get('title_line1', '')
            title_line2 = data.get('title_line2', '')
            photo_caption = data.get('photo_caption', '')
            bullets = data.get('bullets', [])
            body = data.get('body', '')

            # 全形標點後處理
            def is_cjk(c): return '\u4e00' <= c <= '\u9fff'
            punct_map = {',': '，', '.': '。', '!': '！', '?': '？', ';': '；', ':': '：', '(': '（', ')': '）'}
            chars = list(body)
            for i, char in enumerate(chars):
                if char in punct_map:
                    if (i > 0 and is_cjk(chars[i-1])) or (i < len(chars)-1 and is_cjk(chars[i+1])):
                        chars[i] = punct_map[char]
            body = ''.join(chars)

            st.write(f"✅ Claude 完成（內文 {len(body)} 字）")
            status.update(label="✍️ 報導稿完成", state="complete")

        # ── 建立 Google Doc
        with st.status("📄 建立 Google Doc...", expanded=True) as status:
            company_title = (speaker_company or '') + (speaker_title or '')
            doc_title = f'{speaker_name}/{company_title}' if company_title else speaker_name
            doc = docs_service.documents().create(body={'title': doc_title}).execute()
            doc_id = doc['documentId']
            doc_url = f'https://docs.google.com/document/d/{doc_id}/edit'

            info_line = f'講者：{company_title} {speaker_name}　|　講題：{topic}'
            bullets_text = '\n'.join([f'{i+1}. {b}' for i, b in enumerate(bullets)])
            PHOTO_PH = '[PHOTO_HERE]'

            full_text = (
                info_line + '\n\n' +
                title_line1 + '\n' + title_line2 + '\n\n' +
                (PHOTO_PH + '\n' if photo_public_url else '') +
                (photo_caption + '\n\n' if photo_caption else '') +
                bullets_text + '\n\n' +
                body
            )

            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': [{'insertText': {'location': {'index': 1}, 'text': full_text}}]}
            ).execute()

            # 套用格式
            doc_content = docs_service.documents().get(documentId=doc_id).execute()
            fmt = []
            for el in doc_content.get('body', {}).get('content', []):
                if 'paragraph' not in el: continue
                s = el.get('startIndex', 0)
                e = el.get('endIndex', 0)
                t = ''.join(pe.get('textRun', {}).get('content', '') for pe in el['paragraph'].get('elements', [])).strip()
                if not t: continue
                if t.startswith('講者：'):
                    fmt += [
                        {'updateParagraphStyle': {'range': {'startIndex': s, 'endIndex': e}, 'paragraphStyle': {'alignment': 'CENTER', 'spaceBelow': {'magnitude': 12, 'unit': 'PT'}}, 'fields': 'alignment,spaceBelow'}},
                        {'updateTextStyle': {'range': {'startIndex': s, 'endIndex': e}, 'textStyle': {'fontSize': {'magnitude': 10, 'unit': 'PT'}, 'bold': False, 'foregroundColor': {'color': {'rgbColor': {'red': 0.46, 'green': 0.46, 'blue': 0.46}}}}, 'fields': 'fontSize,bold,foregroundColor'}}
                    ]
                elif t == title_line1 or t == title_line2:
                    fmt += [
                        {'updateParagraphStyle': {'range': {'startIndex': s, 'endIndex': e}, 'paragraphStyle': {'alignment': 'CENTER', 'lineSpacing': 130, 'spaceBelow': {'magnitude': 4, 'unit': 'PT'}}, 'fields': 'alignment,lineSpacing,spaceBelow'}},
                        {'updateTextStyle': {'range': {'startIndex': s, 'endIndex': e}, 'textStyle': {'fontSize': {'magnitude': 22, 'unit': 'PT'}, 'bold': True}, 'fields': 'fontSize,bold'}}
                    ]
                elif t == photo_caption:
                    fmt += [
                        {'updateParagraphStyle': {'range': {'startIndex': s, 'endIndex': e}, 'paragraphStyle': {'alignment': 'CENTER', 'spaceBelow': {'magnitude': 12, 'unit': 'PT'}}, 'fields': 'alignment,spaceBelow'}},
                        {'updateTextStyle': {'range': {'startIndex': s, 'endIndex': e}, 'textStyle': {'fontSize': {'magnitude': 10, 'unit': 'PT'}, 'bold': False, 'foregroundColor': {'color': {'rgbColor': {'red': 0.46, 'green': 0.46, 'blue': 0.46}}}}, 'fields': 'fontSize,bold,foregroundColor'}}
                    ]
                elif t and t[0].isdigit() and '. ' in t:
                    fmt += [
                        {'updateParagraphStyle': {'range': {'startIndex': s, 'endIndex': e}, 'paragraphStyle': {'spaceBelow': {'magnitude': 4, 'unit': 'PT'}}, 'fields': 'spaceBelow'}},
                        {'updateTextStyle': {'range': {'startIndex': s, 'endIndex': e}, 'textStyle': {'fontSize': {'magnitude': 12, 'unit': 'PT'}, 'bold': True}, 'fields': 'fontSize,bold'}}
                    ]
                elif len(t) <= 25 and t and t[-1] not in '。，、！？' and not t[0].isdigit():
                    fmt += [
                        {'updateParagraphStyle': {'range': {'startIndex': s, 'endIndex': e}, 'paragraphStyle': {'spaceAbove': {'magnitude': 12, 'unit': 'PT'}, 'spaceBelow': {'magnitude': 6, 'unit': 'PT'}}, 'fields': 'spaceAbove,spaceBelow'}},
                        {'updateTextStyle': {'range': {'startIndex': s, 'endIndex': e}, 'textStyle': {'fontSize': {'magnitude': 14, 'unit': 'PT'}, 'bold': True}, 'fields': 'fontSize,bold'}}
                    ]
                else:
                    fmt += [
                        {'updateParagraphStyle': {'range': {'startIndex': s, 'endIndex': e}, 'paragraphStyle': {'lineSpacing': 160, 'spaceBelow': {'magnitude': 8, 'unit': 'PT'}}, 'fields': 'lineSpacing,spaceBelow'}},
                        {'updateTextStyle': {'range': {'startIndex': s, 'endIndex': e}, 'textStyle': {'fontSize': {'magnitude': 12, 'unit': 'PT'}, 'bold': False, 'foregroundColor': {'color': {'rgbColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13}}}}, 'fields': 'fontSize,bold,foregroundColor'}}
                    ]
            if fmt:
                docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': fmt}).execute()

            # 插入照片
            if photo_public_url:
                doc_content = docs_service.documents().get(documentId=doc_id).execute()
                ph_index = None
                for el in doc_content.get('body', {}).get('content', []):
                    if 'paragraph' in el:
                        for pe in el['paragraph'].get('elements', []):
                            if 'textRun' in pe and PHOTO_PH in pe['textRun']['content']:
                                ph_index = pe['startIndex'] + pe['textRun']['content'].index(PHOTO_PH)
                if ph_index is not None:
                    docs_service.documents().batchUpdate(
                        documentId=doc_id,
                        body={'requests': [
                            {'deleteContentRange': {'range': {'startIndex': ph_index, 'endIndex': ph_index + len(PHOTO_PH)}}},
                            {'insertInlineImage': {'location': {'index': ph_index}, 'uri': photo_public_url, 'objectSize': {'height': {'magnitude': 252, 'unit': 'PT'}, 'width': {'magnitude': 336, 'unit': 'PT'}}}}
                        ]}
                    ).execute()
                    doc_content = docs_service.documents().get(documentId=doc_id).execute()
                    for el in doc_content.get('body', {}).get('content', []):
                        if 'paragraph' in el:
                            for pe in el['paragraph'].get('elements', []):
                                if 'inlineObjectElement' in pe:
                                    ps = el.get('startIndex', 0)
                                    pe_end = el.get('endIndex', 0)
                                    docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': [{'updateParagraphStyle': {'range': {'startIndex': ps, 'endIndex': pe_end}, 'paragraphStyle': {'alignment': 'CENTER'}, 'fields': 'alignment'}}]}).execute()
                                    break

            status.update(label="📄 Google Doc 完成", state="complete")

        # ── 完成
        st.success("🎉 報導稿生成完成！")
        st.link_button("📄 開啟 Google Doc", doc_url, type="primary", use_container_width=True)
        if len(body) < 800:
            st.warning(f"⚠️ 內文只有 {len(body)} 字，建議重新執行")

    except Exception as e:
        st.error(f"❌ 發生錯誤：{str(e)}")
        st.exception(e)
