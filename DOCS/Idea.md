1. The idea

I want to build an AI-powered legal platform for lawyers in Bangladesh.

A lawyer meets a client who wants to pursue a legal case. The client provides documents and other information. Those materials may be PDFs, photographs, scanned papers, hard-copy documents that have been photographed or scanned, or other supported formats.

The lawyer uploads the client's materials to the platform. The AI reads and analyzes the documents, extracts the important facts, understands the case as far as the available information allows, and researches relevant Bangladesh laws, legal provisions, regulations, and court judgments.

After reviewing the case materials and relevant law, the AI helps the lawyer understand how the case could be approached. It should identify possible legal strategies, explain the strengths and weaknesses of each, identify risks, and consider what the opposing lawyer might argue or do.

The most distinctive feature is a **chess-inspired legal strategy analysis engine**.

A chess engine evaluates possible moves, considers what the opponent might do in response, explores alternative lines, and evaluates which move appears strongest. I want the legal platform to use a comparable structured approach for legal strategy:

- Evaluate one possible legal approach.

- Explore plausible responses from the opposing side.

- Consider the counterarguments available to the lawyer.

- Identify obstacles, risks, and weaknesses.

- Evaluate alternative approaches.

- Compare the possible paths and explain which appears better supported by the facts and law.

The AI should continue helping throughout the case. After each court hearing, the lawyer enters what happened. The AI updates its understanding, reassesses the current strategy, considers new possible developments, and tells the lawyer whether the existing strategy still appears suitable or whether it should be reviewed or changed.

The platform must also provide two different dashboard experiences in one application: one for lawyers and one for clients. Lawyers receive the full professional workspace. Clients see only the information relevant to their own case that the lawyer has chosen to share.

The AI is a decision-support tool for lawyers. It does not replace the lawyer, decide cases, guarantee a court outcome, or claim to know exactly what a judge or opposing lawyer will do.

# 2. Product goals

The platform should achieve these goals:

1. Help lawyers understand large collections of client documents more efficiently.

2. Help identify relevant facts, evidence, contradictions, and missing information.

3. Make Bangladesh legal research easier and more traceable.

4. Compare possible legal strategies in a structured way.

5. Explore plausible opposing arguments and possible responses.

6. Keep the strategy analysis updated as new case information arrives.

7. Give lawyers a complete workspace for managing cases and clients.

8. Give clients a simple, controlled view of their case progress.

9. Protect confidential client information and keep each case's data isolated.

10. Make every important AI conclusion traceable to source documents or legal authorities.

# 3. Users and access levels

The application has one platform and two main user experiences.

## 3.1 Lawyer

The lawyer is the primary user and controls the case workspace.

The lawyer should be able to:

- Register and sign in.

- Create and manage client profiles.

- Create individual legal cases.

- Invite clients to access their own case information.

- Upload case documents in supported formats.

- Review extracted text and OCR results.

- Ask the AI to analyze case documents.

- Research Bangladesh laws and judgments.

- Review evidence, timelines, contradictions, and missing information.

- Generate and compare possible legal strategies.

- Review possible opposing-side arguments.

- Review risks and possible counterarguments.

- Record hearing information after each hearing.

- Receive updated AI analysis after new information is entered.

- Decide which case updates and documents clients may see.

- Close cases and manage client access.

- Keep authorized access to historical case records.

- Review previous AI analyses and strategy changes.

## 3.2 Client

The client has a separate, simplified dashboard.

The client should only see information relevant to their own case and explicitly approved for client viewing by the lawyer.

The client dashboard may include:

- Current case status.

- General progress of the case.

- A client-friendly explanation of the current stage.

- Next hearing date, when confirmed.

- Whether the client needs to attend court.

- Other actions the client needs to take.

- Documents or information the lawyer has requested.

- Updates that the lawyer has approved for sharing.

- Documents the lawyer has deliberately shared.

- Relevant notifications.

The client must not automatically see:

- The lawyer's private notes.

- Internal AI analysis.

- Confidential strategy discussions.

- Unshared evidence assessments.

- Internal risk assessments.

- Private communications.

- Other clients' cases or information.

The lawyer must control which fields, updates, and documents are visible to the client. Do not assume that everything entered into a case should appear in the client dashboard.

