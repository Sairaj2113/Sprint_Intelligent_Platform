"""Synthetic development data for the Sprint Intelligence Platform.

The Bank Loan Jira history in this module is fictional demo data inspired by
the project requirements. It is not a record of verified employee activity,
dates, test results, or deployments.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Comment, Deployment, Employee, Issue, IssueHistory
from app.models import Project, ProjectMember, Sprint, TestResult
from app.models.deployment import DeploymentStatus
from app.models.issue import IssuePriority, IssueStatus, IssueType
from app.models.project import ProjectMethodology, ProjectStatus
from app.models.sprint import SprintStatus
from app.models.test_result import TestingStatus


@dataclass(frozen=True)
class SprintSeed:
    name: str
    goal: str
    status: SprintStatus
    start_date: dt.date
    end_date: dt.date
    started_at: dt.datetime
    completed_at: dt.datetime | None


@dataclass(frozen=True)
class IssueSeed:
    key: str
    title: str
    issue_type: IssueType
    status: IssueStatus
    sprint_name: str
    assignee_code: str
    reporter_code: str
    story_points: int
    description: str
    acceptance_criteria: str
    technical_notes: str
    parent_key: str | None = None


SYNTHETIC_EMPLOYEES = (
    ("EMP001", "Sairaj Pankar", "sairajpankar@gmail.com", "Software / AI Engineer", "Engineering"),
    ("EMP002", "Anjali Sharma", "anjali.sharma@example.test", "Data Engineer", "Data"),
    ("EMP003", "Rohan Patil", "rohan.patil@example.test", "ML Engineer", "AI/ML"),
    ("EMP004", "Sneha Kulkarni", "sneha.kulkarni@example.test", "Frontend Engineer", "Engineering"),
    ("EMP005", "Neha Mehta", "neha.mehta@example.test", "Backend Engineer", "Engineering"),
    ("EMP006", "Aditya Tiwari", "aditya.tiwari@example.test", "QA Engineer", "Quality Engineering"),
)

SPRINT_SEEDS = (
    SprintSeed("Foundation and Risk Model", "Establish project architecture, customer data processing, feature engineering and initial LightGBM risk model.", SprintStatus.COMPLETED, dt.date(2026, 6, 2), dt.date(2026, 6, 13), dt.datetime(2026, 6, 2, 9, tzinfo=dt.UTC), dt.datetime(2026, 6, 13, 17, tzinfo=dt.UTC)),
    SprintSeed("Assessment API and Dashboard", "Build customer assessment workflows, prediction persistence, FastAPI services and Streamlit reporting.", SprintStatus.COMPLETED, dt.date(2026, 6, 16), dt.date(2026, 6, 27), dt.datetime(2026, 6, 16, 9, tzinfo=dt.UTC), dt.datetime(2026, 6, 27, 17, tzinfo=dt.UTC)),
    SprintSeed("Production Hardening", "Improve authentication, transaction safety, analytics correctness, testing, model governance and deployment readiness.", SprintStatus.ACTIVE, dt.date(2026, 6, 30), dt.date(2026, 7, 11), dt.datetime(2026, 6, 30, 9, tzinfo=dt.UTC), None),
)

# Key, title, type, final status, sprint, assignee, reporter, points, description,
# acceptance criteria, technical notes, parent key. All entries are synthetic.
ISSUE_SEEDS = (
    IssueSeed("BLI-1", "Data and Feature Engineering", IssueType.EPIC, IssueStatus.DONE, "Foundation and Risk Model", "EMP002", "EMP001", 8, "Prepare reliable customer data and reusable risk features.", "Data inputs are mapped and feature outputs are reproducible.", "Synthetic epic used to group foundation data work."),
    IssueSeed("BLI-2", "Prepare customer loan dataset", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP002", "EMP001", 5, "Prepare a normalized training dataset from loan customer records.", "Dataset has documented columns, target label and quality checks.", "Use a versioned preparation script with deterministic output.", "BLI-1"),
    IssueSeed("BLI-3", "Map input schema to model contract", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP002", "EMP005", 3, "Map customer attributes to the model input contract.", "Required fields and compatible data types are validated.", "Maintain one mapping shared by batch and API paths.", "BLI-1"),
    IssueSeed("BLI-4", "Handle missing values and categorical encoding", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP002", 5, "Implement missing-value treatment and categorical feature encoding.", "Transformations handle nulls without changing feature order.", "Persist encoder configuration with the training artifact.", "BLI-1"),
    IssueSeed("BLI-5", "Derive financial risk features", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP001", 5, "Derive income, debt and repayment risk signals for model training.", "Derived features are documented and available in training data.", "Keep formulas deterministic and auditable.", "BLI-1"),
    IssueSeed("BLI-6", "Verify training-serving feature parity", IssueType.TASK, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP006", 3, "Check that online inference produces training-equivalent features.", "Parity tests pass for representative customer payloads.", "Compare named feature vectors before model invocation.", "BLI-5"),
    IssueSeed("BLI-7", "ML Risk Prediction", IssueType.EPIC, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP001", 8, "Train, evaluate and serve a repeatable loan default risk model.", "A versioned model returns deterministic risk categories.", "Synthetic epic for risk-model delivery work."),
    IssueSeed("BLI-8", "Build LightGBM training pipeline", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP001", 5, "Create a repeatable LightGBM training pipeline.", "Pipeline trains from prepared features and records configuration.", "Parameterize training inputs and random seed.", "BLI-7"),
    IssueSeed("BLI-9", "Handle class imbalance and evaluate ROC-AUC", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP006", 5, "Evaluate imbalance treatment and ROC-AUC for the candidate model.", "Evaluation includes ROC-AUC and class-distribution context.", "Use a held-out validation split for this synthetic demo.", "BLI-7"),
    IssueSeed("BLI-10", "Record model artifact and version metadata", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP001", 3, "Store model artifact identifiers and training metadata.", "Version, feature set and evaluation metadata are recorded.", "Keep provenance fields adjacent to the artifact reference.", "BLI-7"),
    IssueSeed("BLI-11", "Define deterministic risk thresholds", IssueType.STORY, IssueStatus.DONE, "Foundation and Risk Model", "EMP003", "EMP005", 3, "Map scores to LOW, MEDIUM and HIGH risk bands.", "Boundary scores produce stable, documented labels.", "Apply thresholds in one shared inference utility.", "BLI-7"),
    IssueSeed("BLI-12", "Load model and run inference", IssueType.TASK, IssueStatus.DONE, "Foundation and Risk Model", "EMP001", "EMP003", 3, "Load the approved model artifact and expose inference integration.", "A valid feature payload produces a score and risk band.", "Load once per process and reject incompatible schemas.", "BLI-8"),
    IssueSeed("BLI-13", "FastAPI and Persistence", IssueType.EPIC, IssueStatus.DONE, "Assessment API and Dashboard", "EMP005", "EMP001", 8, "Deliver assessment APIs and safe persistence for customer predictions.", "Customer queries and saved predictions work through the service layer.", "Synthetic epic for service and database integration."),
    IssueSeed("BLI-14", "Implement customer search and detail APIs", IssueType.STORY, IssueStatus.DONE, "Assessment API and Dashboard", "EMP005", "EMP004", 5, "Provide customer search and detail endpoints.", "Search returns scoped matches and detail validates the identifier.", "Use request schemas and predictable error responses.", "BLI-13"),
    IssueSeed("BLI-15", "Implement stateless and saved prediction APIs", IssueType.STORY, IssueStatus.DONE, "Assessment API and Dashboard", "EMP005", "EMP001", 5, "Support one-off and saved customer predictions.", "Both endpoints return risk output and saved predictions retain customer links.", "Keep stateless requests free of unintended persistence.", "BLI-13"),
    IssueSeed("BLI-16", "Persist predictions with atomic transactions", IssueType.STORY, IssueStatus.DONE, "Assessment API and Dashboard", "EMP005", "EMP002", 5, "Persist application and prediction records as one transaction.", "Partial writes roll back when persistence fails.", "Use one session boundary for each write workflow.", "BLI-13"),
    IssueSeed("BLI-17", "Validate requests and expose service health", IssueType.TASK, IssueStatus.DONE, "Assessment API and Dashboard", "EMP005", "EMP006", 3, "Add request validation plus health and model-information responses.", "Invalid requests receive errors and health reports service state.", "Separate liveness from model metadata reporting.", "BLI-16"),
    IssueSeed("BLI-18", "Dashboard and Analytics", IssueType.EPIC, IssueStatus.DONE, "Assessment API and Dashboard", "EMP004", "EMP001", 8, "Provide Streamlit workflows and risk analytics for demo users.", "Dashboard supports customer review and risk-distribution reporting.", "Synthetic epic for dashboard delivery work."),
    IssueSeed("BLI-19", "Build Streamlit customer search and prediction UI", IssueType.STORY, IssueStatus.DONE, "Assessment API and Dashboard", "EMP004", "EMP005", 5, "Create customer search and prediction input flows in Streamlit.", "Users can find a customer and submit a prediction form.", "Keep API calls behind a small client wrapper.", "BLI-18"),
    IssueSeed("BLI-20", "Show prediction history and risk distribution", IssueType.STORY, IssueStatus.DONE, "Assessment API and Dashboard", "EMP004", "EMP003", 5, "Display prediction history and aggregate risk analytics.", "Views reflect the selected reporting scope.", "Use server-provided filters before chart aggregation.", "BLI-18"),
    IssueSeed("BLI-21", "Fix pagination and reporting scope regression", IssueType.BUG, IssueStatus.DONE, "Assessment API and Dashboard", "EMP004", "EMP006", 3, "Correct a synthetic pagination issue that mixed reporting scopes.", "Changing pages preserves reporting filters and counts.", "Regression test scoped queries and UI pagination together.", "BLI-20"),
    IssueSeed("BLI-22", "Production Hardening", IssueType.EPIC, IssueStatus.IN_PROGRESS, "Production Hardening", "EMP001", "EMP005", 8, "Harden authentication, governance, testing and deployment practices.", "Priority hardening controls are tracked without implying all are complete.", "Synthetic epic for proposed and partial production work."),
    IssueSeed("BLI-23", "Add authentication and role authorization", IssueType.STORY, IssueStatus.IN_PROGRESS, "Production Hardening", "EMP005", "EMP001", 5, "Protect assessment workflows with authentication and role checks.", "Protected routes reject unauthenticated and unauthorized requests.", "Keep role policy decisions in a dedicated authorization layer.", "BLI-22"),
    IssueSeed("BLI-24", "Manage secrets and add audit logging", IssueType.TASK, IssueStatus.CODE_REVIEW, "Production Hardening", "EMP005", "EMP001", 5, "Move sensitive configuration to managed inputs and record audit events.", "No secret values are logged and events include actor and action context.", "Use environment-backed configuration and structured events.", "BLI-23"),
    IssueSeed("BLI-25", "Make prediction requests idempotent with provenance", IssueType.TASK, IssueStatus.TESTING, "Production Hardening", "EMP001", "EMP003", 5, "Prevent duplicate saved predictions and attach model provenance.", "Repeated request keys do not create duplicates and responses include model version.", "Persist an idempotency key with model metadata.", "BLI-23"),
    IssueSeed("BLI-26", "Create CI test database and recovery checks", IssueType.STORY, IssueStatus.TODO, "Production Hardening", "EMP006", "EMP001", 5, "Add isolated CI database tests and deployment recovery checks.", "CI exercises migrations, rollback behavior and a recovery checklist.", "Use disposable PostgreSQL services in the pipeline.", "BLI-22"),
)

RETAIL_SPRINT_SEEDS = (
    SprintSeed("Conversational Search Foundation", "Establish Dialogflow intent handling, FastAPI webhook integration, SentenceTransformer embeddings and semantic product retrieval.", SprintStatus.COMPLETED, dt.date(2026, 7, 14), dt.date(2026, 7, 25), dt.datetime(2026, 7, 14, 9, tzinfo=dt.UTC), dt.datetime(2026, 7, 25, 17, tzinfo=dt.UTC)),
    SprintSeed("Cart and Order Workflow", "Implement session-based cart behavior, add/remove operations, order persistence and order tracking workflows.", SprintStatus.COMPLETED, dt.date(2026, 7, 28), dt.date(2026, 8, 8), dt.datetime(2026, 7, 28, 9, tzinfo=dt.UTC), dt.datetime(2026, 8, 8, 17, tzinfo=dt.UTC)),
    SprintSeed("Reliability and Release Hardening", "Improve session isolation, order correctness, retrieval safety, relevance evaluation, webhook reliability and deployment readiness.", SprintStatus.ACTIVE, dt.date(2026, 8, 11), dt.date(2026, 8, 22), dt.datetime(2026, 8, 11, 9, tzinfo=dt.UTC), None),
)

RETAIL_ISSUE_SEEDS = (
    IssueSeed("RD-1", "Dialogflow Conversation Layer", IssueType.EPIC, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP001", 8, "Deliver the Dialogflow conversation layer for the retail assistant.", "Supported intents produce safe fulfillment paths.", "Synthetic epic for conversational workflow delivery."),
    IssueSeed("RD-2", "Configure supported intent routes and product parameters", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP004", 5, "Configure search, detail, cart and tracking intent routes.", "Product parameters are extracted and passed to fulfillment.", "Keep route names and parameter contracts centralized.", "RD-1"),
    IssueSeed("RD-3", "Extract quantities and maintain order contexts", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP001", 5, "Extract quantities and maintain ongoing-order Dialogflow contexts.", "Quantity updates preserve the active shopper conversation.", "Use explicit session-scoped context keys.", "RD-1"),
    IssueSeed("RD-4", "Handle fallback and clarification conversations", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP004", "EMP006", 3, "Provide fallback messaging and clarification prompts for uncertain intents.", "Unknown requests ask for clarification without creating orders.", "Return fulfillment responses through a shared template layer.", "RD-1"),
    IssueSeed("RD-5", "Fix unsafe handling when output context is missing", IssueType.BUG, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP006", 3, "Correct a synthetic prototype gap when Dialogflow output context is absent.", "Missing context starts a safe session path rather than reusing state.", "Treat absent context as untrusted input.", "RD-4"),
    IssueSeed("RD-6", "Preserve conversation session continuity", IssueType.TASK, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP004", 3, "Keep session continuity across multi-turn product and cart requests.", "Follow-up turns retain only the correct shopper state.", "Use Dialogflow session identifiers in the webhook state boundary.", "RD-3"),
    IssueSeed("RD-7", "FastAPI Webhook", IssueType.EPIC, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP001", 8, "Provide a robust FastAPI fulfillment webhook for Dialogflow.", "Webhook routes validate and dispatch supported intents.", "Synthetic epic for webhook service work."),
    IssueSeed("RD-8", "Implement webhook dispatcher and envelope validation", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP001", 5, "Dispatch Dialogflow webhook requests after validating their envelopes.", "Malformed webhook payloads receive safe error fulfillments.", "Use Pydantic request models and an intent dispatcher.", "RD-7"),
    IssueSeed("RD-9", "Handle missing parameters and centralize fulfillments", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP004", 3, "Handle missing parameters without unsafe assumptions.", "Responses consistently request the information needed to continue.", "Centralize fulfillment formatting for all intent paths.", "RD-7"),
    IssueSeed("RD-10", "Add webhook exceptions and readiness checks", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP005", "EMP006", 3, "Add exception handling plus health and readiness endpoints.", "Dependency failures return safe webhook responses and readiness is observable.", "Avoid exposing internal exception details to the shopper.", "RD-7"),
    IssueSeed("RD-11", "Semantic Product Retrieval", IssueType.EPIC, IssueStatus.DONE, "Conversational Search Foundation", "EMP003", "EMP001", 8, "Provide semantic product discovery for conversational queries.", "Search returns relevant product candidates with safe fallbacks.", "Synthetic epic for embedding and retrieval work."),
    IssueSeed("RD-12", "Load all-MiniLM-L6-v2 and generate embeddings", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP003", "EMP001", 5, "Integrate all-MiniLM-L6-v2 for 384-dimensional product embeddings.", "Product and query embeddings have the expected dimension.", "Load the SentenceTransformer once per service process.", "RD-11"),
    IssueSeed("RD-13", "Search semantically and retrieve product details", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP003", "EMP004", 5, "Retrieve top semantic matches and product details for a shopper query.", "Shortlisted results include stable product identifiers and useful metadata.", "Separate query embedding, vector search and response shaping.", "RD-11"),
    IssueSeed("RD-14", "Evaluate relevance thresholds for nearest matches", IssueType.TASK, IssueStatus.IN_PROGRESS, "Reliability and Release Hardening", "EMP003", "EMP006", 5, "Evaluate thresholds that prevent unrelated nearest products from being selected.", "Low-confidence queries ask for refinement instead of selecting unrelated products.", "Record candidate scores for synthetic evaluation only.", "RD-11"),
    IssueSeed("RD-15", "Pinecone Product Index", IssueType.EPIC, IssueStatus.DONE, "Conversational Search Foundation", "EMP001", "EMP002", 8, "Define and populate the Pinecone product index used by retrieval.", "The nykaa-products contract supports stable product discovery.", "Synthetic epic for product-index delivery."),
    IssueSeed("RD-16", "Define nykaa-products metadata and stable IDs", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP002", "EMP001", 5, "Define product metadata mapping with stable product and variant IDs.", "Each indexed vector has a stable identity and mapped metadata.", "Do not reuse vector IDs across product variants.", "RD-15"),
    IssueSeed("RD-17", "Build ingestion, dimension validation and deduplication", IssueType.STORY, IssueStatus.DONE, "Conversational Search Foundation", "EMP002", "EMP003", 5, "Ingest catalog vectors with 384-dimension checks and query deduplication.", "Invalid dimensions fail before indexing and duplicate results are removed.", "Validate vector shape at the ingestion boundary.", "RD-15"),
    IssueSeed("RD-18", "Add future brand, category and budget filters", IssueType.TASK, IssueStatus.TODO, "Reliability and Release Hardening", "EMP002", "EMP004", 3, "Plan metadata filters for brand, category and budget constrained discovery.", "Filters compose with semantic search without hiding relevant products.", "Keep filter schema compatible with Pinecone metadata.", "RD-17"),
    IssueSeed("RD-19", "Cart and Order Workflow", IssueType.EPIC, IssueStatus.DONE, "Cart and Order Workflow", "EMP005", "EMP001", 8, "Deliver session-based cart, order persistence and tracking workflows.", "Shoppers can manage complete orders safely.", "Synthetic epic for cart and order delivery."),
    IssueSeed("RD-20", "Implement cart add, remove and quantity handling", IssueType.STORY, IssueStatus.DONE, "Cart and Order Workflow", "EMP005", "EMP004", 5, "Support cart add, decrement, removal and quantity validation.", "Cart totals and line quantities update predictably.", "Scope cart state to the shopper session.", "RD-19"),
    IssueSeed("RD-21", "Review and persist complete multi-line orders", IssueType.STORY, IssueStatus.DONE, "Cart and Order Workflow", "EMP005", "EMP002", 5, "Review carts before confirmation and persist every order line.", "Confirmed orders contain all selected products and quantities.", "Persist an order header and line collection atomically.", "RD-19"),
    IssueSeed("RD-22", "Generate references and retrieve order status", IssueType.STORY, IssueStatus.DONE, "Cart and Order Workflow", "EMP005", "EMP004", 5, "Generate stable order references and support status tracking.", "A shopper can retrieve the status of an owned order reference.", "Use exact order identifiers before semantic fallback.", "RD-19"),
    IssueSeed("RD-23", "Fix multi-line order overwrite from reused vector IDs", IssueType.BUG, IssueStatus.DONE, "Cart and Order Workflow", "EMP005", "EMP006", 3, "Correct a synthetic bug where reused vector IDs overwrote order lines.", "Distinct products and variants remain separate persisted lines.", "Use a unique order-line key rather than a shared vector ID.", "RD-21"),
    IssueSeed("RD-24", "Prevent empty cart completion", IssueType.BUG, IssueStatus.DONE, "Cart and Order Workflow", "EMP005", "EMP006", 2, "Prevent a synthetic prototype path from completing an empty cart.", "Empty carts return a clarification response and create no order.", "Validate line count immediately before confirmation.", "RD-20"),
    IssueSeed("RD-25", "Block order flow for unmatched products", IssueType.BUG, IssueStatus.DONE, "Cart and Order Workflow", "EMP003", "EMP006", 3, "Prevent unmatched product queries from reaching a successful order flow.", "No order path is offered until a valid product is selected.", "Propagate retrieval confidence into fulfillment decisions.", "RD-13"),
    IssueSeed("RD-26", "Fix global-most-recent order ownership lookup", IssueType.BUG, IssueStatus.TESTING, "Reliability and Release Hardening", "EMP005", "EMP006", 5, "Replace a synthetic global maximum order lookup with shopper-owned retrieval.", "Most recent orders are selected only within the requesting shopper scope.", "Filter by shopper identity before sorting by creation time.", "RD-22"),
    IssueSeed("RD-27", "Expand order tracking beyond first ten similarity matches", IssueType.BUG, IssueStatus.CODE_REVIEW, "Reliability and Release Hardening", "EMP005", "EMP006", 3, "Correct a synthetic tracking limitation that searched only ten similarity matches.", "Tracking finds the exact owned order even when it is outside a shallow shortlist.", "Prefer exact reference lookup over similarity ranking.", "RD-22"),
    IssueSeed("RD-28", "Reliability and Release Hardening", IssueType.EPIC, IssueStatus.IN_PROGRESS, "Reliability and Release Hardening", "EMP001", "EMP005", 8, "Harden session isolation, retries, observability and release controls.", "Hardening items are tracked without claiming all proposed controls are complete.", "Synthetic epic for proposed reliability work."),
    IssueSeed("RD-29", "Add session isolation, exact retrieval and idempotency", IssueType.STORY, IssueStatus.TESTING, "Reliability and Release Hardening", "EMP005", "EMP001", 5, "Add session isolation, ownership checks and duplicate confirmation protection.", "Concurrent shoppers cannot share carts and retries do not duplicate orders.", "Use scoped session keys and idempotency tokens.", "RD-28"),
    IssueSeed("RD-30", "Harden webhook authentication, retries and latency tests", IssueType.STORY, IssueStatus.TODO, "Reliability and Release Hardening", "EMP001", "EMP006", 5, "Add webhook authentication, dependency retry safety, secret management and latency instrumentation.", "Webhook access is protected and recovery/load checks are automated.", "Keep secrets outside source and emit latency metrics.", "RD-28"),
)


def clear_seed_data() -> None:
    """Clear all application data in foreign-key-safe order for local development."""
    session = SessionLocal()
    try:
        print("Clearing development seed data...")
        for model in (Comment, Deployment, IssueHistory, TestResult, Issue, ProjectMember, Sprint, Project, Employee):
            session.execute(delete(model))
        session.commit()
        print("Development seed data cleared")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_or_create_employee(session: Session, data: tuple[str, str, str, str, str]) -> Employee:
    code, name, email, role, department = data
    employee = session.scalar(select(Employee).where(Employee.employee_code == code))
    if employee is None:
        employee = Employee(employee_code=code, name=name, email=email, role=role, department=department, is_active=True)
        session.add(employee)
    else:
        employee.name, employee.email = name, email
        employee.role, employee.department, employee.is_active = role, department, True
    session.flush()
    return employee


def _get_or_create_project(
    session: Session, project_key: str, name: str, description: str, lead: Employee
) -> Project:
    project = session.scalar(select(Project).where(Project.project_key == project_key))
    values = {"name": name, "description": description, "methodology": ProjectMethodology.SCRUM, "status": ProjectStatus.ACTIVE, "project_lead_id": lead.id}
    if project is None:
        project = Project(project_key=project_key, **values)
        session.add(project)
    else:
        for field, value in values.items():
            setattr(project, field, value)
    session.flush()
    return project


def _get_or_create_sprint(session: Session, project: Project, data: SprintSeed) -> Sprint:
    sprint = session.scalar(select(Sprint).where(Sprint.project_id == project.id, Sprint.name == data.name))
    values = {"goal": data.goal, "status": data.status, "start_date": data.start_date, "end_date": data.end_date, "started_at": data.started_at, "completed_at": data.completed_at}
    if sprint is None:
        sprint = Sprint(project_id=project.id, name=data.name, **values)
        session.add(sprint)
    else:
        for field, value in values.items():
            setattr(sprint, field, value)
    session.flush()
    return sprint


def _clear_project_issue_data(session: Session, project: Project) -> None:
    """Clear one project's issue descendants before deterministic rebuilding."""
    issue_ids = select(Issue.id).where(Issue.project_id == project.id)
    for model in (Comment, Deployment, IssueHistory, TestResult):
        session.execute(delete(model).where(model.issue_id.in_(issue_ids)))
    session.execute(delete(Issue).where(Issue.project_id == project.id))
    session.flush()


