"""Pydantic request/response modelleri."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class Variable(BaseModel):
    name: str
    label: str
    type: str  # "continuous" | "categorical"
    role: str = "grouping"  # "grouping" | "outcome"
    categories: Optional[List[str]] = None
    included: bool = True
    scale_min: Optional[float] = None
    scale_max: Optional[float] = None
    value_labels: Optional[Dict[str, str]] = None


class DataRow(BaseModel):
    values: dict


class HypothesisItem(BaseModel):
    id: str
    label: str
    type: Optional[str] = "fark"
    candidate_ids: List[str] = []
    var_hints: Optional[List[str]] = None


class AnalysisRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    active_types: Optional[List[str]] = None
    enabled_tests: Optional[List[str]] = None
    missing_codes: Optional[List[str]] = None
    scale_info: Optional[dict] = None
    test_hypothesis_map: Optional[Dict[str, str]] = None
    hypotheses: Optional[List[HypothesisItem]] = None


class PlanRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    missing_codes: Optional[List[str]] = None
    research_topic: Optional[str] = None
    use_ai: Optional[bool] = True
    document_context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class DetectDerivedRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    missing_codes: Optional[List[str]] = None


class ParseHypothesesRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    research_aim: str
    missing_codes: Optional[List[str]] = None
    use_ai: Optional[bool] = True
    document_context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class PlanTestsRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    research_aim: str
    missing_codes: Optional[List[str]] = None
    use_ai: Optional[bool] = True
    profile: Optional[str] = "standart"
    hypotheses: Optional[List[HypothesisItem]] = None
    document_context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class BulguRequest(BaseModel):
    result: Any
    research_topic: Optional[str] = None
    label_map: Optional[Dict[str, str]] = None
    approved_cutoffs: Optional[List[dict]] = None
    scale_info: Optional[dict] = None
    pdf_context: Optional[str] = None
    force_llm: Optional[bool] = False
    all_results: Optional[List[Any]] = None


class BulguSummaryRequest(BaseModel):
    summaries: Optional[List[dict]] = None
    results: Optional[List[Any]] = None
    bulgular: Optional[Dict[str, str]] = None
    research_topic: Optional[str] = None
    hypotheses: Optional[List[dict]] = None


class LayoutConfigModel(BaseModel):
    locale: str = "tr"
    decimal_separator: str = ","
    leading_zero: bool = True
    title_style: str = "tr_classic"
    merge_demographics: bool = True
    correlation_lower_triangle: bool = True
    merge_group_comparisons: bool = True
    suppress_normality_to_footnote: bool = True


class LayoutResultsRequest(BaseModel):
    results: List[dict]
    layout_config: Optional[LayoutConfigModel] = None


class WordExportRequest(BaseModel):
    results: List[dict]
    bulgular: Optional[Dict[str, str]] = None
    intro: Optional[str] = None
    label_map: Optional[Dict[str, str]] = None
    custom_labels: Optional[Dict[str, str]] = None
    custom_titles: Optional[Dict[str, str]] = None
    hypotheses: Optional[List[dict]] = None
    methodology: Optional[List[dict]] = None


class QualityCheckRequest(BaseModel):
    results: List[dict]
    bulgular: Optional[Dict[str, str]] = None
    intro: Optional[str] = None
    hypotheses: Optional[List[dict]] = None
    n_total: Optional[int] = None


class CronbachRequest(BaseModel):
    columns: List[str]
    data: List[DataRow]


class PairedRequest(BaseModel):
    col1: str
    col2: str
    data: List[DataRow]


class RegressionRequest(BaseModel):
    data: List[DataRow]
    predictors: List[str]
    outcome: str
    variables: Optional[List[Variable]] = None


class ClassifyRequest(BaseModel):
    columns: List[str]
    samples: Dict[str, List[Any]]
    labels: Optional[Dict[str, str]] = None
    research_topic: Optional[str] = None
    variable_measure: Optional[Dict[str, str]] = None
    data: Optional[List[DataRow]] = None
    missing_codes: Optional[List[str]] = None
    document_context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class DetectScalesRequest(BaseModel):
    columns: List[str]
    samples: Optional[Dict[str, List[Any]]] = None
    labels: Optional[Dict[str, str]] = None
    variable_measure: Optional[Dict[str, str]] = None
    document_context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class CronbachBatchRequest(BaseModel):
    scales: List[dict]
    data: List[DataRow]
    missing_codes: Optional[List[str]] = None


class SpssTableRequest(BaseModel):
    content: str
    auto_bulgu: bool = True


class ScaleMatchRequest(BaseModel):
    scale_names: List[str]
    column_names: List[str]


class ColumnLabel(BaseModel):
    column: str
    label: str


class ExtractContextRequest(BaseModel):
    file_base64: str
    file_type: str
    column_labels: List[ColumnLabel]


class GenerateLabelsRequest(BaseModel):
    columns: List[str]
    scale_names: Optional[List[str]] = None
    research_topic: Optional[str] = None


class AnalizeOneriRequest(BaseModel):
    columns: List[str]
    labels: Optional[Dict[str, str]] = None
    anket_text: Optional[str] = None
    etik_text: Optional[str] = None
    document_context: Optional[dict] = None