# 4. One application, two dashboards

The application should have one shared platform and backend, but the dashboard shown depends on the authenticated user's role and permissions.

## 4.1 Lawyer dashboard structure

Possible main navigation:

- Overview

- My Cases

- Clients

- Create New Case

- Documents

- AI Case Analysis

- Legal Research

- Evidence Analysis

- Strategy Engine

- Opponent Analysis

- Hearing Calendar

- Case Timeline

- Tasks and Follow-ups

- Reports

- Notifications

- Account and Security Settings

Each case should have its own dedicated workspace.

## 4.2 Client dashboard structure

Possible main navigation:

- My Case

- Case Status

- Case Progress

- Upcoming Hearing

- My Tasks

- Shared Documents

- Lawyer Updates

- Notifications

- Account Settings

Keep the client dashboard simple. Do not show lawyer-only tools or internal AI functionality.

# 5. Client account creation and access

The lawyer should be able to create a client profile and provide the client with a secure way to join the platform.

The original concept was that the lawyer gives the client a unique ID and password so the client can log in. Implement this safely:

- The system can generate a unique client reference or invitation.

- The client should activate their account through a secure invitation process.

- The client should establish or securely receive authentication credentials.

- Never store passwords in plaintext.

- Never use a predictable client ID as a password.

- A client must be authenticated before accessing information.

- A client must be explicitly authorized for each case.

- A case ID or client ID alone must never grant access.

Prefer a permanent client account that can access more than one case if the lawyer has granted access to those cases. This avoids creating a separate account for every case.

# 6. Case creation and management

The lawyer should be able to create a new case and connect it to one or more clients.

Possible case information:

- Case title or internal reference.

- Case type or legal category.

- Court or jurisdiction, if known.

- Client or clients.

- Opposing party, where appropriate.

- Assigned lawyer or legal team.

- Case status.

- Important dates.

- Case description.

- Initial notes.

Every case should have a dedicated workspace containing:

- Case details.

- Client relationship and permissions.

- Original documents.

- Extracted text.

- Evidence items.

- Case timeline.

- Legal research.

- AI analysis.

- Strategies and scenario branches.

- Hearing records.

- Client-visible updates.

- Tasks and notifications.

- Audit history.

Support different case workflows. Do not assume all legal cases follow exactly the same stages.

# 7. Document upload: formats and input sources

The lawyer should be able to provide the AI with the client's documents and related materials.

Supported inputs should include:

- PDF documents.

- Word documents such as DOC and DOCX.

- Images and photographs such as JPG and PNG.

- Scanned documents.

- Photographs of hard-copy papers.

- Multiple documents uploaded together.

- Other formats when they can be processed securely and reliably.

Hard-copy documents are not directly machine-readable. The lawyer should scan or photograph them first, then upload the resulting files.

## 7.1 Document processing

For each uploaded document, the system should:

1. Validate file type, size, and security.

2. Store the original file securely.

3. Extract text from digital documents.

4. Apply OCR to scanned pages and photographs.

5. Preserve page numbers and document references.

6. Detect pages with poor or incomplete extraction.

7. Flag uncertain OCR or handwriting recognition.

8. Allow a lawyer to review and correct extracted text.

9. Organize the extracted content by case, document, and page.

10. Prepare meaningful text chunks for RAG retrieval.

11. Generate embeddings for supported chunks.

12. Attach source and access-control metadata to each chunk.

The original uploaded file remains the source document. Extracted text and embeddings are derived representations and must not replace the original.

# 8. AI document reading and case understanding

After documents are uploaded, the AI should read and analyze all available materials relevant to the case.

It should identify:

- Names of people and organizations.

- Dates and locations.

- Events and their sequence.

- Important statements and claims.

- Agreements, notices, records, and other relevant content.

- Potentially relevant evidence.

- Relationships between documents.

- Contradictions or inconsistencies.

- Missing documents or information.

- Facts that need clarification from the client.

- Potential legal issues that need research.

The AI should create a chronological timeline of relevant events.

For each finding, show the source document and page number where possible. Clearly distinguish what a document says from what the AI infers. A statement appearing in a document is not automatically a proven fact.

