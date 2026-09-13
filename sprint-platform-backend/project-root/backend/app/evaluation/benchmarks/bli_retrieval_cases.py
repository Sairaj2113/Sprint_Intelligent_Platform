"""Initial deterministic BLI PRD semantic-retrieval benchmark."""

from app.evaluation.retrieval_evaluation import RetrievalBenchmarkCase
from app.models import DocumentType


BLI_RETRIEVAL_CASES: list[RetrievalBenchmarkCase] = [
    RetrievalBenchmarkCase("BLI-PRD-01", "BLI", "What are the model quality and approval requirements?", [8, 9, 3], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-02", "BLI", "What input data is required for a loan assessment?", [6], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-03", "BLI", "What are the current risk thresholds for low medium and high risk?", [6], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-04", "BLI", "What happens if the model or service is unavailable?", [3], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-05", "BLI", "What functionality is outside the release scope?", [3], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-06", "BLI", "What must pass before production release?", [8], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-07", "BLI", "Who is responsible for approving model releases?", [3, 9], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-08", "BLI", "What data semantics must be settled before the pilot?", [6], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-09", "BLI", "What risks are associated with training data differing from bank applicants?", [8], expected_document_types=[DocumentType.PRD]),
    RetrievalBenchmarkCase("BLI-PRD-10", "BLI", "What evidence sources describe model training and metrics?", [9], expected_document_types=[DocumentType.PRD]),
]
