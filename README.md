# PRESSLAB

AI 演講自動出稿工具。上傳錄音、照片、簡報，自動生成財經雜誌風格報導稿並輸出 Google Doc。

## 功能

- 🎙️ Gemini 2.5 Flash 轉錄演講逐字稿
- 📄 PyPDF2 解析簡報，掃描版自動改用 Gemini Vision
- ✍️ Claude Sonnet 撰寫 1,100–1,200 字報導稿
- 📁 自動建立 Google Drive 資料夾，存檔音檔、照片、PDF
- 📝 自動建立 Google Doc，套用格式、插入照片
- ⚡ 逐字稿快取（transcript.txt），重跑時跳過 Gemini 節省費用

## 技術架構
音檔 + 照片 + PDF
↓
Gemini 2.5 Flash → 逐字稿（存成 transcript.txt）
↓
Claude Sonnet → 報導稿（JSON 格式）
↓
Google Doc（含格式、照片、標題）
## 部署

### 1. 安裝套件
```bash
pip install -r requirements.txt
```

### 2. 設定 Streamlit Secrets

在 Streamlit Cloud 或本地 `.streamlit/secrets.toml` 填入：
```toml
APP_PASSWORD = "your_password"
GEMINI_API_KEY = "your_gemini_key"
CLAUDE_API_KEY = "your_claude_key"
DRIVE_FOLDER_ID = "your_google_drive_folder_id"
GOOGLE_REFRESH_TOKEN = "your_refresh_token"
GOOGLE_CLIENT_ID = "your_client_id"
GOOGLE_CLIENT_SECRET = "your_client_secret"
WRITING_TEMPLATE = "your_writing_template"
```

### 3. 啟動
```bash
streamlit run presslab_app.py
```

## API Keys 申請

- **Gemini API**：[Google AI Studio](https://aistudio.google.com)
- **Claude API**：[Anthropic Console](https://console.anthropic.com)
- **Google OAuth**：[Google Cloud Console](https://console.cloud.google.com) → 建立 OAuth 用戶端，取得 refresh token

## License

MIT
