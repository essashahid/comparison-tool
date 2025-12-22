#!/usr/bin/env python3
"""
PDF Data to JSON Tool

Developer: Njaka ANDRIAMAHENINA
Email: a6njaka@gmail.com
Version: 2025-12-09
"""

import argparse
import sys
from pathlib import Path
import fitz
import json
import re
import copy


class PDF_Headings:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = None
        self.open_pdf()
        self.all_data = []
        self.raw_data = []
        self.raw_data_by_page = []
        self.all_tab = []
        self.text_levels = [46.8, 62.6, 78.5, 94.3, 110.2, 126.0, 141.8]
        self.all_level1 = []
        self.all_level2 = []
        self.all_level3 = []
        self.all_level4 = []
        self.all_level5 = []
        self.all_level6 = []
        self.all_level7 = []

    def open_pdf(self) -> bool:
        try:
            self.doc = fitz.open(self.pdf_path)
            return True
        except Exception as e:
            print(f"Error opening PDF: {e}")
            return False

    def is_numbering(self, text):
        text = text.strip()
        text = re.sub(r'\s+', '', text)
        if not text:
            return False

        if not (text.startswith('(') and text.endswith(')')):
            return False

        content = text[1:-1].strip()
        if not content:
            return False

        content_lower = content.lower()

        patterns = [
            r'^[a-z]$',
            r'^[0-9]{1,3}$',
            r'^([a-z])\1+$'
        ]
        for pattern in patterns:
            if re.match(pattern, content_lower):
                return True

        if self.is_roman_numeral(content):
            return True

        return False

    @staticmethod
    def is_roman_numeral(s):
        roman_pattern = r'^(M{0,3})(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$'

        return bool(re.match(roman_pattern, s, re.IGNORECASE))

    def get_heading_text(self, h):
        # print("\n---->get_heading_text")
        ret = ""
        h_x1, h_y1, h_x2, h_y2, h_text, h_page = h["x1"], h["y1"], h["x2"], h["y2"], h["text"], h["page"]
        # print("--oo->", h)

        n = h_page - 2
        m = len(self.raw_data_by_page)
        is_found = False
        for i in range(n, n + min(10, m - n)):
            data_page = self.raw_data_by_page[i]
            data_page.sort(key=lambda d: (d["y1"], d["x1"]))
            for data in data_page:
                # print("    -44->", data)
                d_x1, d_y1, d_x2, d_y2, d_page = data["x1"], data["y1"], data["x2"], data["y2"], data["page"]
                text = data["text"]
                m1 = re.search(r"^[0-9.]{10}$", text)
                m2 = re.search(r"^(\d+\.($|\s*\()|\([^.]{1,5}\))", text)
                is_first = True
                if 10 < d_y1:
                    vertical_overlap = (d_y1 <= h_y1 <= d_y2 or d_y1 <= h_y2 <= d_y2)
                    is_right_of_heading = d_x1 > h_x2

                    if vertical_overlap and is_right_of_heading and h_page == d_page:
                        # print("       -55->", data)
                        ret += text
                        is_first = False

                if d_x1 in self.text_levels and m2 is not None and d_y1 > h_y2 + 10:
                    # print("-->BREAK\n", data)
                    is_found = True
                    break

                if d_y2 > h_y1 and is_first and ret != "":
                    # print("--m1-->", text, d_y1, d_page)
                    ret += f"\n{text}"

            if is_found:
                break

        return ret

    def update_raw_data(self):
        print("---->update_raw_data")
        self.raw_data = []
        page_numbers = len(self.doc)
        # page_numbers = 200

        last_x1 = 0
        last_y2 = 0
        cumulate_y = 0

        for i in range(1, page_numbers):
            self.raw_data_by_page.append([])
            page = self.doc[i]
            blocks = page.get_text("dict")["blocks"]

            x_positions = []

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            x_positions.append(span["bbox"][0])
                            text = span["text"].strip()
                            # print("-->", text)
                            x1 = round(span["bbox"][0], 1)
                            y1 = round(span["bbox"][1], 1)
                            x2 = round(span["bbox"][2], 1)
                            y2 = round(span["bbox"][3], 1)
                            if y1 > 70:
                                template = copy.deepcopy({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "text": f"{text}", "value": "", "level": -1, "page": i + 1})
                                if abs(last_x1 - x1) < 2 and abs(y1 - last_y2) < 2:
                                    self.raw_data[-1]["text"] += f" {text}"
                                    self.raw_data[-1]["y2"] = y2 + cumulate_y
                                else:
                                    template["y1"] = y1 + cumulate_y
                                    template["y2"] = y2 + cumulate_y
                                    self.raw_data.append(template)
                                    self.raw_data_by_page[-1].append(template)

                                last_x1 = x1
                                last_y2 = y2
            cumulate_y += page.rect.height

        # for d in self.raw_data_by_page:
        #     print()
        #     for xx in d:
        #         print('->', xx)

        return None

    def get_text_blocks(self):
        print("---->get_text_blocks")
        verification = False

        for d in self.raw_data:
            text = d["text"].strip()
            l = len(text)
            x1 = round(d["x1"], 1)
            y1 = round(d["y1"], 1)
            x2 = round(d["x2"], 1)
            y2 = round(d["y2"], 1)
            i = d["page"]
            m1 = re.search(r"^(\d+\.($|\s*\()|\([^.]{1,5}\))", text)
            m2 = re.search(r"^(?:.?SUBCHAPTER (.*?) deleted.?|SUBCHAPTER\s*(.*))$", text)
            m3 = re.search(r"^(\([a-zA-Z]+\))\s+", text)

            if m1 is not None and l < 10 and x1 < 200 and ":" not in text and "(con.)" not in text:
                self.all_tab.append(x1)

                #TODO: remove the text "/page:{i}" bellow for the final version
                template = copy.deepcopy({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "text": f"{text}/page:{i}", "value": self.get_heading_text(d), "level": -1, "page": i})
                # print("-->", template)

                if x1 == 46.8:
                    self.all_level1.append(text)
                    if verification:
                        print(text, " " * 10, x1, f"    page:{i}")
                    template["level"] = 1
                elif x1 == 62.6:
                    self.all_level2.append(text)
                    if verification:
                        print(" " * 3, text, " " * 10, x1, f"    page:{i}")
                    template["level"] = 2
                elif x1 == 78.5:
                    self.all_level3.append(text)
                    if verification:
                        print(" " * 7, text, " " * 10, x1, f"    page:{i}")
                    template["level"] = 3
                elif x1 == 94.3:
                    self.all_level4.append(text)
                    if verification:
                        print(" " * 12, text, " " * 10, x1, f"    page:{i}")
                    template["level"] = 4
                elif x1 == 110.2:
                    self.all_level5.append(text)
                    if verification:
                        print(" " * 16, text, " " * 10, x1, f"    page:{i}")
                    template["level"] = 5
                elif x1 == 126.0:
                    self.all_level6.append(text)
                    if verification:
                        print(" " * 20, text, " " * 10, x1, f"    page:{i}")
                    template["level"] = 6
                elif x1 == 141.8:
                    self.all_level7.append(text)
                    if verification:
                        print(" " * 24, text, " " * 10, x1, f"    page:{i}")
                    template["level"] = 7

                # Exception
                if i == 758:
                    template["level"] -= 1
                elif i == 760:
                    template["level"] -= 2

                self.all_data.append(template)

            elif m3 is not None:
                txt = m3.group(1)
                if self.is_numbering(txt):
                    print("--v2-->", text, i)

            elif m2 is not None:
                # print()
                # print("*" * 50)
                # print(text, f"         page:{i}")
                # print("*" * 50)
                result = m2.group(1) if m2.group(1) else m2.group(2)
                t = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "text": result, "value": "", "level": 0, "page": i}
                self.all_data.append(t)

        self.all_data = self.clean_data()
        print("NUMBER_OF_DATA:", len(self.all_data))

        return None

    def clean_data(self):
        print("---->clean_data")
        ret_data = []
        for d in self.all_data:
            try:
                text = d["text"]
                m1 = re.search(r"(\(.*?\))\s*(\(.*?\))", text)
                m2 = re.search(r"(\d+\.)\s(\(.*?\))", text)
                if m1 is not None:
                    tmp1 = copy.deepcopy(d)
                    tmp2 = copy.deepcopy(d)
                    tmp1["text"] = m1.group(1)
                    tmp1["value"] = ""
                    tmp2["text"] = m1.group(2)
                    tmp2["level"] += 1
                    index = self.text_levels.index(tmp2["x1"])
                    tmp2["x1"] = self.text_levels[index + 1]
                    ret_data.append(tmp1)
                    ret_data.append(tmp2)
                elif m2 is not None:
                    tmp1 = copy.deepcopy(d)
                    tmp2 = copy.deepcopy(d)
                    tmp1["text"] = m2.group(1)
                    tmp1["value"] = ""
                    tmp2["text"] = m2.group(2)
                    tmp2["level"] += 1
                    index = self.text_levels.index(tmp2["x1"])
                    tmp2["x1"] = self.text_levels[index + 1]
                    ret_data.append(tmp1)
                    ret_data.append(tmp2)
                else:
                    ret_data.append(d)
            except KeyError as e:
                print(f"Key missed in the data: {e}")
                ret_data.append(d)
        return ret_data

    def display_test(self):
        unique_list = list(set(self.all_tab))
        unique_list = sorted(unique_list)
        print(unique_list)
        print()
        self.display_data(sorted(list(set(self.all_level1))), 1)
        self.display_data(sorted(list(set(self.all_level2))), 2)
        self.display_data(sorted(list(set(self.all_level3))), 3)
        self.display_data(sorted(list(set(self.all_level4))), 4)
        self.display_data(sorted(list(set(self.all_level5))), 5)
        self.display_data(sorted(list(set(self.all_level6))), 6)
        self.display_data(sorted(list(set(self.all_level7))), 7)

    @staticmethod
    def display_data(data, level):
        print(level, "-" * 100)
        for d in data:
            print(d)

    def format_data(self):
        print("\n---->format_data")
        return_data = []
        template_subchapter = {"SUBCHAPTER": "", "data": []}
        template = {"heading": "", "heading text": "", "data": []}
        last_level_added = -1
        subchapter = ""
        for data in self.all_data:
            try:
                if data["level"] == 0 and self.is_roman_numeral(data["text"]):
                    t = copy.deepcopy(template_subchapter)
                    t["SUBCHAPTER"] = data["text"]
                    subchapter = data["text"].strip()
                    return_data.append(t)
                    last_level_added = 0

                elif subchapter not in ("XX", "XXI", "XXII"):
                    if data["level"] == 1:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 1
                    elif data["level"] == 2 and last_level_added >= 1:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 2
                    elif data["level"] == 3 and last_level_added >= 2:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 3
                    elif data["level"] == 4 and last_level_added >= 3:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"][-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 4
                    elif data["level"] == 5 and last_level_added >= 4:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"][-1]["data"][-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 5
                    elif data["level"] == 6 and last_level_added >= 5:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"][-1]["data"][-1]["data"][-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 6
                    elif data["level"] == 7 and last_level_added >= 6:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"][-1]["data"][-1]["data"][-1]["data"][-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 7

                    # Exception
                    elif data["level"] == 4 and last_level_added == 2:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 3
                    elif data["level"] == 5 and last_level_added == 3:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"][-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 4
                    else:
                        print("-->E_STD: ", data["text"], data["x1"], data["page"], f"current_level = {data['level']} / last_level_added = {last_level_added}")

                elif subchapter == "XX":
                    if data["x1"] == self.text_levels[0]:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 1
                    else:
                        print("-->E1: ", data["text"], data["x1"], data["page"], f"current_level = {data['level']} / last_level_added = {last_level_added}")

                elif subchapter == "XXI":
                    if data["x1"] == self.text_levels[1]:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 1
                    else:
                        print("-->E2: ", data["text"], data["x1"], data["page"], f"current_level = {data['level']} / last_level_added = {last_level_added}")

                elif subchapter == "XXII":
                    if data["x1"] == self.text_levels[2]:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 1
                    elif data["x1"] == self.text_levels[3]:
                        template1 = copy.deepcopy(template)
                        template1["heading"] = data["text"]
                        template1["heading text"] = data["value"]
                        return_data[-1]["data"][-1]["data"].append(copy.deepcopy(template1))
                        last_level_added = 2
                    else:
                        print("-->E3: ", data["text"], data["x1"], data["page"], f"current_level = {data['level']} / last_level_added = {last_level_added}")


            except KeyError as e:
                print(f"-->Erreur critique: Key missed {e}")
            except Exception as e:
                print(f"Unexcepted error: {e}")

        return return_data

    # Méthode pour exporter en JSON
    def export_to_json(self, filename=None):
        hierarchical_data = self.format_data()
        if filename:
            with open(filename, 'w', encoding='utf-8-sig') as f:
                json.dump(hierarchical_data, f, ensure_ascii=False, indent=4)

        return hierarchical_data


def main():
    """Main function to handle command line arguments and process PDF"""
    parser = argparse.ArgumentParser(description='Extract headings from PDF and export to JSON')
    parser.add_argument('pdf_path', help='Path to the input PDF file')
    parser.add_argument('json_path', nargs='?', help='Path to the output JSON file (optional)')

    args = parser.parse_args()

    # Validate PDF path
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF file '{pdf_path}' not found.")
        sys.exit(1)

    # Generate JSON path if not provided
    if args.json_path:
        json_path = Path(args.json_path)
    else:
        json_path = pdf_path.with_suffix('.json')

    print(f"Processing PDF: {pdf_path}")
    print(f"Output JSON: {json_path}")

    try:
        # Process PDF
        pdf_processor = PDF_Headings(str(pdf_path))
        pdf_processor.update_raw_data()
        pdf_processor.get_text_blocks()

        # Export to JSON
        pdf_processor.export_to_json(str(json_path))
        print(f"Successfully exported JSON to: {json_path}")

    except Exception as e:
        print(f"Error processing PDF: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