def _get_or_create_issue(session: Session, data: IssueSeed, project: Project, sprints: dict[str, Sprint], employees: dict[str, Employee], issues: dict[str, Issue]) -> Issue:
    sprint = sprints[data.sprint_name]
    values = {"project_id": project.id, "sprint_id": sprint.id, "assignee_id": employees[data.assignee_code].id, "reporter_id": employees[data.reporter_code].id, "parent_issue_id": issues[data.parent_key].id if data.parent_key else None, "issue_type": data.issue_type, "title": data.title, "description": data.description, "priority": IssuePriority.MEDIUM, "story_points": data.story_points, "status": data.status, "acceptance_criteria": data.acceptance_criteria, "technical_notes": data.technical_notes, "start_date": sprint.start_date, "due_date": sprint.end_date}
    issue = session.scalar(select(Issue).where(Issue.issue_key == data.key))
    if issue is None:
        issue = Issue(issue_key=data.key, **values)
        session.add(issue)
    else:
        for field, value in values.items():
            setattr(issue, field, value)
    session.flush()
    return issue


def _history_states(issue: Issue) -> list[IssueStatus]:
    if issue.status is IssueStatus.TODO:
        return [IssueStatus.TODO]
    if issue.status is IssueStatus.IN_PROGRESS:
        return [IssueStatus.TODO, IssueStatus.IN_PROGRESS]
    if issue.status is IssueStatus.CODE_REVIEW:
        return [IssueStatus.TODO, IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW]
    if issue.status is IssueStatus.TESTING:
        return [IssueStatus.TODO, IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW, IssueStatus.TESTING]
    if issue.issue_type is IssueType.BUG:
        return [IssueStatus.TODO, IssueStatus.IN_PROGRESS, IssueStatus.TESTING, IssueStatus.DONE]
    return [IssueStatus.TODO, IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW, IssueStatus.TESTING, IssueStatus.DONE]


