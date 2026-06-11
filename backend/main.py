"""StatAI FastAPI uygulaması — endpoint tanımları."""
import io
import re
import traceback
from collections import defaultdict
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import ALLOWED_ORIGINS
from schemas import (
    AnalysisRequest,
    BulguRequest,
    ClassifyRequest,
    ColumnLabel,
    CronbachBatchRequest,
    CronbachRequest,
    DetectScalesRequest,
    ExtractContextRequest,
    PairedRequest,
    PlanRequest,
    ParseHypothesesRequest,
    PlanTestsRequest,
    BulguSummaryRequest,
    RegressionRequest,
    ScaleMatchRequest,
    SpssTableRequest,
    Variable,
    LayoutResultsRequest,
    WordExportRequest,
)
from utils import sanitize
from layout_config import LayoutConfig
from table_layout import normalize_table_layout
from data_cleaning import (
    normalize_variable_labels,
    apply_scale_info_to_variables,
    missing_data_report,
    prepare_analysis_df,
)
from stat_tests import (
    TableCounter,
    cronbach_analysis,
    generate_plan,
    paired_analysis,
    run_analyze,
    table_multiple_regression,
)
from word_export import build_word_document
from file_io import read_uploaded_file
from ai_services import (
    generate_bulgu,
    generate_bulgu_summary,
    compact_summaries_from_results,
    _normalize_ai_plan_ids,
    build_label_context_map,
    extract_full_text,
    generate_plan_ai,
    import_spss_tables_service,
    match_all_scales,
    run_classify,
    run_detect_scales,
    run_import_ethics_report,
)
from test_planner import (
    apply_deterministic_flags,
    build_candidate_tests,
    build_norm_map,
    plan_tests,
)
from hypothesis_engine import (
    compact_candidate_preview,
    parse_research_questions,
    tag_results_with_hypotheses,
)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="StatAI - Akademik Analiz API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "app": "StatAI"}


@app.post("/convert-spss-table")
@app.post("/import-spss-tables")
@limiter.limit("10/minute")
async def import_spss_tables_endpoint(request: Request, req: SpssTableRequest):
    return import_spss_tables_service(req)


@app.post("/plan")
async def generate_analysis_plan(req: PlanRequest):
    rows = [r.values for r in req.data]
    df = pd.DataFrame(rows)
    variables = normalize_variable_labels(req.variables)
    df = prepare_analysis_df(df, variables, req.missing_codes)
    rule_based = generate_plan(df, variables)

    if req.use_ai and req.research_topic:
        ai_tests = await generate_plan_ai(variables, req.research_topic)
        if ai_tests:
            ai_tests = _normalize_ai_plan_ids(ai_tests, rule_based)
            ai_ids = {t.get("id") for t in ai_tests}
            merged = list(ai_tests)
            for rb_test in rule_based:
                if rb_test["id"] not in ai_ids:
                    rb_copy = dict(rb_test)
                    rb_copy["recommended"] = False
                    merged.append(rb_copy)
            return sanitize({"tests": merged, "source": "ai"})

    return sanitize({"tests": rule_based, "source": "rules"})


@app.post("/parse-hypotheses")
@limiter.limit("10/minute")
async def parse_hypotheses_endpoint(request: Request, req: ParseHypothesesRequest):
    rows = [r.values for r in req.data]
    df = pd.DataFrame(rows)
    variables = normalize_variable_labels(req.variables)
    df = prepare_analysis_df(df, variables, req.missing_codes)
    norm_map = build_norm_map(df, variables)
    candidates = build_candidate_tests(df, variables, norm_map)
    candidates = apply_deterministic_flags(df, variables, candidates)
    uygun = [c for c in candidates if c.get("auto_flag") == "uygun"]
    parsed, meta = await parse_research_questions(
        req.research_aim,
        variables,
        uygun,
        df=df,
    )
    return sanitize({
        **parsed,
        "candidates": compact_candidate_preview(uygun, variables),
        "meta": meta,
    })


@app.post("/plan-tests")
@limiter.limit("10/minute")
async def plan_tests_endpoint(request: Request, req: PlanTestsRequest):
    rows = [r.values for r in req.data]
    df = pd.DataFrame(rows)
    variables = normalize_variable_labels(req.variables)
    df = prepare_analysis_df(df, variables, req.missing_codes)
    recommended, excluded, catalog, meta = await plan_tests(
        df,
        variables,
        req.research_aim,
        use_ai=req.use_ai if req.use_ai is not None else True,
        profile=req.profile or "standart",
        hypotheses=[h.model_dump() for h in req.hypotheses] if req.hypotheses else None,
    )
    return sanitize({
        "recommended": recommended,
        "excluded": excluded,
        "catalog": catalog,
        "meta": meta,
        "estimated_tables": meta.get("estimated_tables", 0),
        "hypotheses": [h.model_dump() for h in req.hypotheses] if req.hypotheses else [],
    })