# 9. Bangladesh legal knowledge base

The AI must be designed for Bangladesh's legal system.

The legal knowledge base should include relevant and verifiable material such as:

- Constitution of Bangladesh.

- Acts and statutes.

- Codes and procedural laws.

- Rules and regulations.

- Relevant amendments and repeal information.

- Relevant Supreme Court and High Court judgments.

- Other relevant court decisions and legal precedents.

- Official legal notifications and authoritative publications.

The system should prioritize authentic and authoritative sources. It should record source identity, date, issuing authority or court, and legal status when available.

When analyzing a case, the AI should retrieve relevant legal material and explain:

- Which legal provisions may apply.

- Why they may be relevant.

- Which judgments may be relevant.

- What legal principles those judgments support.

- Whether a source's current status has been checked.

- Whether further legal research is needed.

The platform must not invent laws, sections, case names, judgment text, citations, or legal principles. If a source cannot be verified, the AI must say so.

The legal knowledge base needs an update process and version history so that amended or repealed laws are not mistakenly treated as current.

# 10. Initial legal case analysis

After reviewing the uploaded documents and relevant legal sources, the AI should prepare a structured case analysis for the lawyer.

The analysis should cover:

- The client's position as understood from the available information.

- Important factual issues.

- Important legal issues.

- Potentially applicable laws and sections.

- Relevant judgments and precedents.

- Evidence supporting the client's position.

- Evidence that may weaken the client's position.

- Contradictions.

- Missing evidence.

- Unanswered questions.

- Possible procedural issues.

- Potential risks.

- Areas requiring further investigation.

For every important conclusion, show the supporting document or legal source.

# 11. Chess-inspired legal strategy engine

This is the central and most distinctive feature of the product.

I want the AI to work somewhat like a chess engine when helping a lawyer consider possible strategies.

In chess:

- A player considers a move.

- The engine evaluates possible responses from the opponent.

- It explores several possible lines of play.

- It evaluates the strengths and weaknesses of those lines.

- It suggests a move based on the available position and its analysis.

The legal strategy engine should apply a similar structured method to legal case analysis.

## 11.1 Generate multiple strategies

The AI should not immediately choose one strategy without considering alternatives.

It should generate multiple legally plausible approaches based on:

- The case documents.

- Available evidence.

- Applicable Bangladesh laws.

- Relevant judgments.

- Procedural context.

- The client's objectives and constraints, as established by the lawyer.

## 11.2 Explore each strategy

For every strategy, analyze:

- Legal basis.

- Supporting facts and evidence.

- Relevant legal provisions.

- Relevant precedents.

- Strengths.

- Weaknesses.

- Missing evidence.

- Possible objections.

- Procedural risks.

- Practical obstacles.

- Potential consequences.

- Alternative approaches.

## 11.3 Consider the opposing side

For each proposed approach, explore plausible actions or arguments from the opposing side.

For example:

- What might the opposing lawyer argue?

- Which facts or documents might they challenge?

- Which legal objections might they raise?

- What evidence might they rely on?

- What weaknesses in the proposed strategy might they target?

- What counterarguments could the lawyer consider?

- What risks would remain after a counterargument?

Represent this as scenario branches, for example:

**Our legal approach → possible opposing argument → possible response → remaining risk.**

Do not claim to know exactly what the opposing lawyer will do. These are plausible scenarios, not certain predictions.

## 11.4 Compare and recommend

The AI should compare the available strategies in a clear dashboard or report.

For each option, show:

- Legal support.

- Evidence support.

- Strengths.

- Weaknesses.

- Opposing-side scenarios.

- Counterarguments.

- Risks.

- Missing information.

- Reasons for its overall assessment.

The AI may identify the strategy that appears best supported by the available facts and law, but it must explain its reasoning and uncertainty. The lawyer makes the final decision.

## 11.5 No fabricated win probability

The original vision includes showing the lawyer how strong a case or strategy may be and how different choices could affect the case. A chess-like evaluation may be useful, but court outcomes cannot be predicted with certainty.

Do not display an invented percentage such as a 90% or 95% chance of winning without a validated, calibrated, case-appropriate statistical model and a defensible dataset.

