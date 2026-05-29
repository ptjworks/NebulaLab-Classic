# Nebula Lab Classic

Nebula Lab Classic is the free legacy Streamlit edition of Nebula Lab. It is intended for lightweight scientific data cleaning, quick visualization, rule-based import workflows, and optional OriginPro handoff experiments.

The current commercial/desktop product line lives separately in the main Nebula Lab repository. This Classic repository keeps the older Streamlit app usable for students, small labs, and community exploration.

## What Is Included

- Multi-file CSV/TXT/Excel import and parsing helpers.
- Rule-based column cleanup and saved `.nbr` rule templates.
- Plotly-based overlay and waterfall visualization.
- Optional AI analysis panel using user-provided API credentials.
- Optional OriginPro export helpers for local Windows environments with OriginPro installed.
- Example data in `sample_data/sample_data.csv`.

## What Is Not Included

- No Pro activation or license gate.
- No private update channel.
- No NAS, Gitee, or manual release-distribution workflow.
- No packaged desktop installer. Run this edition with Streamlit.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Optional Services

AI analysis is disabled until you enter your own provider URL, model, and API key in the app. Do not commit local `ai_config.json` or `chat_history.json` files.

OriginPro export requires a local Windows OriginPro installation and Origin's Python bridge package. Install it only on machines that need Origin export:

```bash
pip install "originpro>=1.1.15"
```

If OriginPro is unavailable, the rest of the app can still be used for data import and visualization.

## Maintenance Status

Classic is a legacy/community-oriented edition. It is kept small on purpose. Bug fixes and documentation improvements are welcome, but major product work should happen in the modern Nebula Lab desktop line.

## License

Nebula Lab Classic is released under the GNU Affero General Public License v3.0. See `LICENSE`.