def _seed_issue_history(session: Session, issue: Issue, sprint: Sprint, position: int) -> int:
    changed_at = dt.datetime.combine(sprint.start_date + dt.timedelta(days=position % 4), dt.time(9), tzinfo=dt.UTC)
    old_status: IssueStatus | None = None
    states = _history_states(issue)
    for offset, new_status in enumerate(states):
        session.add(IssueHistory(issue_id=issue.id, old_status=old_status, new_status=new_status, changed_by=issue.assignee_id, changed_at=changed_at + dt.timedelta(days=offset), notes="Synthetic development-demo status transition."))
        old_status = new_status
    return len(states)


def _seed_test_results(session: Session, issues: dict[str, Issue], qa: Employee) -> int:
    records = (
        ("BLI-4", TestingStatus.PASSED, 18, 18, 0, 0, "Synthetic feature transformation verification.", dt.datetime(2026, 6, 10, 14, tzinfo=dt.UTC)),
        ("BLI-11", TestingStatus.PASSED, 12, 12, 0, 0, "Synthetic risk-threshold boundary verification.", dt.datetime(2026, 6, 12, 15, tzinfo=dt.UTC)),
        ("BLI-15", TestingStatus.PASSED, 20, 20, 0, 0, "Synthetic prediction endpoint contract checks.", dt.datetime(2026, 6, 24, 15, tzinfo=dt.UTC)),
        ("BLI-16", TestingStatus.PASSED, 14, 14, 0, 1, "Synthetic transaction rollback verification.", dt.datetime(2026, 6, 25, 16, tzinfo=dt.UTC)),
        ("BLI-20", TestingStatus.PASSED, 11, 11, 0, 0, "Synthetic dashboard reporting validation.", dt.datetime(2026, 6, 26, 14, tzinfo=dt.UTC)),
        ("BLI-21", TestingStatus.PASSED, 9, 9, 1, 1, "Synthetic pagination regression verification.", dt.datetime(2026, 6, 27, 11, tzinfo=dt.UTC)),
        ("BLI-25", TestingStatus.IN_PROGRESS, 16, 11, 0, 0, "Synthetic idempotency and provenance test run.", dt.datetime(2026, 7, 7, 13, tzinfo=dt.UTC)),
    )
    for key, status, total, passed, bugs, reopened, notes, tested_at in records:
        session.add(TestResult(issue_id=issues[key].id, testing_status=status, test_cases_total=total, test_cases_passed=passed, bugs_found=bugs, reopened_count=reopened, testing_notes=notes, tested_by=qa.id, tested_at=tested_at))
    return len(records)


