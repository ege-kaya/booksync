from ebooklib import epub
from bs4 import BeautifulSoup
import os


def open_book(path):
    book = epub.read_epub(path)
    texts = ""
    for item in book.items:
        if isinstance(item, epub.EpubHtml):
            if item.is_chapter():
                body = item.get_body_content().decode("utf-8")
                clean = BeautifulSoup(body, "lxml").text
                text = os.linesep.join([s for s in clean.splitlines() if s])
                texts += text

    return texts
