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

import re
import requests
from bs4 import BeautifulSoup

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

    # Load progress if exists
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

    # Loop through remaining pages
    for i in range(page_num, num_pages + 1):
        progress.progress(i / num_pages, text=f"Extracting question links - page {i} of {num_pages}...")
        page_url = url + f"{i}/"

        try:
            page_response = requests.get(page_url, headers=HEADERS)
            page_response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching page {i}: {e}")
            break  # stop on network error to avoid corrupting progress

        soup = BeautifulSoup(page_response.content, "html.parser")
        titles = soup.find_all("div", class_="dicussion-title-container")

        for title in titles:
            if title.text:
                title_text = title.text.strip()
                if f"Exam {exam_code}" in title_text:
                    a_tag = title.find("a")
                    if a_tag and "href" in a_tag.attrs:
                        href = a_tag["href"]
                        if href not in question_links:
                            question_links.append(href)

        # Save progress after each page
        temp_obj = {
            "page_num": i + 1,  # next page to start from
            "status": "in progress",
            "links": question_links,
        }
        save_json(temp_obj, json_path)

    # Separate links: those with question numbers and those without
    numbered_links = []
    non_numbered_links = []

    for link in question_links:
        match = re.search(r'question-(\d+)', link)
        if match:
            numbered_links.append((int(match.group(1)), link))
        else:
            non_numbered_links.append(link)

    # Sort only numbered links
    numbered_links.sort(key=lambda x: x[0])
    sorted_links = [link for _, link in numbered_links] + non_numbered_links

    final_obj = {
        "page_num": num_pages + 1,
        "status": "complete",
        "links": sorted_links,
    }
    save_json(final_obj, json_path)
    progress.progress(1, text="All links extracted and saved.")
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
    if question_number_match:
        question_number = question_number_match.group(1)
    else:
        # Try to find it inside the page
        question_number = "unknown"
        try:
            header = soup.find("div", class_="question-discussion-header")
            if header:
                # Look for text like "Question #: 1"
                header_text = header.get_text(strip=True)
                number_in_text = re.search(r"Question\s*#:\s*(\d+)", header_text)
                if number_in_text:
                    question_number = number_in_text.group(1)
        except Exception as e:
            print(f"⚠️ Could not extract question number from page: {e}")

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
    # Load saved progress
    questions_obj = load_json(json_path)
    if questions_obj:
        questions = questions_obj.get("questions", [])
        status = questions_obj.get("status", "in progress")
        error_string = questions_obj.get("error", "")
    else:
        questions = []
        status = "in progress"
        error_string = ""

    prefix = "https://www.examtopics.com"
    questions_num = len(question_links)

    # Track already-scraped links (safe even if no question number)
    scraped_links = {q.get("link") for q in questions if q.get("link")}

    # Determine where to resume
    start_index = 0
    for idx, link in enumerate(question_links):
        full_link = prefix + link
        if full_link not in scraped_links:
            start_index = idx
            break
    else:
        # All links done
        progress.progress(1, text="All questions already scraped.")
        return questions_obj

    # Loop through remaining links
    for i in range(start_index, questions_num):
        link = question_links[i]
        full_link = prefix + link

        # Skip already-scraped links (extra safety)
        if full_link in scraped_links:
            progress.progress((i + 1) / questions_num, text=f"{i + 1}/{questions_num} - Skipping {full_link}")
            continue

        progress.progress((i + 1) / questions_num, text=f"{i + 1}/{questions_num} - Scraping {full_link}")

        # Scrape the page
        question_object = scrape_page(full_link)

        # Handle errors gracefully
        if question_object.get("error"):
            error_string = f"Error: {question_object['error']}"
            save_json({
                "status": "in progress",
                "error": error_string,
                "questions": questions
            }, json_path)
            break

        # Ensure the link and question_number are stored for future resumes
        question_object["link"] = full_link

        questions.append(question_object)
        scraped_links.add(full_link)

        # Save after each question ✅
        save_json({
            "status": "in progress",
            "error": error_string,
            "questions": questions
        }, json_path)

        if not rapid_scraping:
            time.sleep(12)

    # Sort only questions with valid numeric numbers; keep others’ order
    numbered = [q for q in questions if str(q.get("question_number", "")).isdigit()]
    non_numbered = [q for q in questions if not str(q.get("question_number", "")).isdigit()]

    numbered.sort(key=lambda x: int(x["question_number"]))
    questions_sorted = numbered + non_numbered

    status = "complete" if len(questions_sorted) == questions_num and not error_string else "in progress"

    final_obj = {
        "status": status,
        "error": error_string,
        "questions": questions_sorted
    }
    save_json(final_obj, json_path)

    progress.progress(1, text="Scraping complete." if status == "complete" else "Progress saved.")
    return final_obj
    

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