def _seed_deployments(session: Session, issues: dict[str, Issue]) -> int:
    records = (
        ("BLI-12", "model-service", "Synthetic staging deployment of model inference integration.", dt.datetime(2026, 6, 13, 15, tzinfo=dt.UTC)),
        ("BLI-15", "staging", "Synthetic staging deployment of prediction API workflows.", dt.datetime(2026, 6, 25, 15, tzinfo=dt.UTC)),
        ("BLI-19", "staging", "Synthetic staging deployment of the Streamlit demonstration dashboard.", dt.datetime(2026, 6, 26, 16, tzinfo=dt.UTC)),
        ("BLI-17", "staging", "Synthetic service health-check deployment verification.", dt.datetime(2026, 6, 27, 16, tzinfo=dt.UTC)),
    )
    for key, environment, notes, deployed_at in records:
        session.add(Deployment(issue_id=issues[key].id, deployment_status=DeploymentStatus.STAGING, environment=environment, deployment_date=deployed_at, production_notes=notes))
    return len(records)


def _seed_comments(session: Session, issues: dict[str, Issue], employees: dict[str, Employee]) -> int:
    records = (
        ("BLI-3", "EMP005", "Synthetic review note: keep the API schema mapping aligned with the model contract.", dt.datetime(2026, 6, 5, 11, tzinfo=dt.UTC)),
        ("BLI-9", "EMP006", "Synthetic QA observation: retain ROC-AUC context alongside class-imbalance assumptions.", dt.datetime(2026, 6, 11, 14, tzinfo=dt.UTC)),
        ("BLI-16", "EMP002", "Synthetic integration note: the persistence path should roll back the complete write set.", dt.datetime(2026, 6, 23, 10, tzinfo=dt.UTC)),
        ("BLI-21", "EMP006", "Synthetic regression result: pagination now preserves the selected reporting scope.", dt.datetime(2026, 6, 27, 12, tzinfo=dt.UTC)),
        ("BLI-24", "EMP001", "Synthetic code-review note: redact secret values from configuration errors and audit events.", dt.datetime(2026, 7, 4, 15, tzinfo=dt.UTC)),
        ("BLI-25", "EMP003", "Synthetic model-governance note: return model version with each idempotent response.", dt.datetime(2026, 7, 7, 14, tzinfo=dt.UTC)),
    )
    for key, employee_code, content, created_at in records:
        session.add(Comment(issue_id=issues[key].id, employee_id=employees[employee_code].id, content=content, created_at=created_at))
    return len(records)


