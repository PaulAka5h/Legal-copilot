"""HTML parsing module for Acts, Chapters, Sections, and Footnotes."""

from typing import Dict, List, Optional
import logging
import re
import urllib.parse
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)


class BDLawsParser:
    """Parses raw HTML of Acts and Sections on bdlaws.minlaw.gov.bd."""

    @staticmethod
    def parse_act_page(html: str, act_url: str) -> Dict[str, any]:
        """Parses an Act page to extract metadata, chapters, and section links."""
        soup = BeautifulSoup(html, "html.parser")
        master = soup.find("div", class_="masterContent") or soup

        # 1. Official Act Title
        h3 = master.find("h3")
        title = ""
        if h3:
            title = " ".join(h3.get_text().split())

        # 2. Act Number & Year from h4
        h4 = master.find("h4")
        act_no_year_text = " ".join(h4.get_text().split()) if h4 else ""

        # 3. Publish / Enactment Date from publish-date class if present
        pub_p = master.find("p", class_="publish-date")
        publish_date = ""
        if pub_p:
            publish_date = pub_p.get_text(strip=True).strip("[] ")

        # 4. Extract Section links & hierarchy
        section_links = []
        for a in master.find_all("a", href=re.compile(r"/act-\d+/section-\d+\.html")):
            href = a.get("href", "").strip()
            full_sec_url = urllib.parse.urljoin(act_url, href)
            sec_text = " ".join(a.get_text().split())

            # Find closest parent chapter group if structured within one
            chapter_no = None
            chapter_title = None
            parent_chapter_div = a.find_parent("div", class_="act-chapter-group")
            if parent_chapter_div:
                ch_no_p = parent_chapter_div.find("p", class_="act-chapter-no")
                ch_title_p = parent_chapter_div.find("p", class_="act-chapter-name")
                if ch_no_p:
                    chapter_no = ch_no_p.get_text(strip=True)
                if ch_title_p:
                    chapter_title = ch_title_p.get_text(strip=True)

            m = re.search(r"/act-(\d+)/section-(\d+)\.html", href)
            sec_id = m.group(2) if m else None

            section_links.append({
                "section_id": sec_id,
                "section_link_text": sec_text,
                "section_url": full_sec_url,
                "chapter_number": chapter_no,
                "chapter_title": chapter_title,
            })

        # Deduplicate section links in order
        unique_sections = []
        seen_sec_urls = set()
        for sl in section_links:
            if sl["section_url"] not in seen_sec_urls:
                seen_sec_urls.add(sl["section_url"])
                unique_sections.append(sl)

        return {
            "act_title": title,
            "act_number_year_raw": act_no_year_text,
            "enactment_date": publish_date or None,
            "sections": unique_sections,
        }

    @staticmethod
    def parse_section_page(html: str, section_url: str) -> Dict[str, any]:
        """Parses a Section page (/act-{id}/section-{sec_id}.html)."""
        soup = BeautifulSoup(html, "html.parser")
        master = soup.find("div", class_="masterContent") or soup

        # 1. Enactment / Commencement date
        pub_p = master.find("p", class_="publish-date")
        enactment_date = pub_p.get_text(strip=True).strip("[] ") if pub_p else None

        # 2. Chapter Information
        ch_div = master.find("div", class_="act-chapter-group")
        chapter_no = None
        chapter_title = None
        if ch_div:
            c_no_elem = ch_div.find("p", class_="act-chapter-no")
            c_title_elem = ch_div.find("p", class_="act-chapter-name")
            if c_no_elem:
                chapter_no = c_no_elem.get_text(strip=True)
            if c_title_elem:
                chapter_title = c_title_elem.get_text(strip=True)

        # 3. Section Title (Header)
        txt_head = master.find("div", class_="txt-head")
        section_title = " ".join(txt_head.get_text().split()) if txt_head else ""

        # 4. Section Content Details
        txt_details = master.find("div", class_="txt-details") or master.find(id="sec-dec")
        section_content = ""
        section_number = None

        if txt_details:
            section_content = txt_details.get_text("\n", strip=True)

            first_line = section_content.split("\n")[0].strip()
            # Support Bangla (১।, ১ক।, ২।), English (1., 53., 53A.), and Roman (I., II.)
            num_match = re.match(r"^([০-৯\d]+[A-Za-z\u0980-\u09ff]?|[IVXLCDMivxlcdm]+)\s*[\.\।]", first_line)
            if num_match:
                section_number = num_match.group(1)

        # 5. Extract Subsections: only numeric/alphabetic clause identifiers: (1), (১), (a), (ক), (i), (iv)
        # Avoid matching arbitrary parenthesized words like (সংশোধন)
        subsections = []
        if section_content:
            lines = [ln.strip() for ln in section_content.split("\n") if ln.strip()]
            current_sub = None
            sub_pattern = re.compile(r"^(\([০-৯\d]{1,3}\)|\([a-zA-Z\u0995-\u09b9]{1,2}\)|\([ivxlcdmIVXLCDM]{1,4}\))\s*(.*)")
            for line in lines:
                sub_match = sub_pattern.match(line)
                if sub_match:
                    if current_sub:
                        subsections.append(current_sub)
                    current_sub = {
                        "subsection_identifier": sub_match.group(1),
                        "text": sub_match.group(2).strip(),
                    }
                elif current_sub:
                    current_sub["text"] += " " + line

            if current_sub:
                subsections.append(current_sub)

        return {
            "section_number": section_number,
            "section_title": section_title,
            "section_content": section_content,
            "chapter_number": chapter_no,
            "chapter_title": chapter_title,
            "enactment_date": enactment_date,
            "subsections": subsections,
            "source_url": section_url,
        }
