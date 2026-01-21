# donutcoresync downloader (Python + CustomTkinter)

Python GUI app (CustomTkinter) that lets you pick a download directory and fetch preset files from the web.

## Setup
```pwsh
cd .\donutcoresync
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## How it works
- Choose a target folder (created if needed).
- Select one of the predefined downloads and click **Download**.
- Progress/status is shown at the bottom.

## Adding more downloads
Edit `app.py` and append to `DOWNLOAD_ITEMS`:
```python
{"name": "My File", "url": "https://example.com/file.zip"}
```