def seed_bank_loan_project(session: Session) -> dict[str, int]:
    """Seed or refresh only deterministic synthetic BLI records; DEMO remains."""
    employees = {data[0]: _get_or_create_employee(session, data) for data in SYNTHETIC_EMPLOYEES}
    project = _get_or_create_project(
        session,
        "BLI",
        "Bank Loan Defaulter Prediction System",
        "ML-assisted loan default risk assessment platform with customer review, risk scoring, prediction persistence, analytics and controlled deployment.",
        employees["EMP001"],
    )
    for employee in employees.values():
        if session.scalar(select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.employee_id == employee.id)) is None:
            session.add(ProjectMember(project_id=project.id, employee_id=employee.id))
    session.flush()
    sprints = {data.name: _get_or_create_sprint(session, project, data) for data in SPRINT_SEEDS}
    _clear_project_issue_data(session, project)
    issues: dict[str, Issue] = {}
    for data in ISSUE_SEEDS:
        issues[data.key] = _get_or_create_issue(session, data, project, sprints, employees, issues)
    history_count = sum(_seed_issue_history(session, issues[data.key], sprints[data.sprint_name], position) for position, data in enumerate(ISSUE_SEEDS))
    test_result_count = _seed_test_results(session, issues, employees["EMP006"])
    deployment_count = _seed_deployments(session, issues)
    comment_count = _seed_comments(session, issues, employees)
    return {"employees": len(employees), "memberships": len(employees), "sprints": len(sprints), "issues": len(issues), "history": history_count, "test_results": test_result_count, "deployments": deployment_count, "comments": comment_count}


