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


class AnalysisRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    active_types: Optional[List[str]] = None
    enabled_tests: Optional[List[str]] = None
    missing_codes: Optional[List[str]] = None
    scale_info: Optional[dict] = None


class PlanRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    missing_codes: Optional[List[str]] = None
    research_topic: Optional[str] = None
    use_ai: Optional[bool] = True


class PlanTestsRequest(BaseModel):
    variables: List[Variable]
    data: List[DataRow]
    research_aim: str
    missing_codes: Optional[List[str]] = None
    use_ai: Optional[bool] = True


class BulguRequest(BaseModel):
    result: Any
    research_topic: Optional[str] = None
    label_map: Optional[Dict[str, str]] = None
    approved_cutoffs: Optional[List[dict]] = None
    scale_info: Optional[dict] = None
    pdf_context: Optional[str] = None
    force_llm: Optional[bool] = False


class BulguSummaryRequest(BaseModel):
    summaries: List[dict]
    research_topic: Optional[str] = None


class WordExportRequest(BaseModel):
    results: List[dict]
    bulgular: Optional[Dict[str, str]] = None
    intro: Optional[str] = None
    label_map: Optional[Dict[str, str]] = None
    custom_labels: Optional[Dict[str, str]] = None
    custom_titles: Optional[Dict[str, str]] = None


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


class DetectScalesRequest(BaseModel):
    columns: List[str]
    samples: Optional[Dict[str, List[Any]]] = None
    variable_measure: Optional[Dict[str, str]] = None


class CronbachBatchRequest(BaseModel):
    scales: List[dict]
    data: List[DataRow]


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
