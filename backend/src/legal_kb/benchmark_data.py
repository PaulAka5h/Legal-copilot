"""Comprehensive benchmark evaluation dataset for Bangladesh Legal RAG.

Includes verified questions across:
1. Exact section lookups (English and Bengali)
2. Offence & penalty provisions
3. Exception-related questions
4. Procedural & limitation questions
5. Bilingual / Bangla queries
6. Insufficient evidence / negative queries (anti-hallucination test)
"""

from typing import List, Optional
from pydantic import BaseModel


class LegalBenchmarkQuery(BaseModel):
    id: str
    query: str
    language: str  # 'en', 'bn', 'mixed'
    expected_act: str
    expected_section: Optional[str] = None
    category: str  # 'exact_section', 'offence', 'exception', 'insufficient_evidence', 'bilingual'
    should_answer: bool = True  # False for queries outside the database to test rejection


BENCHMARK_DATASET: List[LegalBenchmarkQuery] = [
    # 1. Exact Section Lookups (English)
    LegalBenchmarkQuery(
        id="BENCH-01",
        query="What is the definition of murder under Section 300 of the Penal Code?",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="300",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-02",
        query="Explain Section 302 of the Penal Code regarding punishment for murder.",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="302",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-03",
        query="What does Section 138 of the Negotiable Instruments Act say about dishonour of cheques?",
        language="en",
        expected_act="The Negotiable Instruments Act, 1881",
        expected_section="138",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-04",
        query="Show me Section 420 regarding cheating and dishonestly inducing delivery of property.",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="420",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-05",
        query="What is Section 378 of the Penal Code about theft?",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="378",
        category="exact_section",
    ),
    # 2. Exact Section Lookups (Bengali)
    LegalBenchmarkQuery(
        id="BENCH-06",
        query="দণ্ডবিধির ধারা ৩০০ অনুযায়ী খুন কাকে বলে?",
        language="bn",
        expected_act="The Penal Code, 1860",
        expected_section="300",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-07",
        query="দণ্ডবিধির ৩০২ ধারায় খুনের শাস্তি কী?",
        language="bn",
        expected_act="The Penal Code, 1860",
        expected_section="302",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-08",
        query="ধারা ৪২০ এর প্রতারণার বিধান কী?",
        language="bn",
        expected_act="The Penal Code, 1860",
        expected_section="420",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-09",
        query="চেক ডিজঅনার হলে ১৩৮ ধারার অধীনে কি প্রতিকার পাওয়া যায়?",
        language="bn",
        expected_act="The Negotiable Instruments Act, 1881",
        expected_section="138",
        category="exact_section",
    ),
    LegalBenchmarkQuery(
        id="BENCH-10",
        query="দণ্ডবিধির ৩৭৯ ধারায় চুরির শাস্তি কী?",
        language="bn",
        expected_act="The Penal Code, 1860",
        expected_section="379",
        category="exact_section",
    ),
    # 3. Offence & Conceptual Questions
    LegalBenchmarkQuery(
        id="BENCH-11",
        query="What constitutes criminal breach of trust under Bangladesh law?",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="405",
        category="offence",
    ),
    LegalBenchmarkQuery(
        id="BENCH-12",
        query="What is the legal punishment for extortion?",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="384",
        category="offence",
    ),
    LegalBenchmarkQuery(
        id="BENCH-13",
        query="কারো ক্ষতি করার উদ্দেশ্যে ইচ্ছাকৃত আঘাত প্রদানের শাস্তি কী?",
        language="bn",
        expected_act="The Penal Code, 1860",
        expected_section="323",
        category="offence",
    ),
    # 4. Exception-related Questions
    LegalBenchmarkQuery(
        id="BENCH-14",
        query="When is culpable homicide not considered murder under grave and sudden provocation?",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="300",
        category="exception",
    ),
    LegalBenchmarkQuery(
        id="BENCH-15",
        query="Does private defence extend to causing death under the Penal Code?",
        language="en",
        expected_act="The Penal Code, 1860",
        expected_section="100",
        category="exception",
    ),
    # 5. Negative / Insufficient Evidence Questions (Anti-Hallucination)
    LegalBenchmarkQuery(
        id="BENCH-16",
        query="What does the French Commercial Code of 1807 state about maritime mortgages?",
        language="en",
        expected_act="",
        expected_section=None,
        category="insufficient_evidence",
        should_answer=False,
    ),
    LegalBenchmarkQuery(
        id="BENCH-17",
        query="Under Section 9999 of the Intergalactic Space Act, what is the penalty for asteroid speeding?",
        language="en",
        expected_act="",
        expected_section=None,
        category="insufficient_evidence",
        should_answer=False,
    ),
    LegalBenchmarkQuery(
        id="BENCH-18",
        query="কাল্পনিক মঙ্গল গ্রহের পরিবহন আইন অনুযায়ী জরিমানা কত?",
        language="bn",
        expected_act="",
        expected_section=None,
        category="insufficient_evidence",
        should_answer=False,
    ),
]
