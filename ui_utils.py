import streamlit as st
from bs4 import BeautifulSoup

def fix_image_paths(html_text, prefix):
    soup = BeautifulSoup(html_text, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src.startswith("http"):
            img["src"] = prefix + src
    return str(soup)

def render_question_header(question, show_topic=False):
    title = f"Question {question['question_number']}"
    if show_topic:
        title = f"Topic {question.get('topic', '1')} · {title}"
    st.markdown(
        f"""
        <h2 style="display: flex; align-items: center; gap: 20px;">
            {title}
            <a href="{question['link']}" target="_blank" class="exam-link" style="
                color: #1f77b4;
                text-decoration: none;
                font-size: 16px;
            ">🔗 View on ExamTopics</a>
        </h2>
        """ + """
        <style>
            @media (max-width: 600px) {
                .exam-link {
                    display: none;
                }
            }
        </style>
        """,
        unsafe_allow_html=True
    )

def render_question_body(question, image_prefix):
    question_html = fix_image_paths(question["question"], image_prefix)
    st.markdown(f"**{question_html}**", unsafe_allow_html=True)

def render_answers(question, highlight):
    for a in question.get("answers", []):
        background_color = "transparent"
        if question["most_voted"]:
            if highlight and a[0] in question["most_voted"]:
                background_color = "lightgreen"
        st.markdown(f'<div style="background-color:{background_color}; padding:10px; margin:2px; border-radius:5px;">{a}</div>', unsafe_allow_html=True)

def render_highlight_toggle(question):
    st.markdown("")
    toggle_label = "Hide Most Voted Answers" if st.session_state.highlight else "Highlight Most Voted Answers"
    
    if len(question.get("answers", [])) >= 2:
        if st.button(toggle_label):
            if question.get("most_voted"):
                st.session_state.highlight = not st.session_state.highlight
                st.rerun()
            else:
                st.warning("No most voted answer info available.")

def render_discussion(comments):
    if not comments:
        st.info("No discussion available.")
        return

    st.markdown("""
    <style>
        .comment-box {
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 10px 15px;
            margin-bottom: 16px;
            background-color: #fdfdfd;
        }
        .comment-header {
            font-weight: bold;
            margin-bottom: 6px;
            font-size: 1.05em;
        }
        .selected-label {
            color: #2e7d32;
            font-weight: bold;
            margin-left: 10px;
            font-size: 0.9em;
        }
        .reply {
            margin-left: 12px;
            margin-top: 6px;
            padding: 6px 10px;
            background-color: #f5f5f5;
            border-left: 3px solid #ccc;
            border-radius: 4px;
            font-size: 0.9em;
        }
    </style>
    """, unsafe_allow_html=True)

    for idx, comment in enumerate(comments, 1):
        header = f"💬 Comment {idx}"
        if comment.get("selected_answer"):
            header += f'<span class="selected-label">🟩 Selected Answer: {comment["selected_answer"]}</span>'

        replies_html = ""
        for reply in comment.get("replies", []):
            replies_html += f'<div class="reply">{reply}</div>'

        comment_html = f"""
        <div class="comment-box">
            <div class="comment-header">{header}</div>
            <div>{comment['content']}</div>
            {replies_html}</div>
        """
        st.markdown(comment_html, unsafe_allow_html=True)
