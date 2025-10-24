from bs4 import BeautifulSoup
import requests
import re
import streamlit as st
import json
import time
import os

HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "https://google.com",
            "Connection": "keep-alive",
        }
PREFIX = "https://www.examtopics.com/discussions/"

def load_json(json_path):
    if not os.path.exists(json_path):
        return {}
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}
        
def save_json(file, json_path):
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(file, f, ensure_ascii=False, indent=2)

def get_exam_category(exam_code):
    response = requests.get(f"https://www.examtopics.com/search/?query={exam_code}", headers=HEADERS, allow_redirects=True)
    final_url = response.url
    if "/exams/" in final_url:
        parts = final_url.strip("/").split("/")
        if len(parts) >= 2:
            return parts[-2]  # category is second-to-last
        return None

    soup = BeautifulSoup(response.content, "html.parser")
    exam_list = soup.find_all("ul", class_="exam-list-font")
    if len(exam_list) < 1:
        return None

    for exam in exam_list:
        for a in exam.find_all("a", href=True):
            if a.text.strip().startswith(exam_code):
                href = a['href']
                # Split the path and get the second-to-last segment
                parts = href.strip("/").split("/")
                if len(parts) >= 2:
                    return parts[-2]
    
    return None

def get_question_links(exam_code, progress, json_path):
    progress.progress(0, text=f"Starting link extraction...")
    category = get_exam_category(exam_code)

    if not category:
        raise ValueError(f"Exam code {exam_code} not found.")

    url = f"{PREFIX}{category}/"
    # Get the first page to find number of pages
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.content, "html.parser")

    # Find number of pages
    page_indicator = soup.find("span", class_="discussion-list-page-indicator")
    if not page_indicator:
        raise ValueError("Page indicator not found. Page structure may have changed.")
    strong_tags = page_indicator.find_all("strong")
    num_pages = int(strong_tags[1].text)

    links_json = load_json(json_path)
    if links_json:
        question_links = links_json.get("links", [])
        page_num = links_json.get("page_num", 1)
        status = links_json.get("status", "in progress")
        if status == "complete":
            progress.progress(1, text=f"Links extracted from file")
            return question_links
    else:
        question_links = []
        page_num = 1
        status = "in progress"

    # Loop through all pages
    for i in range(page_num, num_pages + 1):
        progress.progress((i) / num_pages, text=f"Extracting question links - page {i} of {num_pages}...")
        page_url = url + f"{i}/"

        page_response = requests.get(page_url, headers=HEADERS)
        soup = BeautifulSoup(page_response.content, "html.parser")
        titles = soup.find_all("div", class_="dicussion-title-container")
        for title in titles:
            if title.text:
                title_text = title.text.strip()
                if f"Exam {exam_code}" in title_text:
                    a_tag = title.find("a")
                    if a_tag and "href" in a_tag.attrs:
                        question_links.append(a_tag["href"])
    sorted_links = sorted(question_links, key=lambda link: int(re.search(r'question-(\d+)', link).group(1)))
    question_links_obj = {"page_num": i, "status": "complete", "links": sorted_links}
    save_json(question_links_obj, json_path)
    return sorted_links