@app.post("/analyze")
async def analyze(req: AnalysisRequest):
    rows = [r.values for r in req.data]
    df = pd.DataFrame(rows)
    variables = normalize_variable_labels(req.variables)
    variables = apply_scale_info_to_variables(variables, req.scale_info)
    df = prepare_analysis_df(df, variables, req.missing_codes)
    missing_data = missing_data_report(df, variables)
    results, meta = run_analyze(
        df,
        variables,
        req.active_types,
        req.enabled_tests,
        req.scale_info,
        req.missing_codes,
    )
    if req.test_hypothesis_map:
        results = tag_results_with_hypotheses(
            results, req.test_hypothesis_map, variables,
        )
    if req.hypotheses:
        meta["hypotheses"] = [h.model_dump() for h in req.hypotheses]
    return sanitize({"results": results, "missing_data": missing_data, "meta": meta})


@app.post("/layout-results")
async def layout_results(req: LayoutResultsRequest):
    cfg = LayoutConfig.from_optional(
        req.layout_config.model_dump() if req.layout_config else None,
    )
    return sanitize({"results": normalize_table_layout(req.results, cfg)})


@app.post("/analyze/cronbach")
async def analyze_cronbach(req: CronbachRequest):
    try:
        if len(req.columns) < 2:
            raise HTTPException(status_code=400, detail="En az 2 sütun gerekli")
        df = pd.DataFrame([r.values for r in req.data])
        missing = [c for c in req.columns if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Sütunlar bulunamadı: {missing}")
        for col in req.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        result = cronbach_analysis(df, req.columns)
        if result is None:
            raise HTTPException(status_code=400, detail="Cronbach alfa hesaplanamadı (yetersiz veri veya varyans)")
        return sanitize({"result": result})
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/detect-items")
def detect_item_columns(req: DetectScalesRequest):
    columns = req.columns
    samples = req.samples or {}
    measure = req.variable_measure or {}

    item_columns: set = set()
    scale_groups: dict = {}
    total_columns: List[str] = []
    other_columns: List[str] = []

    item_pattern = re.compile(
        r"^([a-zA-Z_]{1,10}?)(\d{1,3})(_ters|_t|_r|_T|_rev)?$",
        re.I,
    )
    total_re = re.compile(
        r"(_toplam|_total|_score|_puan|_skor|_sum|_avg|_mean)$"
        r"|^t[a-z]{2,}",
        re.I,
    )

    if measure:
        for col in columns:
            m = measure.get(col, "").lower()
            if m == "scale":
                if total_re.search(col):
                    total_columns.append(col)
                else:
                    other_columns.append(col)
                continue
            if m == "nominal":
                other_columns.append(col)
                continue
            if m == "ordinal":
                if item_pattern.match(col):
                    item_columns.add(col)
                else:
                    other_columns.append(col)
                continue

        prefix_groups = defaultdict(list)
        for col in item_columns:
            m_pat = item_pattern.match(col)
            if m_pat:
                prefix = m_pat.group(1).rstrip("_").lower()
                if prefix:
                    prefix_groups[prefix].append(col)
        scale_groups = dict(prefix_groups)
    else:
        prefix_groups = defaultdict(list)
        for col in columns:
            m_pat = item_pattern.match(col)
            if m_pat:
                prefix = m_pat.group(1).rstrip("_").lower()
                if prefix:
                    prefix_groups[prefix].append(col)

        for prefix, cols in prefix_groups.items():
            if len(cols) < 3:
                continue
            narrow_count = 0
            for col in cols:
                vals = [
                    v for v in (samples.get(col) or [])
                    if v is not None
                    and str(v).replace(".", "").replace("-", "").isdigit()
                ]
                if vals:
                    try:
                        nums = [float(v) for v in vals]
                        if max(nums) - min(nums) <= 10 and len(set(nums)) <= 8:
                            narrow_count += 1
                    except Exception:
                        pass
            if narrow_count >= len(cols) * 0.5:
                for col in cols:
                    item_columns.add(col)
                scale_groups[prefix] = cols

        for col in columns:
            if col in item_columns:
                continue
            if total_re.search(col):
                total_columns.append(col)
            else:
                other_columns.append(col)

    processed = item_columns | set(total_columns) | set(other_columns)
    for col in columns:
        if col not in processed:
            other_columns.append(col)

    return {
        "item_columns": list(item_columns),
        "scale_groups": scale_groups,
        "total_columns": total_columns,
        "other_columns": other_columns,
        "source": "spss_measure" if measure else "data_inference",
    }


@app.post("/detect-scales")
@limiter.limit("10/minute")
async def detect_scales(request: Request, req: DetectScalesRequest):
    return run_detect_scales(req)


@app.post("/analyze/cronbach-batch")
async def analyze_cronbach_batch(req: CronbachBatchRequest):
    df = pd.DataFrame([r.values for r in req.data])
    results = []
    tc = TableCounter()

    for scale in req.scales:
        name = scale.get("name", "Ölçek")
        items = scale.get("items", [])
        valid_items = []
        for col in items:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce",
                )
                valid_items.append(col)

        if len(valid_items) < 2:
            continue

        try:
            items_df = df[valid_items].dropna()
            k = len(valid_items)
            if len(items_df) < 3:
                continue

            item_vars = items_df.var(axis=0, ddof=1).sum()
            total_var = items_df.sum(axis=1).var(ddof=1)
            if total_var == 0:
                continue

            alpha = float((k / (k - 1)) * (1 - item_vars / total_var))
            if alpha >= 0.90:
                interp = "Yüksek"
            elif alpha >= 0.70:
                interp = "İyi"
            elif alpha >= 0.60:
                interp = "Kabul Edilebilir"
            else:
                interp = "Düşük"

            tno, title = tc.next(f"Ölçek Güvenilirlik Analizi — {name}")
            results.append({
                "type": "cronbach",
                "table_number": tno,
                "title": title,
                "headers": ["Ölçek", "Madde Sayısı", "Geçerli n", "Cronbach α", "Değerlendirme"],
                "rows": [[name, k, len(items_df), f"{alpha:.3f}", interp]],
                "note": "Not. α = Cronbach alfa iç tutarlılık katsayısı. Kabul edilebilir sınır: α ≥ .70.",
                "significant": None,
            })
        except Exception:
            continue

    return sanitize({"results": normalize_table_layout(results)})


