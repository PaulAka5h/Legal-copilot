"""Hearing update -> timeline -> re-run analysis and strategy -> reassessment diff (Step F).

The order text becomes a lawyer_entered fact (the lawyer typed it), so the
re-run analysis sees it. A next date entered and confirmed by the lawyer
creates a confirmed hearing; a date found in the order text by code is only a
draft suggestion. A plain-language client summary is stored as a draft in
client_visible_updates; the lawyer publishes it through the existing flow.
"""

import re
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import write_audit_event
from app.case_analysis import service as analysis_service
from app.database import user_transaction
from app.facts import repository as facts_repo
from app.strategy_tree import service as strategy_service

_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}
_MONTHS.update({m: i for i, m in enumerate(
    ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর",
     "ডিসেম্বর"], start=1)})
_MONTHS = {__import__("unicodedata").normalize("NFC", k): v for k, v in _MONTHS.items()}


def suggest_date(order_text: str, after: date | None = None) -> date | None:
    """Latest plausible date written in the order text (draft only). English or Bangla."""
    import unicodedata

    value = unicodedata.normalize("NFC", order_text).translate(_BN_DIGITS)
    found: list[date] = []
    patterns = (
        (r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        (r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", lambda m: (int(m[3]), int(m[2]), int(m[1]))),
        (r"\b(\d{1,2})\s+([A-Za-zঀ-৿]+),?\s+(\d{4})", lambda m: (int(m[3]), _MONTHS.get(
            unicodedata.normalize("NFC", m[2]).lower(), 0), int(m[1]))),
    )
    for pattern, parts in patterns:
        for match in re.finditer(pattern, value):
            try:
                found.append(date(*parts(match)))
            except ValueError:
                continue
    candidates = [d for d in found if after is None or d > after]
    return max(candidates) if candidates else None


def _finding_changes(before: dict | None, after: dict) -> list[dict]:
    old = {f["offence_or_claim"]: f["strength"] for f in (before or {}).get("findings", [])}
    new = {f["offence_or_claim"]: f["strength"] for f in after["findings"]}
    return [{"offence_or_claim": name, "before": old.get(name), "after": new.get(name)}
            for name in sorted(old.keys() | new.keys()) if old.get(name) != new.get(name)]


def _tasks(tree: dict | None, analysis: dict, suggested: date | None, confirmed: bool) -> list[str]:
    tasks: list[str] = []
    if tree:
        for move in tree["root"]["children"]:
            tasks.extend(move["requirements"])
    tasks.extend(analysis["missing_information"])
    if suggested and not confirmed:
        tasks.append(f"Confirm the next hearing date (order text mentions {suggested.isoformat()}; draft only).")
    if not confirmed and not suggested:
        tasks.append("Enter and confirm the next hearing date.")
    seen: set[str] = set()
    return [t for t in tasks if not (t in seen or seen.add(t))][:15]


def client_summary(hearing_date, order_text: str, next_date, confirmed: bool) -> tuple[str, str, str]:
    """Plain-language summary for the client: the order and next date only, no legal analysis (Rule 8)."""
    bn = sum("ঀ" <= c <= "৿" for c in order_text) > len(order_text) / 3
    when = hearing_date.strftime("%d %B %Y") if hearing_date else ""
    nxt = next_date.strftime("%d %B %Y") if (next_date and confirmed) else None
    if bn:
        body = (f"আপনার মামলার শুনানি হয়েছে {when}। আদালতের আদেশ: {order_text}\n"
                + (f"পরবর্তী শুনানির তারিখ: {nxt}।" if nxt else "পরবর্তী তারিখ আপনার আইনজীবী নিশ্চিত করবেন।"))
        return "শুনানির হালনাগাদ", body, "bn"
    body = (f"Your case had a hearing{(' on ' + when) if when else ''}. The court's order: {order_text}\n"
            + (f"Next hearing date: {nxt}." if nxt else "Your lawyer will confirm the next date."))
    return "Hearing update", body, "en"


async def submit_update(session_factory: async_sessionmaker[AsyncSession], *, case_id: UUID, hearing_id: UUID,
                        user_id: UUID, payload, embedder, reranker, llm, allow_mock: bool, thresholds) -> UUID:
    async with user_transaction(session_factory, user_id) as session:
        hearing = (await session.execute(text(
            "SELECT h.id, h.scheduled_at, h.organization_id FROM public.hearings h WHERE h.id = :h AND h.case_id = :c"),
            {"h": hearing_id, "c": case_id})).mappings().first()
        if hearing is None:
            raise LookupError("hearing not found")
        organization_id = hearing["organization_id"]
        prior = (await session.execute(text(
            "SELECT id, version FROM public.hearing_updates WHERE hearing_id = :h ORDER BY version DESC LIMIT 1"),
            {"h": hearing_id})).first()
        update_id = await session.scalar(text(
            """
            INSERT INTO public.hearing_updates (case_id, organization_id, hearing_id, author_id, happened,
              orders_directions, next_hearing_date, next_hearing_confirmed, source_label, version, supersedes_id)
            VALUES (:c, :o, :h, :u, :happened, :orders, :next, :confirmed, 'lawyer_entered', :v, :sup)
            RETURNING id
            """), {"c": case_id, "o": organization_id, "h": hearing_id, "u": user_id,
                   "happened": payload.notes or "", "orders": payload.order_text, "next": payload.next_hearing_date,
                   "confirmed": payload.next_hearing_confirmed, "v": (prior[1] + 1) if prior else 1,
                   "sup": prior[0] if prior else None})
        when = hearing["scheduled_at"].date().isoformat() if hearing["scheduled_at"] else "a hearing"
        await facts_repo.insert_fact(session, {
            "case_id": case_id, "organization_id": organization_id, "lineage_id": uuid4(), "version": 1,
            "supersedes_id": None, "category": "document",
            "statement": f"Court order at the hearing on {when}: {payload.order_text}"[:4000],
            "attributes": {"date": hearing["scheduled_at"].date().isoformat()} if hearing["scheduled_at"] else {},
            "statement_type": "lawyer_entered", "fact_status": "undisputed", "origin": "lawyer",
            "source_check": "not_applicable", "extraction_run_id": None, "created_by": user_id,
        })
        next_hearing_id = None
        if payload.next_hearing_confirmed:
            next_hearing_id = await session.scalar(text(
                """
                INSERT INTO public.hearings (case_id, organization_id, scheduled_at, purpose, date_status,
                  date_confirmed_by, date_confirmed_at)
                VALUES (:c, :o, :d, 'Next hearing (lawyer-confirmed)', 'confirmed', :u, now())
                RETURNING id
                """), {"c": case_id, "o": organization_id, "d": payload.next_hearing_date, "u": user_id})
        await session.execute(text("UPDATE public.hearings SET date_status = 'held' WHERE id = :h"), {"h": hearing_id})
        previous_analysis = await analysis_service.get_analysis(session, case_id)
        previous_tree = await strategy_service.get_tree(session, case_id)

    analysis_id = await analysis_service.run_analysis(
        session_factory, case_id=case_id, user_id=user_id, incident_date=payload.incident_date, language=None,
        embedder=embedder, reranker=reranker, llm=llm, allow_mock=allow_mock, thresholds=thresholds,
        trigger="hearing_update", trigger_ref_id=update_id)
    tree_id = await strategy_service.run_strategy(
        session_factory, case_id=case_id, user_id=user_id, analysis_version=None, llm=llm, allow_mock=allow_mock,
        trigger="hearing_update", trigger_ref_id=update_id)

    async with user_transaction(session_factory, user_id) as session:
        analysis = analysis_service.to_out(await analysis_service.get_analysis_by_id(session, case_id, analysis_id))
        tree = strategy_service.to_out(await strategy_service.get_tree(session, case_id, tree_id=tree_id))
        comparison = (strategy_service.compare_trees(strategy_service.to_out(previous_tree), tree)
                      if previous_tree else {"closed_options": [], "new_options": [
                          m["move"] for m in tree["root"]["children"]]})
        hearing_day = hearing["scheduled_at"].date() if hearing["scheduled_at"] else None
        suggested = None if payload.next_hearing_confirmed else suggest_date(payload.order_text, hearing_day)
        title, body, language = client_summary(hearing["scheduled_at"], payload.order_text, payload.next_hearing_date,
                                               payload.next_hearing_confirmed)
        client_update_id = await session.scalar(text(
            """
            INSERT INTO public.client_visible_updates (case_id, organization_id, title, body, language, status,
              drafted_by_ai)
            VALUES (:c, :o, :t, :b, :l, 'draft', true) RETURNING id
            """), {"c": case_id, "o": organization_id, "t": title, "b": body, "l": language})
        diff = {
            "changes": _finding_changes(analysis_service.to_out(previous_analysis) if previous_analysis else None,
                                        analysis),
            "closed_options": comparison["closed_options"], "new_options": comparison["new_options"],
            "tree_version": tree["version"], "analysis_version": analysis["version"],
            "tasks": _tasks(tree, analysis, suggested, payload.next_hearing_confirmed),
            "suggested_next_date": suggested.isoformat() if suggested else None,
            "next_hearing_id": str(next_hearing_id) if next_hearing_id else None,
        }
        import json

        reassessment_id = await session.scalar(text(
            """
            INSERT INTO public.case_reassessments (case_id, organization_id, hearing_id, hearing_update_id,
              previous_analysis_id, analysis_id, previous_tree_id, tree_id, diff, client_update_id, created_by)
            VALUES (:c, :o, :h, :hu, :pa, :a, :pt, :t, CAST(:d AS jsonb), :cu, :u) RETURNING id
            """), {"c": case_id, "o": organization_id, "h": hearing_id, "hu": update_id,
                   "pa": previous_analysis["id"] if previous_analysis else None, "a": analysis_id,
                   "pt": previous_tree["id"] if previous_tree else None, "t": tree_id,
                   "d": json.dumps(diff, ensure_ascii=False), "cu": client_update_id, "u": user_id})
        await write_audit_event(session, action="hearing.reassessed", actor_user_id=user_id, actor_role="lawyer",
                                object_type="case_reassessment", object_id=reassessment_id, case_id=case_id,
                                ip_address=None, user_agent=None, request_id=None,
                                details={"hearing_id": str(hearing_id), "tree_version": tree["version"],
                                         "closed": len(diff["closed_options"]), "new": len(diff["new_options"])})
    return reassessment_id


REASSESSMENT_QUERY = """
    SELECT r.id, r.hearing_id, r.hearing_update_id, r.diff, r.client_update_id, r.created_at, u.status AS client_update_status
    FROM public.case_reassessments r
    LEFT JOIN public.client_visible_updates u ON u.id = r.client_update_id
    WHERE r.case_id = :c
"""


def reassessment_out(row: dict) -> dict:
    diff = row["diff"]
    return {"id": row["id"], "hearing_id": row["hearing_id"], "hearing_update_id": row["hearing_update_id"],
            "changes": diff["changes"], "closed_options": diff["closed_options"], "new_options": diff["new_options"],
            "tree_version": diff["tree_version"], "analysis_version": diff["analysis_version"], "tasks": diff["tasks"],
            "suggested_next_date": diff["suggested_next_date"], "next_hearing_id": diff["next_hearing_id"],
            "client_update_id": row["client_update_id"], "client_update_status": row["client_update_status"],
            "created_at": row["created_at"]}
