from reportlab.lib.pagesizes import letter
from reportlab.lib import utils
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import requests
from io import BytesIO
from bs4 import BeautifulSoup

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

def fetch_image_from_url(url):
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=5)
        if response.status_code == 200:
            return ImageReader(BytesIO(response.content))
    except Exception as e:
        print(f"Failed to fetch image {url}: {e}")
    return None

def wrap_text(text, max_width, font, font_size, new_line=False):
    from reportlab.pdfgen import canvas
    from io import BytesIO
    c = canvas.Canvas(BytesIO())
    c.setFont(font, font_size)

    lines = []
    for paragraph in text.split('\n'):
        words = paragraph.split()
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            if c.stringWidth(test_line, font, font_size) <= max_width:
                current_line = test_line
            else:
                # If the word itself is too long, split it
                if c.stringWidth(word, font, font_size) > max_width:
                    if current_line:
                        lines.append(current_line)
                        current_line = ""
                    # Break the word into chunks
                    chunk = ""
                    for char in word:
                        if c.stringWidth(chunk + char, font, font_size) <= max_width:
                            chunk += char
                        else:
                            lines.append(chunk)
                            chunk = char
                    if chunk:
                        current_line = chunk
                else:
                    lines.append(current_line)
                    current_line = word

        if current_line:
            lines.append(current_line)
        if new_line:
            lines.append("")

    return lines

def generate_pdf(questions, progress):
    total = len(questions)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40  # start from top
    questions = sorted(questions, key=lambda q: int(q.get("question_number", 0)))
    for idx, q in enumerate(questions):
        progress.progress((idx + 1) / total, text=f"Generating question {idx + 1} of {total}...")
        question_number = q.get("question_number", "N/A")
        soup = BeautifulSoup(q.get("question", ""), "html.parser")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        question_text = soup.get_text()
        answers = q.get("answers", [])
        most_voted = q.get("most_voted") or []

        # Question number
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, f"Question {question_number}")
        y -= 20

        # Question text (wrap long lines to fit within page width)
        c.setFont("Helvetica", 10)
        c.setStrokeColor(colors.lightgrey)
        max_width = width - 80  # Margin on both sides
        lines = wrap_text(question_text, max_width, "Helvetica", 10)
        
        for line in lines:
            if y < 100:  # Check for space at the bottom of the page
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", 10)
            c.drawString(40, y, line)
            y -= 14

        y -= 10

        # Question images
        soup = BeautifulSoup(q.get("question", ""), "html.parser")
        images = soup.find_all("img")
        for img in images:
            src = img.get("src", "")
            if src.startswith("/"):
                src = "https://www.examtopics.com" + src
            img_reader = fetch_image_from_url(src)
            if img_reader:
                img_width = 300
                img_height = 150  # Or dynamically based on ratio
                if y - img_height < 50:
                    c.showPage()
                    y = height - 40
                c.drawImage(img_reader, 40, y - img_height, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
                y -= img_height + 30
            else:
                raise ValueError(f"Failed to load image for question. Image data was None.")

        # Answers
        for a in answers:
            wrapped_answer = wrap_text(a, max_width, "Helvetica", 10)
            for line in wrapped_answer:
                if y < 80:
                    c.showPage()
                    y = height - 40
                c.drawString(40, y, line)
                y -= 14

        y -= 10
        if y < 80:
            c.showPage()
            y = height - 40

        # Most voted
        c.setFillColor(colors.black)
        if most_voted:
            most_voted_str = ", ".join(most_voted)
            c.setFillColor(colors.green)
        else:
            most_voted_str = "No most voted answer available."
        info_text = f"Most Voted: {most_voted_str}"
        wrapped_info = wrap_text(info_text, max_width, "Helvetica-Bold", 10)
        c.setFont("Helvetica-Bold", 10)
        for line in wrapped_info:
            if y < 80:
                c.showPage()
                y = height - 40
            c.drawString(40, y, line)
            y -= 14

        y -= 10
        if y < 80:
            c.showPage()
            y = height - 40

        # --- Discussion Section ---
        comments = q.get("comments", [])
        if comments:
            if y < 100:
                c.showPage()
                y = height - 40

            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(colors.black)
            c.drawString(40, y, "Discussion:")
            y -= 16

            c.setFont("Helvetica", 9)

            for idx, comment in enumerate(comments, 1):
                if comment.get("selected_answer"):
                    selected_answer_string = f"Selected Answer: {comment['selected_answer']}"
                else:
                    selected_answer_string = ""
                comment_text = f"{comment.get('content', '').strip()}"
                comment_lines = wrap_text(comment_text, max_width - 20, "Helvetica", 9)
                
                reply_boxes = []
                for reply in comment.get("replies", []):
                    reply_lines = wrap_text(reply.strip(), max_width - 40, "Helvetica-Oblique", 8)
                    reply_boxes.append(reply_lines)

                # Estimate total height
                base_height = len(comment_lines) * 12 + 22 # 12 for each line (also the header one) + 10 for padding
                replies_height = sum(len(r) * 10 + 10 for r in reply_boxes)
                box_height = base_height + replies_height + 2

                if y - box_height < 60:
                    c.showPage()
                    y = height - 40

                # Draw main comment box
                c.setFillColor(colors.whitesmoke)
                c.setStrokeColor(colors.lightgrey)
                c.roundRect(40, y - box_height, max_width, box_height, 6, fill=True, stroke=True)

                # Render comment text
                text_y = y - 14
                c.setFont("Helvetica", 9)
                c.setFillColor(colors.black)
                header_prefix = f"Comment {idx}    "
                c.drawString(50, text_y, header_prefix)
                prefix_width = c.stringWidth(header_prefix, "Helvetica", 9)
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(colors.green)
                c.drawString(50 + prefix_width, text_y, selected_answer_string)
                text_y -= 12
                c.setFont("Helvetica", 9)
                c.setFillColor(colors.black)
                for line in comment_lines:
                    c.drawString(50, text_y, line)
                    text_y -= 12

                # Render replies inside inner boxes
                for reply_lines in reply_boxes:
                    reply_box_height = len(reply_lines) * 10 + 6

                    c.setFillColorRGB(1, 1, 0.88)  # pastel yellow
                    c.setStrokeColor(colors.khaki)

                    c.roundRect(55, text_y - reply_box_height + 4, max_width - 30, reply_box_height, 4, fill=True, stroke=True)

                    c.setFont("Helvetica-Oblique", 8)
                    c.setFillColorRGB(0.1, 0.1, 0.1)
                    reply_y = text_y - 6
                    for line in reply_lines:
                        c.drawString(60, reply_y, line)
                        reply_y -= 10

                    text_y -= reply_box_height + 4  # space between replies

                y -= (box_height + 12)


        y -= 20
        if y < 80:
            c.showPage()
            y = height - 40

    c.save()
    buffer.seek(0)
    return buffer
