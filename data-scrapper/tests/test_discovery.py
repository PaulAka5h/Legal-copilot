"""Unit tests for ActDiscovery module."""

from scraper.discovery import ActDiscovery

MOCK_INDEX_HTML = """
<!DOCTYPE html>
<html>
<body>
<table class="datatable">
    <thead>
        <tr><th>Title</th><th>Number</th><th>Year</th></tr>
    </thead>
    <tbody>
        <tr>
            <td><a href="/act-11.html">The Penal Code, 1860</a></td>
            <td>XLV</td>
            <td>1860</td>
        </tr>
        <tr>
            <td><a href="/act-1306.html">বাংলাদেশ ট্যারিফ কমিশন (সংশোধন) আইন, ২০২০</a></td>
            <td>১</td>
            <td>২০২০</td>
        </tr>
        <tr>
            <!-- Duplicate act link to test deduplication -->
            <td><a href="/act-11.html">The Penal Code, 1860 Duplicate</a></td>
            <td>XLV</td>
            <td>1860</td>
        </tr>
    </tbody>
</table>
</body>
</html>
"""


def test_parse_catalog_table():
    discovery = ActDiscovery(client=None)
    acts = discovery.parse_catalog_table(MOCK_INDEX_HTML, source_url="https://bdlaws.minlaw.gov.bd/test")

    assert len(acts) == 3
    # Check English act parsing
    act_en = acts[0]
    assert act_en["act_id"] == "11"
    assert act_en["act_name"] == "The Penal Code, 1860"
    assert act_en["act_number"] == "XLV"
    assert act_en["act_year"] == "1860"
    assert act_en["language"] == "en"
    assert act_en["source_url"] == "https://bdlaws.minlaw.gov.bd/act-11.html"

    # Check Bangla act parsing
    act_bn = acts[1]
    assert act_bn["act_id"] == "1306"
    assert act_bn["act_name"] == "বাংলাদেশ ট্যারিফ কমিশন (সংশোধন) আইন, ২০২০"
    assert act_bn["act_number"] == "১"
    assert act_bn["act_year"] == "২০২০"
    assert act_bn["language"] == "bn"
