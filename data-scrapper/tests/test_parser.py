"""Offline unit tests for HTML parser using mock and real HTML fixtures."""

from scraper.parser import BDLawsParser


SAMPLE_ACT_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="masterContent">
    <section class="bg-act-section">
        <h3>The Penal Code, 1860</h3>
        <h4>ACT NO. XLV OF 1860</h4>
    </section>
    <section class="bt-act-section-search">
        <p class="publish-date">[ 6th October, 1860 ]</p>
    </section>
    <div class="act-chapter-group">
        <p class="act-chapter-no">Chapter III</p>
        <p class="act-chapter-name">OF PUNISHMENTS</p>
        <a href="/act-11/section-2188.html">53. Punishments</a>
    </div>
</div>
</body>
</html>
"""

SAMPLE_SECTION_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="masterContent">
    <div class="act-chapter-group">
        <p class="act-chapter-no">Chapter III</p>
        <p class="act-chapter-name">OF PUNISHMENTS</p>
    </div>
    <div class="txt-head">
        Punishments
    </div>
    <div class="txt-details" id="sec-dec">
        53. The punishments to which offenders are liable under the provisions of this Code are,-
        (1) Rigorous, that is, with hard labour;
        (2) Simple;
    </div>
</div>
</body>
</html>
"""


def test_parse_act_page():
    parsed = BDLawsParser.parse_act_page(SAMPLE_ACT_HTML, "https://bdlaws.minlaw.gov.bd/act-11.html")
    assert parsed["act_title"] == "The Penal Code, 1860"
    assert "XLV OF 1860" in parsed["act_number_year_raw"]
    assert parsed["enactment_date"] == "6th October, 1860"
    assert len(parsed["sections"]) == 1
    sec = parsed["sections"][0]
    assert sec["section_id"] == "2188"
    assert sec["chapter_number"] == "Chapter III"
    assert sec["chapter_title"] == "OF PUNISHMENTS"


def test_parse_section_page():
    parsed = BDLawsParser.parse_section_page(SAMPLE_SECTION_HTML, "https://bdlaws.minlaw.gov.bd/act-11/section-2188.html")
    assert parsed["section_number"] == "53"
    assert parsed["section_title"] == "Punishments"
    assert "The punishments to which offenders" in parsed["section_content"]
    assert len(parsed["subsections"]) == 2
    assert parsed["subsections"][0]["subsection_identifier"] == "(1)"