def _seed_retail_test_results(
    session: Session, issues: dict[str, Issue], qa: Employee
) -> int:
    records = (
        ("RD-8", TestingStatus.PASSED, 14, 14, 0, 0, "Synthetic webhook-envelope validation checks.", dt.datetime(2026, 7, 21, 14, tzinfo=dt.UTC)),
        ("RD-12", TestingStatus.PASSED, 10, 10, 0, 0, "Synthetic 384-dimensional embedding integration checks.", dt.datetime(2026, 7, 22, 15, tzinfo=dt.UTC)),
        ("RD-13", TestingStatus.PASSED, 18, 18, 1, 0, "Synthetic product-search relevance verification.", dt.datetime(2026, 7, 24, 13, tzinfo=dt.UTC)),
        ("RD-17", TestingStatus.PASSED, 16, 16, 0, 0, "Synthetic product index dimension and deduplication checks.", dt.datetime(2026, 7, 25, 15, tzinfo=dt.UTC)),
        ("RD-20", TestingStatus.PASSED, 15, 15, 0, 0, "Synthetic cart add, remove and quantity validation.", dt.datetime(2026, 8, 4, 14, tzinfo=dt.UTC)),
        ("RD-21", TestingStatus.PASSED, 12, 12, 1, 1, "Synthetic multi-line order preservation verification.", dt.datetime(2026, 8, 6, 15, tzinfo=dt.UTC)),
        ("RD-26", TestingStatus.IN_PROGRESS, 14, 10, 0, 0, "Synthetic exact order ownership and tracking test run.", dt.datetime(2026, 8, 15, 14, tzinfo=dt.UTC)),
        ("RD-29", TestingStatus.IN_PROGRESS, 20, 13, 0, 0, "Synthetic session isolation and duplicate confirmation checks.", dt.datetime(2026, 8, 18, 15, tzinfo=dt.UTC)),
        ("RD-5", TestingStatus.PASSED, 8, 8, 0, 0, "Synthetic missing output-context regression checks.", dt.datetime(2026, 7, 23, 11, tzinfo=dt.UTC)),
    )
    for key, status, total, passed, bugs, reopened, notes, tested_at in records:
        session.add(TestResult(issue_id=issues[key].id, testing_status=status, test_cases_total=total, test_cases_passed=passed, bugs_found=bugs, reopened_count=reopened, testing_notes=notes, tested_by=qa.id, tested_at=tested_at))
    return len(records)


