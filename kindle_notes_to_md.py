#!/usr/bin/env python3

"""
Convert an HTML file of book notes exported from an Amazon Kindle to a Markdown document
"""

import argparse
import os
import re
import sys
import traceback
from collections import OrderedDict

import pyperclip
from bs4 import BeautifulSoup
from loguru import logger


logger.remove(0)
logger.add(sys.stdout, level="INFO")


class Note:
    # highlight, possibly including a note
    def __init__(self, category=None, text=None, hierarchy=None, page=None, location=None):
        self.category = category # highlight or note
        self.text = text # The highlight or note text
        self.hierarchy = hierarchy # Some books have extra hierarchy in a note / highlight header
        self.page = page # Will be a number, or Roman numeral if in an introduction
        self.location = location # int Location as given by Kindle


class ChapterNotes:
    def __init__(self, chapter_title=""):
        self.title = chapter_title  # name of this chapter
        self.notes = OrderedDict()  # Location (int) -> [Note]


class KindleNotes:
    def __init__(self):
        self.book_title = ""
        self.author     = ""

        self.chapter_notes = []

    def parse_file(self, html_file: str):
        with open(html_file, 'r', encoding='utf8') as fp:
            htmls = fp.read()

        soup = BeautifulSoup(htmls, 'html.parser')
        divs = soup.select('[class]') # this technically isn't "divs" as there are some highlight spans that get captured

        note = None

        for div in divs:
            div_class = div['class'][0]
            text = div.get_text().strip().replace(u' \xa0', "")

            if div_class == 'bookTitle':
                self.book_title = text
            elif div_class == 'authors':
                self.author = text
            elif div_class == 'sectionHeading':
                self.chapter_notes.append(ChapterNotes(text))
            elif div_class == 'noteHeading':
                match = re.search(r"^(?P<category>Note|Highlight)(?P<sub_category>.*) - (?P<hierarchy>.+)?Page\s+(?P<page>[0-9ivxmlcdm]+).*Location\s+(?P<location>[0-9]+)", text)
                if not match:
                    logger.critical(f"Couldn't parse noteHeading for {text}")
                    exit(1)
                logger.debug(match)

                # TODO: parse highlight color from sub_category
                category = match.group('category').lower()
                hierarchy = match.group('hierarchy')
                if hierarchy is not None:
                    hierarchy = hierarchy.replace(">","").strip()
                page = match.group("page")
                location = match.group("location")

                note = Note(category=category, hierarchy=hierarchy, page=page, location=location)

                self.chapter_notes[-1].notes[location] = note
            elif div_class == 'noteText':
                note.text = text
            else:
                x = True # placeholder
                # TODO: be pessimistic on unknown div classes?
                # logger.warning(f"Unexpected div class {div_class}")
                # sys.exit(1)

    def output_md(self, args):
        md = "Meta:\n"
        md += f"title: {self.book_title}\n"
        md += f"author: {self.author}\n"

        md += "# Highlights & Notes:\n"

        for chapter in self.chapter_notes:
            last_hierarchy = None
            md += f"## {chapter.title}\n"

            for location in chapter.notes:
                note = chapter.notes[location]

                if note.hierarchy is not None and last_hierarchy != note.hierarchy:
                    md += f"### {note.hierarchy}\n"
                    last_hierarchy = note.hierarchy

                if note.category == "highlight":
                    md += "> "
                md += f"{note.text} - *pp {note.page} loc {note.location}*\n\n"

        if args.clipboard:
            pyperclip.copy(md)
        else:
            if not os.path.exists(args.output) or args.override:
                with open(args.output, 'w', encoding='utf8') as fp:
                    fp.write(md)

                logger.info(f"Wrote the output to {args.output}")
            else:
                logger.info("Could not save .md file, because it already exists. Use --override flag.")


def parse_command_line_args():
    description = "Convert an HTML file of book notes exported from an Amazon " \
                  "Kindle to a Markdown document "
    parser = argparse.ArgumentParser(description=description)

    # positional input argument
    parser.add_argument('input',
                        help='Input HTML file')

    parser.add_argument('-c', '--clipboard',
                        action='store_true',
                        help='Use to export .md directly to the clipboard instead of file')

    parser.add_argument('-y', '--override',
                        action='store_true',
                        default=False,
                        help='Whether to override .md file in case if one already exists')

    parser.add_argument('-o', '--output',
                        default="",
                        help='A file to which save the Markdown document')

    args = parser.parse_args()

    # if no output passed, output .md file next to original HTML notes
    args.output = os.path.splitext(args.input)[0] + '.md'

    return args


if __name__ == '__main__':
    try:
        args = parse_command_line_args()

        notes = KindleNotes()
        notes.parse_file(args.input)
        notes.output_md(args)
    except Exception as ex:
        logger.exception(ex)
        traceback.print_exc()
        sys.exit(1)
