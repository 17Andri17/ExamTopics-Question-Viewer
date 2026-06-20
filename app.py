import streamlit as st
import os
import random
from streamlit_modal import Modal
import streamlit.components.v1 as components
from scraper import get_question_links, scrape_questions, load_json
from pdf import generate_pdf
from ui_utils import render_question_header, render_question_body, render_answers, render_discussion, render_highlight_toggle
from utils import annotate_topics, order_questions, get_topics, search_questions, plain_text
from versions import (
    version_path, links_path, local_versions, next_version,
    version_label, stamp_version, github_versions, load_from_github,
)

if os.environ.get("HOSTNAME"):
    IS_DEPLOYED = os.environ["HOSTNAME"] == "streamlit"
else:
    IS_DEPLOYED = False

def get_exam_questions(exam_code, version, progress, rapid_scraping=False):
    if IS_DEPLOYED:
        questions, err = load_from_github(exam_code, version)
        if questions:
            progress.progress(100, text="Loaded from GitHub")
        return questions, err

    questions_path = version_path(exam_code, version)
    links_file = links_path(exam_code, version)

    # A finished snapshot just gets read back from disk.
    if os.path.exists(questions_path):
        questions_JSON = load_json(questions_path)
        if questions_JSON.get("status") == "complete":
            progress.progress(100, text="Extracted questions from file")
            return questions_JSON.get("questions", []), ""

    # Otherwise scrape it (initial scrape of v1, or a new/continuing version).
    try:
        links = get_question_links(exam_code, progress, links_file)
    except Exception as e:
        return [], str(e)

    if len(links) == 0:
        return [], "No questions found. Please check the exam code and try again."

    questions_obj = scrape_questions(links, questions_path, progress, rapid_scraping)
    questions = questions_obj.get("questions", [])
    stamp_version(exam_code, version)
    if questions_obj.get("error", "") != "":
        return questions, f"Error occurred while scraping questions. Your connection may be slow or the website may have limited your rate. You can still see {len(questions)} questions. Try again later by refreshing the page."
    return questions, ""
    
def clear_text():
    st.session_state.input = st.session_state.question_number_input_text
    st.session_state.question_number_input_text = ""

st.set_page_config(page_title="ExamTopics Viewer", layout="wide")

css_style = """
            <style>
            .stMainBlockContainer{
                padding-top: 16px;
            }
            </style>
            <div id="top"></div>
        """
st.markdown(css_style, unsafe_allow_html=True)

st.session_state["rapid_scraping"] = st.session_state.get("rapid_scraping", False)
st.session_state["show_discussion"] = st.session_state.get("show_discussion", True)
st.session_state["default_highlight"] = st.session_state.get("default_highlight", False)

st.title("ExamTopics Question Viewer")

top_col1, top_options_btn_col, top_col2 = st.columns((15,1,4))
code_col, options_btn_col = st.columns((15, 1))

if "questions" not in st.session_state:
    with code_col:
        exam_code = st.text_input("Enter Exam Code (e.g., CAD):", placeholder="Enter Exam Code (e.g., CAD):", label_visibility="collapsed")
    with options_btn_col:
        open_modal = st.button("⚙️", key="gear_button", help="Open Settings")
else:
    with top_col1:
        exam_code = st.text_input("Enter Exam Code (e.g., CAD):", placeholder="Enter Exam Code (e.g., CAD):", label_visibility="collapsed")
    with top_options_btn_col:
        open_modal = st.button("⚙️", key="gear_button", help="Open Settings")

modal = Modal(
    title="Settings",
    key="demo-modal",
    padding=22,
    max_width=480
)
if open_modal:
    modal.open()

if modal.is_open():
    with modal.container():
        st.markdown("### 🔧 Scraper Settings")

        rapid_scraping = st.toggle(
            "Enable Rapid Scraping",
            help="Faster scraping, but may trigger rate-limiting from the website."
        )
        
        st.session_state["rapid_scraping"] = rapid_scraping

        st.markdown("""
        <hr style='margin-top:10px;margin-bottom:10px'/>
        """, unsafe_allow_html=True)

        st.markdown("### 🎨 Display Preferences")

        default_highlight = st.toggle("Highlight correct answers by default", value=st.session_state.get("default_highlight", False), help="Highlight correct answers by default")
        show_discussion = st.toggle("Show discussion", value=st.session_state.get("show_discussion", True), help="Show discussion by default")
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.session_state["show_discussion"] = show_discussion
        st.session_state["default_highlight"] = default_highlight
        if default_highlight:
            st.session_state["highlight"] = True