If a score is used, explain exactly what it measures. A score for evidence completeness or legal-source support must not be presented as the probability of winning.

Prefer transparent qualitative assessments such as strong, moderate, weak, or insufficient information, with clear reasons and limitations.

# 12. Lawyer strategy dashboard

Each case should have a dedicated strategy and analysis view.

It should present:

- Case overview.

- Current strategy.

- Alternative strategies.

- Strategy comparison.

- Supporting laws and judgments.

- Evidence supporting each strategy.

- Weaknesses and vulnerabilities.

- Possible opposing arguments.

- Possible counterarguments.

- Risks and obstacles.

- Missing evidence.

- Questions for further investigation.

- Recommended next steps for lawyer review.

- Analysis date and version.

- Changes from the previous analysis.

The lawyer should be able to understand why a strategy is recommended and what assumptions the analysis depends on.

# 13. Hearing updates and continuous strategy reassessment

The AI should continue assisting the lawyer throughout the case, not only at the beginning.

After every court hearing, the lawyer should be able to brief the AI by entering what happened.

The lawyer may record:

- Hearing date.

- What happened during the hearing.

- What the lawyer's side argued.

- What the opposing lawyer argued.

- Questions or observations from the judge, as recorded by the lawyer.

- Whether new evidence or documents were presented.

- Objections or procedural developments.

- Any order or direction, if known.

- The next hearing date, if confirmed.

- Follow-up tasks.

After the lawyer submits the hearing update, the AI should:

1. Add the new information to the case timeline.

2. Preserve the original hearing note and its author.

3. Distinguish lawyer-entered notes from independently verified court records.

4. Analyze how the new information affects the case.

5. Compare the new position with the previous analysis.

6. Reevaluate the current strategy.

7. Consider new plausible opposing-side responses.

8. Identify new risks, opportunities, and evidence needs.

9. Recommend whether the existing strategy should be maintained or reviewed.

10. Explain any suggested strategy change and why it may matter.

11. Update the lawyer dashboard.

12. Prepare a separate client-friendly update only if the lawyer approves it.

The platform must preserve earlier analyses and strategy versions. Do not silently overwrite the history.

# 14. Client progress and hearing information

The client dashboard should show the information the client needs from their own perspective.

For example:

- What stage the case is currently at.

- General progress.

- Whether a hearing has taken place.

- The next hearing date, if confirmed.

- Whether the client needs to attend court.

- Whether the client needs to provide a document or take another action.

- Important updates approved by the lawyer.

The system must not automatically turn an AI prediction into a confirmed hearing date, court order, or client instruction. Confirmed dates and instructions should be entered or verified by an authorized person.

The lawyer should be able to write or approve a client-friendly explanation rather than exposing internal legal analysis.

# 15. Case closure and client access deactivation

When a case is finished, the lawyer should be able to mark it as closed.

The intended behavior is:

1. Lawyer marks the case closed.

2. Client access to that case is deactivated or restricted according to the configured policy.

3. The client can no longer view that case through the portal if access has been deactivated.

4. The lawyer retains authorized access to the case history and records.

5. Original documents and case data remain protected in storage according to the applicable retention policy.

6. Other active cases belonging to the same client are not affected.

7. Any permanent deletion must follow an explicit authorized process and applicable retention obligations.

Do not delete the client's entire account merely because one case is closed. Do not assume that deleting a login or disabling portal access means the underlying case data should be deleted.

# 16. RAG and vector database architecture

I want to use a RAG-like architecture so the AI can retrieve relevant information from case documents and the Bangladesh legal knowledge base.

A typical document RAG flow should be:

**Upload original file → secure storage → text extraction/OCR → text cleaning → chunking → embeddings → vector storage with metadata → permission-filtered retrieval → AI analysis with source references.**

The platform should support two logically distinct knowledge areas:

1. **Private case knowledge:** documents and information belonging to a particular case and its authorized users.

2. **Shared legal reference knowledge:** verified Bangladesh legal materials that can be used across cases according to the platform's permissions and licensing.

Every private chunk must carry metadata such as:

- Organization or lawyer ID.

- Case ID.

- Client relationship where appropriate.

- Document ID.

- Page number or source location.

- Processing and embedding version.

- Access classification.

