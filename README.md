# Nebula Lab Classic

Nebula Lab Classic is the original Streamlit edition of Nebula Lab: a small, free and open-source web app for cleaning up instrument data files and plotting them. You run it from source on your own computer and use it in your browser. Its interface is in Simplified Chinese.

This repository is a snapshot of that edition. It was published in May 2026 and has not been changed since.

> **Looking for Nebula Lab?** The current product is the Nebula Lab desktop app for Windows. It is a separate code base, and development continues there.
>
> Website: <https://nebulalab.app/> · Download: <https://github.com/ptjworks/NebulaLab-Releases/releases/latest>

## Features

The app has three pages, chosen in the sidebar.

**数据加载 (data import)**

- Upload several files at once. `.csv`, `.txt`, `.dat`, `.xy` and `.asc` files are read as delimited text, `.xlsx` and `.xls` files as Excel workbooks.
- The encoding (for example UTF-8 or GBK), delimiter and header row are detected automatically. You can change the header row, the rows to skip, the delimiter and the worksheet.
- Choose which columns to keep, rename them, and add arithmetic steps: add, subtract, multiply or divide by a number, or by the column's first value, maximum or minimum.
- Settings belong to each file. Before importing, copy the current file's settings to the other files (matched by column position or by name) or apply a saved rule to all of them: a file that has no settings yet is skipped on import.
- Save settings as named rules (`.nbr` JSON files in the `rules/` folder), and import or export rule files. `rules/热重.nbr` is an example rule for thermogravimetric (TGA) data.
- Give each file a display name that the charts use.

**分析工作台 (analysis)**

- Plot one Y column against an X column, or against the row number, for several samples at once with Plotly: overlaid or as a waterfall with adjustable spacing, drawn as lines, markers or both.
- Axis-label presets for XRD, FTIR, Raman, UV-Vis, TGA, DSC, stress-strain, cyclic voltammetry and impedance (Nyquist) plots.
- Curve operations: Savitzky-Golay smoothing, min-max normalization, subtracting a straight baseline through the first and last points, and the first derivative. Reset returns to the imported data.
- Fixed axis ranges, reversed and logarithmic axes, color cycling, a legend toggle and per-chart legend names.

**AI 智能分析 (AI chat)**

- A chat panel for OpenAI-compatible APIs, with provider presets or a custom base URL, using your own API key. It does not work in this snapshot; see [Known issues](#known-issues).

Also:

- Save the whole session as a `.nbp` project file and restore it later (sidebar: 工程存档与恢复).
- Optional export to OriginPro on Windows; see [Optional: OriginPro export](#optional-originpro-export).
- Example data in `sample_data/sample_data.csv`.

Classic has no license activation, no update checker and no installer.

## Requirements

- Python 3 with `pip`. The repository pins neither a Python version nor package versions, so `pip install -r requirements.txt` installs the latest compatible releases.
- Last checked on Windows 11 in October 2026 with Python 3.13, Streamlit 1.66.1, pandas 3.1.0 and NumPy 2.5.4. That Streamlit version logs deprecation warnings for some functions the app uses (`use_container_width`, `st.components.v1.html`). If a later Streamlit release breaks the app, install the checked one with `pip install "streamlit==1.66.1"`.

## Quick start

Start the app from the repository root: it reads `assets/style.css`, `.streamlit/config.toml` and `rules/` relative to the current folder.

Windows (PowerShell):

```powershell
git clone https://github.com/ptjworks/NebulaLab-Classic.git
cd NebulaLab-Classic
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

If PowerShell refuses to run `Activate.ps1`, skip that line and call the environment's Python directly:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

macOS / Linux (the standard equivalent; only the Windows steps were checked):

```bash
git clone https://github.com/ptjworks/NebulaLab-Classic.git
cd NebulaLab-Classic
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The first time you run Streamlit it may ask for an email address in the terminal; leave it blank and press Enter. Streamlit then opens the app in your browser, by default at <http://localhost:8501>. To try it, upload `sample_data/sample_data.csv` on the 数据加载 page, click 🚀 确认配置并导入所有数据 (confirm and import), then open 分析工作台.

## Where your data goes

- **Uploaded files stay in memory.** Streamlit runs a local server, and the app keeps uploaded files in that server's memory for your browser session. It does not save them to disk (OriginPro export only writes the selected curves to a temporary file, which it deletes afterwards), and it sends them nowhere unless you use the AI panel. Closing the tab loses unsaved work; save a `.nbp` project to keep it.
- **The app writes these files** in the folder you started it from:
  - `rules/<name>.nbr` when you save a rule;
  - `ai_config.json` when you click 💾 保存配置 in the AI settings. It holds the provider, base URL, model and your **API key in plain text**;
  - `chat_history.json` for AI conversations.

  `ai_config.json` and `chat_history.json` are listed in `.gitignore`. Do not commit or share them.
- **`.nbp` project files are Python pickle files.** Opening one can run code stored in it, so only open project files you made yourself or fully trust.
- **Network access:**
  - The AI panel connects only to the base URL you enter; 🔄 刷新模型 (refresh models) fetches the model list from it. Chat messages are built to carry, with the default options, the selected samples' names, row counts and column names plus the conversation, and ticking 📄 原始数据 adds the first 20 rows of each selected sample. Because of the bug under [Known issues](#known-issues), no message is actually sent.
  - The stylesheet loads the Inter and JetBrains Mono fonts from Google Fonts.
  - Streamlit's defaults apply: it sends usage statistics to Streamlit, and it listens on all network interfaces, so other computers on your network can open the app at the "Network URL" it prints. The included `.streamlit/config.toml` changes neither. To keep the app on this computer and stop the statistics:

    ```bash
    streamlit run app.py --server.address localhost --browser.gatherUsageStats false
    ```

## Optional: OriginPro export

The 🚀 发送至 OriginPro button (analysis page, 导出发送 panel) sends the selected curves to OriginPro and plots them there. It needs Windows, a local OriginPro installation, and Origin's `originpro` Python package in the same environment:

```bash
pip install "originpro>=1.1.15"
```

Without the package the button only reports that it is missing; the rest of the app works. Graph templates (`.otp` or `.otpu`) placed in `origin_templates/` appear in the template list; `热重.otpu` is included.

## Known issues

As of October 2026 (the code is unchanged since May 2026):

- **AI chat does not work.** Sending a message shows `AI Error: AIAnalyzer.__init__() got an unexpected keyword argument 'model'`, because `modules/pages/copilot_page.py` passes `model=` while `AIAnalyzer` in `modules/ai_agent.py` expects `model_name=`. The 🖼️ 图表快照 (chart snapshot) option is not connected to anything.
- **✂️ 按视图裁剪点 (crop to view) fails.** It raises an error and leaves that curve broken until you click 🔄 重置当前数据 (reset).
- **The built-in manual is partly out of date.** 📘 使用说明书 was written for an earlier desktop build and describes things Classic does not have, such as a gallery view and a standalone window.

## Repository layout

| Path | Contents |
| --- | --- |
| `app.py` | Streamlit entry point |
| `modules/` | Import, plotting, AI, OriginPro and project code; `modules/pages/` holds the three pages |
| `rules/` | Saved import rules (`.nbr`) |
| `origin_templates/` | OriginPro graph templates |
| `sample_data/` | Example CSV file |
| `assets/` | Stylesheet and images |
| `tests/` | Checks that licensing and update code stays out of Classic; run with `pip install pytest`, then `python -m pytest` |

## License

Nebula Lab Classic is released under the GNU Affero General Public License v3.0. See [`LICENSE`](LICENSE).