if exam_code:
    # --- Discover the available versions for this exam ---
    if IS_DEPLOYED:
        if st.session_state.get("versions_exam") != exam_code:
            st.session_state.versions_list = github_versions(exam_code) or [1]
            st.session_state.versions_exam = exam_code
        versions_list = st.session_state.versions_list
    else:
        versions_list = local_versions(exam_code) or [1]

    # A re-scrape queues a switch to a new (not-yet-existing) version.
    pending_version = st.session_state.pop("pending_version", None)
    if pending_version is not None:
        if pending_version not in versions_list:
            versions_list = sorted(set(versions_list) | {pending_version})
        st.session_state.version_select = pending_version

    latest_version = max(versions_list)

    # Reset the selection to the newest version when the exam changes.
    if st.session_state.get("version_exam") != exam_code:
        st.session_state.version_exam = exam_code
        st.session_state.version_select = latest_version

    version_options = sorted(versions_list, reverse=True)
    if st.session_state.get("version_select") not in version_options:
        st.session_state.version_select = latest_version

    # --- Version selector + re-scrape control ---
    ver_col, rescrape_col = st.columns((4, 1))
    with ver_col:
        if len(version_options) > 1:
            selected_version = st.selectbox(
                "Version",
                version_options,
                format_func=lambda v: version_label(exam_code, v, latest_version),
                label_visibility="collapsed",
                key="version_select",
            )
        else:
            selected_version = latest_version
    with rescrape_col:
        rescrape_help = (
            "Fetch this exam again to pick up new questions and answers. "
            "The result is saved as a new version; older versions are kept."
            if not IS_DEPLOYED else
            "Re-scraping is only available when running the app locally."
        )
        rescrape_clicked = st.button("🔄 Re-scrape", use_container_width=True, disabled=IS_DEPLOYED, help=rescrape_help)

    if rescrape_clicked and not IS_DEPLOYED:
        st.session_state.pending_version = next_version(exam_code)
        st.session_state.force_rescrape = True
        st.rerun()

    # --- Load the selected version (scraping it if it doesn't exist yet) ---
    force_load = st.session_state.pop("force_rescrape", False)
    need_load = (
        force_load
        or st.session_state.get("loaded_exam_code") != exam_code
        or st.session_state.get("loaded_version") != selected_version
    )
    if need_load:
        with st.spinner("Fetching questions..."):
            progress = st.progress(0, text="Starting questions extraction...")
            questions, err = get_exam_questions(exam_code, selected_version, progress, rapid_scraping=st.session_state["rapid_scraping"])
            questions = order_questions(annotate_topics(questions))
            st.session_state.error = err
            st.session_state.questions = questions
            st.session_state.loaded_exam_code = exam_code
            st.session_state.loaded_version = selected_version
            st.session_state.just_loaded = True
            # Reset the view for the freshly loaded set of questions.
            st.session_state.question_index = 0
            st.session_state.text_query = ""
            st.session_state.pop("active_topic", None)
            st.session_state.pop("topic_select", None)
            if len(questions) > 0:
                st.session_state.active_topic = questions[0]["topic"]
                st.session_state.question = questions[0]
            else:
                st.warning("No questions found.")
            st.rerun()
    else:
        questions = st.session_state.questions
    with top_col2:
        export_button = st.button("Export Questions to PDF", use_container_width=True)
    if export_button:
        progress_pdf = st.progress(0, text="Starting PDF generation...")
        questions = st.session_state["questions"]
        try:
            pdf_data = generate_pdf(questions, progress_pdf)
            st.success("PDF generation complete.")
            version_suffix = f"_v{selected_version}" if selected_version > 1 else ""
            st.download_button(
                label="Download PDF",
                data=pdf_data,
                file_name=f"{exam_code}{version_suffix}_questions.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"❌ Failed to generate PDF. Reason: {str(e)}. It may be due to a connection issue. Please try again.")

    if st.session_state.get("just_loaded"):
        if st.session_state.get("error", "") != "":
            st.error(st.session_state.get("error", ""))
        else:
            loaded_v = st.session_state.get("loaded_version", 1)
            version_note = f" (version {loaded_v})" if len(version_options) > 1 or loaded_v > 1 else ""
            st.success(f"Loaded {len(st.session_state.questions)} questions{version_note}.")
        st.session_state.just_loaded = False

    topics = get_topics(questions)
    multi_topic = len(topics) > 1

    # Apply a pending jump from a text-search result. This must run before the
    # topic selectbox is created so we can point it at the target topic.
    pending = st.session_state.pop("pending_jump", None)
    if pending:
        target_topic, target_link = pending
        if multi_topic:
            st.session_state.topic_select = target_topic
        st.session_state.active_topic = target_topic
        target_questions = [q for q in questions if q.get("topic") == target_topic]
        st.session_state.question_index = next(
            (i for i, q in enumerate(target_questions) if q.get("link") == target_link), 0
        )

    if multi_topic:
        col_search, col_topic, col_prev, col_rand, col_next = st.columns((3, 2, 1, 1, 1))
    else:
        col_search, col_prev, col_rand, col_next = st.columns((5, 1, 1, 1))

    with col_search:
        question_number_input = st.text_input("Search question", key="question_number_input_text", on_change=clear_text, placeholder="Search by question number or text", label_visibility="collapsed")

    if multi_topic:
        with col_topic:
            current_topic = st.selectbox(
                "Topic",
                topics,
                format_func=lambda t: f"Topic {t}",
                label_visibility="collapsed",
                key="topic_select",
            )
    else:
        current_topic = topics[0] if topics else "1"

    # Reset to the first question whenever the active topic changes.
    if st.session_state.get("active_topic") != current_topic:
        st.session_state.active_topic = current_topic
        st.session_state.question_index = 0

    topic_questions = [q for q in questions if q.get("topic") == current_topic]

    with col_prev:
        previous_button = st.button("Previous", use_container_width=True)
    with col_rand:
        random_button = st.button("Random", use_container_width=True)
    with col_next:
        next_button = st.button("Next", use_container_width=True)

    index = st.session_state.get("question_index", 0)
    index = max(0, min(index, len(topic_questions) - 1)) if topic_questions else 0

    if random_button and topic_questions:
        index = random.randrange(len(topic_questions))
        st.session_state.highlight = False
    elif next_button and topic_questions:
        index = min(index + 1, len(topic_questions) - 1)
        st.session_state.highlight = False
    elif previous_button and topic_questions:
        index = max(index - 1, 0)
        st.session_state.highlight = False
    elif st.session_state.get("input", "") != "":
        query = st.session_state.get("input", "").strip()
        st.session_state.input = ""
        if query.isdigit():
            match_index = next((i for i, q in enumerate(topic_questions) if str(q.get("question_number")) == query), None)
            if match_index is not None:
                index = match_index
                st.session_state.highlight = False
                st.session_state.text_query = ""
            else:
                scope = f" in Topic {current_topic}" if multi_topic else ""
                st.warning(f"No question found with that number{scope}.")
        else:
            # Non-numeric query: search question and answer text across topics.
            st.session_state.text_query = query

    st.session_state.question_index = index
    selected_question = topic_questions[index] if topic_questions else None

    if not st.session_state.get("highlight"):
        st.session_state.highlight = False

    # Text-search results (shown above the current question, across all topics).
    text_query = st.session_state.get("text_query", "")
    if text_query:
        results = search_questions(questions, text_query)
        header_col, clear_col = st.columns((6, 1))
        with header_col:
            st.markdown(f"**{len(results)} result(s) for “{text_query}”:**")
        with clear_col:
            if st.button("Clear", use_container_width=True):
                st.session_state.text_query = ""
                st.rerun()
        if not results:
            st.info("No questions matched your search.")
        for q in results[:50]:
            label_topic = f"Topic {q['topic']} · " if multi_topic else ""
            snippet = plain_text(q.get("question", ""))[:120]
            if st.button(f"{label_topic}Question {q['question_number']}: {snippet}…", key=f"result_{q['link']}", use_container_width=True):
                st.session_state.pending_jump = (q["topic"], q["link"])
                st.session_state.text_query = ""
                st.rerun()
        if len(results) > 50:
            st.caption(f"Showing the first 50 of {len(results)} results.")
        st.markdown("---")

    if selected_question:
        st.session_state.question = selected_question
        render_question_header(selected_question, show_topic=multi_topic)

        render_question_body(selected_question, "https://www.examtopics.com")

        higlight_flag = st.session_state.get("highlight", False) or st.session_state.get("default_highlight", False)
        render_answers(selected_question, higlight_flag)
        if not st.session_state.get("default_highlight"):
            render_highlight_toggle(selected_question)

        if st.session_state.get("show_discussion"):
            st.markdown("---")
            st.markdown("### Discussion:")
            render_discussion(selected_question.get("comments", []))