Enforce permissions at retrieval time. A vector search must never expose another lawyer's or client's confidential case information because the text happens to be semantically similar.

The vector database is for retrieval, not the primary archive. Store original documents securely and keep authoritative case records and access permissions in a suitable database.

Support reprocessing, versioning, retention, and authorized deletion of chunks and embeddings when source documents change or must be removed.

# 17. Accuracy, verification, and uncertainty

I want the option analysis to be as accurate and reliable as technically possible. The system should not produce confident-sounding guesses.

It must:

- Verify legal citations against authoritative sources where possible.

- Check whether laws have been amended or repealed.

- Verify that cited judgments exist and support the stated point.

- Check whether factual claims are supported by the correct case documents.

- Identify unsupported assumptions.

- Detect contradictions.

- Flag missing information.

- Identify low-confidence OCR.

- Distinguish facts, claims, interpretations, assumptions, and predictions.

- Explain when sources disagree.

- State when it cannot verify a conclusion.

- Keep source references for important conclusions.

Use a separate verification stage or component to check important AI outputs. A separate verifier can catch errors but cannot guarantee correctness by itself. The lawyer must review important legal analysis.

The target is maximum achievable reliability, not a false guarantee of 100% accuracy. It is better for the AI to say that there is insufficient information than to invent an answer.

# 18. AI architecture and specialized agents

The system may use multiple specialized AI components or agents, coordinated by an orchestrator.

Possible responsibilities:

- Document extraction and classification.

- Case fact and timeline analysis.

- Bangladesh legal research and retrieval.

- Evidence analysis.

- Contradiction and missing-information detection.

- Strategy generation.

- Opposing-side scenario analysis.

- Strategy comparison.

- Independent verification.

- Client-friendly update drafting.

These can be separate agents, services, or carefully separated workflow stages. Do not add multiple agents merely for appearance. Use them where they improve traceability, reliability, or maintainability.

Do not train a new large language model from scratch as the first step. Start with a suitable existing model and build the legal knowledge retrieval, document-processing, permissions, evaluation, and strategy workflows around it. Model choice should be based on actual testing, cost, privacy, and quality.

# 19. Security, confidentiality, and data protection

The platform will process confidential legal and personal information. Security must be designed into the system from the beginning.

Requirements:

- Secure authentication.

- Role-based access control.

- Case-level permissions.

- Strong password hashing through a trusted authentication system.

- Secure account recovery and invitations.

- Encryption in transit and at rest.

- Private file storage.

- Short-lived authorized download links where appropriate.

- Audit logs for sensitive actions.

- Secure backups and recovery.

- Rate limiting and abuse protection.

- Data retention and deletion controls.

- Protection against cross-case data leakage.

- Authorization checks on the backend, not only in the frontend.

The lawyer, client, and any legal team member must only see information they are authorized to access.

Do not send confidential client data to an external AI provider until its data-handling terms, retention settings, and security controls have been reviewed. Do not use client documents for model training without explicit authorization, an appropriate lawful basis, and safeguards.

# 20. Suggested database entities

The architecture should consider entities such as:

- Users

- LawyerProfiles

- ClientProfiles

- Cases

- CaseMembers

- CaseInvitations

- Documents

- ExtractedPages

- DocumentChunks

- EmbeddingReferences

- LegalSources

- LegalSourceVersions

- EvidenceItems

- CaseFacts

- CaseEvents

- Hearings

- HearingUpdates

- LegalResearchResults

- Strategies

- StrategyScenarios

- StrategyComparisons

- AIAnalyses

- VerificationResults

- ClientVisibleUpdates

- Tasks

- Notifications

- AuditLogs

The coding agent should design the actual relational schema, constraints, indexes, and relationships after reviewing the requirements. Do not treat this suggested list as a final schema without analysis.

# 21. Interface and design expectations

The application should be professional, modern, clear, and responsive.

The lawyer dashboard can contain detailed information but should be organized so a lawyer can quickly understand a case. The client dashboard should be much simpler and should avoid confusing legal or AI terminology.

Use clear visual distinctions for:

- Confirmed case information.

- Lawyer-entered notes.

- AI-generated analysis.

- Unverified information.

- Upcoming dates.

- Completed tasks.