def scrape_page(link):
    question_object = {}

    try:
        response = requests.get(link, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
    except Exception as e:
        return {
            "question": "",
            "answers": [],
            "comments": [],
            "most_voted": None,
            "link": link,
            "question_number": "unknown",
            "error": f"Request or parsing failed: {e}"
        }

    question_number_match = re.search(r"question-(\d+)", link)
    question_number = question_number_match.group(1) if question_number_match else "unknown"

    # Extract question
    question = ""
    try:
        question_div = soup.find("div", class_="question-body")
        question_content = question_div.find("p", class_="card-text") if question_div else None
        if question_content:
            question = question_content.decode_contents().strip()
    except Exception:
        pass

    # Extract most voted answers
    most_voted = None
    try:
        voted_answers = soup.find("div", class_="voted-answers-tally")
        if voted_answers:
            script_content = voted_answers.find("script")
            if script_content and script_content.string:
                voted_json = json.loads(script_content.string)
                most_voted_object = next((item for item in voted_json if item.get('is_most_voted')), None)
                if most_voted_object:
                    most_voted = most_voted_object.get("voted_answers", None)
    except Exception:
        pass

    # Extract answer options
    answers = []
    try:
        if question_div:
            answers_div = question_div.find("div", class_="question-choices-container")
            if answers_div:
                answer_options = answers_div.find_all("li")
                if answer_options:
                    answers = [re.sub(r'\s+', ' ', answer_option.text).strip() for answer_option in answer_options]
    except Exception:
        pass

    # Extract comments and replies
    comments = []
    try:
        discussion_div = soup.find("div", class_="discussion-container")
        comment_divs = discussion_div.find_all("div", class_="comment-container", recursive=False) if discussion_div else []
        for comment_div in comment_divs:
            comment = {}
            try:
                comment_content_div = comment_div.find("div", class_="comment-content")
                comment_content = comment_content_div.text.strip() if comment_content_div else ""
            except Exception:
                comment_content = ""

            try:
                comment_selected_answer = comment_div.find("div", class_="comment-selected-answers")
                selected_answer = comment_selected_answer.find("span").text.strip() if comment_selected_answer else ""
            except Exception:
                selected_answer = ""

            replies = []
            try:
                comment_replies_div = comment_div.find("div", class_="comment-replies")
                if comment_replies_div:
                    reply_divs = comment_replies_div.find_all("div", class_="comment-container")
                    for reply in reply_divs:
                        try:
                            reply_content = reply.find("div", class_="comment-content").text.strip()
                        except Exception:
                            reply_content = ""
                        replies.append(reply_content)
            except Exception:
                pass

            comment["content"] = comment_content
            comment["selected_answer"] = selected_answer
            comment["replies"] = replies

            comments.append(comment)
    except Exception:
        pass

    question_object["question"] = question
    question_object["answers"] = answers
    question_object["comments"] = comments
    question_object["question_number"] = question_number
    question_object["link"] = link
    question_object["most_voted"] = most_voted
    question_object["error"] = None

    return question_object

        
def scrape_questions(question_links, json_path, progress, rapid_scraping=False):
    questions_obj = load_json(json_path)
    if questions_obj:
        questions = questions_obj.get("questions", [])
    else:
        questions = []
    prefix = "https://www.examtopics.com"
    questions_num = len(question_links)
    error_string = ""
    for i, link in enumerate(question_links):
        question_number_match = re.search(r"question-(\d+)", link)
        question_number = question_number_match.group(1) if question_number_match else "unknown"
        if question_number in [q["question_number"] for q in questions]:
            progress.progress((i+1)/(questions_num), text=f"{i+1}/{questions_num} - Skipping {prefix+link}")
            continue
        progress.progress((i+1)/(questions_num), text=f"{i+1}/{questions_num} - Scraping {prefix+link}")
        question_object = scrape_page(prefix+link)
        if question_object["error"]:
            error_string = (f"Error: {question_object['error']}")
            break
        questions.append(question_object)
        if not rapid_scraping:
            time.sleep(15)
    questions.sort(key=lambda x: x["question_number"])
    status = "complete" if len(questions) == questions_num else "in progress"
    questions_obj = {"status": status, "error": error_string, "questions": questions}
    save_json(questions_obj, json_path)
    return questions_obj
    

def load_json_from_github(exam_code):
    url = f"https://raw.githubusercontent.com/17Andri17/ExamTopics-Question-Viewer/refs/heads/main/data/{exam_code}.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        questions_obj = json.loads(response.text)
        questions = questions_obj.get("questions", [])
        return questions, ""
    except requests.RequestException as e:
        return [], f"Failed to load file from GitHub for exam {exam_code}. It probably does not exist."