@app.post("/analyze/paired")
async def analyze_paired(req: PairedRequest):
    df = pd.DataFrame([r.values for r in req.data])
    for col in (req.col1, req.col2):
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Sütun bulunamadı: {col}")
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    try:
        result = paired_analysis(df, req.col1, req.col2)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"result": result}


@app.post("/analyze/regression")
async def analyze_regression(req: RegressionRequest):
    if not req.predictors:
        raise HTTPException(status_code=400, detail="En az bir yordayıcı seçilmelidir.")
    if req.outcome in req.predictors:
        raise HTTPException(status_code=400, detail="Sonuç değişkeni yordayıcılar arasında olamaz.")

    df = pd.DataFrame([r.values for r in req.data])
    label_map = {v.name: v.label for v in (req.variables or []) if v.name and v.label}

    for col in req.predictors + [req.outcome]:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Sütun bulunamadı: {col}")
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    predictors = [
        Variable(name=c, label=label_map.get(c, c), type="continuous", role="grouping", included=True)
        for c in req.predictors
    ]
    outcome = Variable(
        name=req.outcome,
        label=label_map.get(req.outcome, req.outcome),
        type="continuous",
        role="outcome",
        included=True,
    )

    try:
        tc = TableCounter()
        result = table_multiple_regression(tc, df, predictors, outcome)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"result": result}


@app.post("/classify")
@limiter.limit("10/minute")
async def classify_columns(request: Request, req: ClassifyRequest):
    return run_classify(req)


@app.post("/ai/bulgu")
@limiter.limit("10/minute")
async def ai_bulgu(request: Request, req: BulguRequest):
    text, source, meta = generate_bulgu(
        req.result,
        req.research_topic,
        req.label_map,
        req.approved_cutoffs,
        req.scale_info,
        req.pdf_context,
        force_llm=bool(req.force_llm),
    )
    return {"bulgu": text, "source": source, "meta": meta}


@app.post("/ai/bulgu-summary")
@limiter.limit("10/minute")
async def ai_bulgu_summary(request: Request, req: BulguSummaryRequest):
    text, meta = generate_bulgu_summary(
        req.summaries, req.research_topic, req.hypotheses,
    )
    return {"summary": text, "meta": meta}


@app.post("/export/word")
async def export_word(req: WordExportRequest):
    try:
        doc_bytes = build_word_document(
            normalize_table_layout(req.results),
            req.bulgular,
            req.intro or "",
            req.label_map,
            req.custom_labels,
            req.custom_titles,
            req.hypotheses,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Word dosyası oluşturulamadı: {str(e)}")
    return StreamingResponse(
        io.BytesIO(doc_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=statai_bulgular.docx"},
    )


@app.post("/match-scales")
@limiter.limit("10/minute")
async def match_scales_endpoint(request: Request, req: ScaleMatchRequest):
    return match_all_scales(req.scale_names, req.column_names)


@app.post("/extract-context")
@limiter.limit("10/minute")
async def extract_context(request: Request, req: ExtractContextRequest):
    file_type = (req.file_type or "").lower().strip()
    if file_type not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="file_type 'pdf' veya 'docx' olmalı")
    if not req.column_labels:
        return {"context_map": {}, "page_count": 0, "matched_count": 0}

    full_text, page_count = extract_full_text(req.file_base64, file_type)
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="Dosyadan metin çıkarılamadı")

    context_map = build_label_context_map(full_text, req.column_labels)
    return {
        "context_map": context_map,
        "page_count": page_count,
        "matched_count": sum(1 for v in context_map.values() if v),
    }


@app.post("/import-ethics-report")
@limiter.limit("10/minute")
async def import_ethics_report(
    request: Request,
    file: UploadFile = File(...),
    research_topic: Optional[str] = Form(None),
):
    filename = (file.filename or "").lower()
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dosya okunamadı: {e}")
    return run_import_ethics_report(file_bytes, filename, research_topic)


@app.post("/read-file")
async def read_file(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    file_bytes = await file.read()
    return read_uploaded_file(filename, file_bytes)