- Risks and unresolved questions.

- Client-approved updates.

Do not make an AI-generated prediction look like an official court decision or confirmed legal fact.

# 22. Development instructions for the AI coding agent

Read this entire document before writing code.

Do not immediately generate the entire application in one step.

First inspect the existing project, if one exists. Preserve useful existing work and do not overwrite files without understanding them.

Before implementation, provide:

1. A concise explanation of your understanding of the product.

2. A proposed system architecture.

3. Recommended frontend, backend, database, authentication, file storage, OCR, vector database, and AI technologies.

4. Reasons and trade-offs for each technology choice.

5. A database and permission design.

6. A document-processing and RAG design.

7. A strategy-analysis workflow.

8. A security and privacy plan.

9. A phased implementation roadmap.

10. Key risks, dependencies, and unresolved questions.

Do not claim a feature works until it has been implemented and tested. Do not use fake legal data or invented judgments. If an external service, legal dataset, API key, or provider is unavailable, explain the dependency and provide a clearly labelled integration boundary rather than pretending it is functional.

Build modules incrementally. After each module:

- Run tests.

- Fix errors.

- Check authorization.

- Test case and client data isolation.

- Check that existing features still work.

- Document what is complete and what remains.

Keep code modular, maintainable, and documented. Use environment variables for secrets. Do not commit API keys or passwords.

# 23. Suggested development phases

The coding agent may adjust the order after architecture review, but should consider this sequence.

## Phase 1: Foundation

- Project setup.

- Authentication.

- Lawyer and client roles.

- Database foundation.

- Case creation.

- Case-level authorization.

## Phase 2: Two dashboards

- Lawyer dashboard.

- Client dashboard.

- Client invitation and account activation.

- Per-case client access.

- Lawyer-controlled client-visible updates.

- Case closure and access deactivation.

## Phase 3: Case and document management

- Case workspace.

- Secure document uploads.

- Original file storage.

- PDF and Word extraction.

- OCR for images and scans.

- Page references and extraction review.

## Phase 4: RAG and legal knowledge

- Text chunking.

- Embeddings.

- Vector database integration.

- Metadata and permission-filtered retrieval.

- Bangladesh legal source ingestion.

- Source verification and version tracking.

## Phase 5: Case analysis

- Case summaries.

- Fact extraction.

- Timeline generation.

- Evidence organization.

- Contradiction and missing-information checks.

- Cited legal research.

## Phase 6: Chess-inspired strategy engine

- Multiple strategy generation.

- Strategy evaluation.

- Opposing-side scenario branches.

- Counterargument analysis.

- Risk and alternative comparison.

- Independent verification.

- Lawyer review and approval.

## Phase 7: Hearings and continuous updates

- Hearing calendar and records.

- Hearing update workflow.

- Case timeline updates.

- Strategy reassessment.

- Strategy history and versioning.

- Client-approved progress updates.

## Phase 8: Security and production readiness

- Security testing.

- Privacy review.

- Cross-case isolation tests.

- Performance testing.

- Backups and recovery.

- Monitoring.

- Deployment and operating documentation.

# 24. Definition of a successful product

The product should ultimately allow a lawyer to:

1. Create a case and connect the correct client.

2. Upload the client's PDFs, photographs, scans, and other supported documents.

3. Have the AI extract and organize the information with source references.

4. Retrieve relevant Bangladesh laws and judgments from verifiable sources.

5. Review an evidence-based case analysis.

6. Compare multiple legal strategies.

7. Explore plausible opposing arguments and possible responses.

8. Understand risks, weaknesses, missing evidence, and uncertainty.

9. Record what happened at each hearing.

10. Receive an updated analysis when new case information is entered.

11. Decide what progress information the client can see.

12. Close the case while retaining protected historical records and managing client access correctly.

The client should be able to sign in securely and see only their own authorized case information, progress, upcoming confirmed hearing details, tasks, and lawyer-approved updates.

The platform must protect confidential information, cite its sources, preserve analysis history, and never pretend that uncertain legal outcomes are guaranteed.

for tech stack 

in frontend will use next js

in backend Python and fast api

for database PostgreSQL and Pgvector

also openapi or restapi (more suitale with project) 