def _seed_retail_deployments(session: Session, issues: dict[str, Issue]) -> int:
    records = (
        ("RD-8", DeploymentStatus.STAGING, "staging", "Synthetic staging deployment of the FastAPI Dialogflow webhook.", dt.datetime(2026, 7, 24, 16, tzinfo=dt.UTC)),
        ("RD-13", DeploymentStatus.STAGING, "staging", "Synthetic staging deployment of SentenceTransformer and product-search integration.", dt.datetime(2026, 7, 25, 16, tzinfo=dt.UTC)),
        ("RD-19", DeploymentStatus.PRODUCTION, "demo-production", "Synthetic, limited demo/prototype deployment of the Nyxiee chat storefront integration.", dt.datetime(2026, 8, 8, 16, tzinfo=dt.UTC)),
        ("RD-21", DeploymentStatus.STAGING, "staging", "Synthetic staging deployment of complete order persistence workflow.", dt.datetime(2026, 8, 7, 16, tzinfo=dt.UTC)),
        ("RD-29", DeploymentStatus.STAGING, "staging", "Synthetic staging deployment for session and idempotency hardening verification.", dt.datetime(2026, 8, 19, 16, tzinfo=dt.UTC)),
    )
    for key, status, environment, notes, deployed_at in records:
        session.add(Deployment(issue_id=issues[key].id, deployment_status=status, environment=environment, deployment_date=deployed_at, production_notes=notes))
    return len(records)


