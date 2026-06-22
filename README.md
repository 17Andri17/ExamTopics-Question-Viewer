# 📘 ExamTopics Question Viewer

🔗 Online App: https://examtopics-question-viewer.streamlit.app/
> **Note:** The **online version** of this app only supports viewing exams that were scraped earlier.  
> Due to limited free hosting storage, **live scraping is not available online**.  
> For full functionality, including scraping new exams and offline access, please **clone and run the app locally**.

## 💡 What is This?
A **Streamlit** web app that lets you view and export exam questions from [ExamTopics.com](https://www.examtopics.com) based on a specific exam code (e.g., `CAD`, `CSA`, `CIS-ITSM`). It scrapes discussion pages, shows most-voted answers, supports intuitive question navigation, and enables exporting everything to a well-formatted PDF for offline review.

## 🔧 Features

✅ Scrape questions and answers by exam code <br>
✅ View most-voted answers with optional highlighting <br>
✅ Read user discussion and selected answers <br>
✅ Browse by topic — exams that reuse question numbers across multiple topics show a topic selector so every question is reachable <br>
✅ Navigate: next, previous, random, search by number, or search by question/answer text <br>
✅ Re-scrape an exam to pick up new questions and answers, with full version history (older versions are kept and can be re-opened) <br>
✅ Export questions and answers to a formatted PDF <br>
✅ Caching via local JSON to avoid re-scraping <br>
✅ Built-in error handling for rate limits and offline fallback

---

## 🚀 Getting Started (Offline / Full Version)

### 1. Clone the Repository

```bash
git clone https://github.com/{your-username}/ExamTopics-Question-Viewer.git
cd ExamTopics-Question-Viewer
```

### 2. Create a Virtual Environment & Install Dependencies

```bash
python -m venv {venv-name}
source {venv-name}/bin/activate  # On Windows: {venv-name}\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the App
```bash
python -m streamlit run app.py
```

## 🔁 Re-scraping & Versions

Exam content on ExamTopics changes over time — new questions get added and
discussions gain new most-voted answers. Use the **🔄 Re-scrape** button to run
the whole scraping procedure again. The result is saved as a **new version**
instead of overwriting the existing data:

- Existing exams (anything scraped before this feature) are treated as
  **Version 1** — no version suffix means version 1.
- Each re-scrape is written to `data/{exam_code}_v{n}.json`, leaving older
  snapshots untouched.
- The app always opens the **newest** version by default. When more than one
  version exists, a **version selector** appears so you can go back and view any
  previous version (read-only).
- If a re-scrape is interrupted (e.g. by rate-limiting), pressing **Re-scrape**
  again resumes the unfinished version rather than starting another one.

> Re-scraping runs the same rate-limited requests as the initial scrape, so it
> can take a while for large exams. It is only available when running locally;
> the online version is read-only.

## 📤 Exporting to PDF
Once questions are loaded, click Export Questions to PDF. The PDF includes:

- Questions and all answers
- Information about most-voted answers
- Comments with selected answer labels
- Clean formatting for offline study

## 🛑 Rate Limiting Notice

ExamTopics enforces **aggressive rate-limiting**, so by default, the app waits **5 seconds between requests** to reduce the risk of being blocked.

If an error occurs while scraping, it’s likely because your IP address has been temporarily **rate-limited or blocked**. This block can last **several hours to days**, depending on usage.  
However, you’ll still be able to view any questions you’ve previously scraped and saved locally. Additionally, you can sometimes continue to fetch more questions, but typically you'll be allowed to access only a few pages before hitting the limit again.

### ⚡ Rapid Scraper Option (Use with Caution)

In the app’s **settings**, you can enable a **“Rapid Scraper”** mode that disables the 5-second delay.  
This allows for much faster scraping, but it **greatly increases the chance of hitting rate limits or getting blocked**.


To bypass rate-limiting more quickly, you can try changing your IP address. Here are some easy ways:

- 🔌 **Restart your router** – may assign a new IP
- 📱 **Use mobile data** or tethering
- 🔄 **Switch networks** (e.g., to a public Wi-Fi)
- 🌐 **Try a VPN** with different server locations

## 📚 Pre-Scraped Exams
Some exams have already been scraped and saved locally in the data/ directory. These are the best way to use the app, since loading them avoids rate limits and delays entirely. Instead of waiting for slow scraping or risking being blocked, you can instantly load these pre-saved questions and explore them with full functionality.

To see the full list of available pre-scraped exams, check the data/ folder in the project directory — each exam has its own .json file named after its exam code (e.g., CAD.json)