def _seed_retail_comments(
    session: Session, issues: dict[str, Issue], employees: dict[str, Employee]
) -> int:
    records = (
        ("RD-16", "EMP001", "Synthetic design note: product and variant identifiers must remain stable across Pinecone ingestion runs.", dt.datetime(2026, 7, 20, 11, tzinfo=dt.UTC)),
        ("RD-17", "EMP003", "Synthetic review note: reject vectors that are not 384 dimensions before index writes.", dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC)),
        ("RD-23", "EMP006", "Synthetic QA finding: reuse of a vector identifier must never overwrite a prior order line.", dt.datetime(2026, 8, 5, 14, tzinfo=dt.UTC)),
        ("RD-26", "EMP006", "Synthetic test feedback: order recency must be resolved within the requesting shopper scope.", dt.datetime(2026, 8, 15, 16, tzinfo=dt.UTC)),
        ("RD-29", "EMP005", "Synthetic implementation note: session keys and confirmation tokens must be isolated per shopper.", dt.datetime(2026, 8, 18, 16, tzinfo=dt.UTC)),
        ("RD-14", "EMP003", "Synthetic relevance observation: low-confidence matches should trigger clarification rather than product selection.", dt.datetime(2026, 8, 14, 13, tzinfo=dt.UTC)),
        ("RD-30", "EMP001", "Synthetic release note: measure webhook latency and make dependency retries safe before broader rollout.", dt.datetime(2026, 8, 20, 15, tzinfo=dt.UTC)),
    )
    for key, employee_code, content, created_at in records:
        session.add(Comment(issue_id=issues[key].id, employee_id=employees[employee_code].id, content=content, created_at=created_at))
    return len(records)


def seed_retail_dialogue_project(session: Session) -> dict[str, int]:
    """Seed deterministic synthetic RetailDialogue records without affecting BLI."""
    employees = {data[0]: _get_or_create_employee(session, data) for data in SYNTHETIC_EMPLOYEES}
    project = _get_or_create_project(
        session,
        "RD",
        "RetailDialogue E-commerce Chatbot",
        "Conversational e-commerce assistant for semantic product discovery, cart management, order persistence, and order tracking using Dialogflow, FastAPI, SentenceTransformer embeddings, and Pinecone.",
        employees["EMP001"],
    )
    for employee in employees.values():
        membership = session.scalar(select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.employee_id == employee.id))
        if membership is None:
            session.add(ProjectMember(project_id=project.id, employee_id=employee.id))
    session.flush()
    sprints = {data.name: _get_or_create_sprint(session, project, data) for data in RETAIL_SPRINT_SEEDS}
    _clear_project_issue_data(session, project)
    issues: dict[str, Issue] = {}
    for data in RETAIL_ISSUE_SEEDS:
        issues[data.key] = _get_or_create_issue(session, data, project, sprints, employees, issues)
    history_count = sum(_seed_issue_history(session, issues[data.key], sprints[data.sprint_name], position) for position, data in enumerate(RETAIL_ISSUE_SEEDS))
    test_result_count = _seed_retail_test_results(session, issues, employees["EMP006"])
    deployment_count = _seed_retail_deployments(session, issues)
    comment_count = _seed_retail_comments(session, issues, employees)
    return {"employees": len(employees), "memberships": len(employees), "sprints": len(sprints), "issues": len(issues), "history": history_count, "test_results": test_result_count, "deployments": deployment_count, "comments": comment_count}


def seed_database() -> None:
    """Seed repeatable synthetic development/demo data without touching DEMO."""
    session = SessionLocal()
    try:
        print("Starting database seed...")
        bank_loan = seed_bank_loan_project(session)
        retail = seed_retail_dialogue_project(session)
        session.commit()
        print(f"Employees ready: {bank_loan['employees']}")
        print("Bank Loan project ready")
        print(f"Bank Loan members: {bank_loan['memberships']}")
        print(f"Bank Loan sprints: {bank_loan['sprints']}")
        print(f"Bank Loan issues: {bank_loan['issues']}")
        print(f"Bank Loan history: {bank_loan['history']}")
        print(f"Bank Loan test results: {bank_loan['test_results']}")
        print(f"Bank Loan deployments: {bank_loan['deployments']}")
        print(f"Bank Loan comments: {bank_loan['comments']}")
        print("RetailDialogue project ready")
        print(f"RetailDialogue members: {retail['memberships']}")
        print(f"RetailDialogue sprints: {retail['sprints']}")
        print(f"RetailDialogue issues: {retail['issues']}")
        print(f"RetailDialogue history: {retail['history']}")
        print(f"RetailDialogue test results: {retail['test_results']}")
        print(f"RetailDialogue deployments: {retail['deployments']}")
        print(f"RetailDialogue comments: {retail['comments']}")
        print("Database seed completed successfully")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
