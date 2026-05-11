from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.services.ops_db_service import fetch_run_rows
from backend.services.run_state_service import refresh_run_record


TRINITY_SPOT_CONTRACT_VERSION = "trinity.spot.v1alpha1"
TRINITY_SPOT_BUNDLE_TYPE = "spot-review-policy-learning"


@dataclass(frozen=True)
class ExportSummary:
    run_id: str
    company_id: str
    exported_count: int
    skipped_count: int
    output_dir: Path
    files: tuple[str, ...]


def export_trinity_spot_training_bundles(
    *,
    runs_dir: Path,
    run_id: str,
    company_id: str,
    output_dir: Path,
    row_indices: list[int] | None = None,
) -> ExportSummary:
    record = refresh_run_record(runs_dir=runs_dir, run_id=run_id, sync_review_rows=False)
    if not record:
        raise RuntimeError(f"Run '{run_id}' was not found.")

    rows = fetch_run_rows(runs_dir=runs_dir, run_id=run_id, review_required_only=True)
    if row_indices:
        allowed = {int(item) for item in row_indices}
        rows = [row for row in rows if int(row.get("row_index") or 0) in allowed]
    if not rows:
        raise RuntimeError("No review-required rows matched the export request.")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped_count = 0
    for row in sorted(rows, key=lambda item: int(item.get("row_index") or 0)):
        bundle = build_trinity_spot_training_bundle(
            run_id=run_id,
            company_id=company_id,
            language=str(record.get("language") or ""),
            review_mode=str(record.get("review_mode") or ""),
            row=row,
        )
        if bundle is None:
            skipped_count += 1
            continue
        row_index = int(row.get("row_index") or 0)
        output_path = output_dir / f"{run_id}_row_{row_index}.json"
        output_path.write_text(json.dumps({"bundle": bundle}, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(output_path))

    if not written:
        raise RuntimeError("No exportable reviewed rows were found. Save a review decision before exporting.")

    return ExportSummary(
        run_id=run_id,
        company_id=company_id,
        exported_count=len(written),
        skipped_count=skipped_count,
        output_dir=output_dir,
        files=tuple(written),
    )


def build_trinity_spot_training_bundle(
    *,
    run_id: str,
    company_id: str,
    language: str,
    review_mode: str,
    row: dict,
) -> dict | None:
    review_state = str(row.get("review_state") or "pending")
    review_decision = str(row.get("review_decision") or "").strip().lower()
    if review_state not in {"reviewed", "escalated"}:
        return None
    if review_decision not in {"confirm", "adjust"}:
        return None

    row_index = int(row.get("row_index") or 0)
    assigned_category = str(row.get("assigned_category") or "").strip()
    post_text = str(row.get("post_text") or "").strip()
    if row_index <= 0 or not assigned_category or not post_text:
        return None

    occurred_at = _coerce_timestamp(row.get("updated_at"))
    cycle_id = str(uuid5(NAMESPACE_URL, f"spot:{company_id}:{run_id}:{row_index}:{review_state}:{review_decision}"))
    selected_candidate_key = _selected_candidate_key(assigned_category=assigned_category)
    combined_confidence = _normalized_confidence(row.get("confidence_score"))
    review_required = bool(row.get("review_required"))
    policy_sensitive = assigned_category != "Not Antisemitic" or review_required
    disposition = _review_disposition(
        assigned_category=assigned_category,
        review_decision=review_decision,
    )
    disagreement_severity = _disagreement_severity(row)

    request = {
        "company_id": company_id,
        "run_id": run_id,
        "row_ref": f"sheet1:{row_index}",
        "language": language or "unknown",
        "message_text": post_text,
        "occurred_at": occurred_at,
        "metadata": {
            "source": "spot",
            "review_mode": review_mode,
            "item_number": str(row.get("item_number") or ""),
        },
        "contract_version": TRINITY_SPOT_CONTRACT_VERSION,
    }
    result = {
        "company_id": company_id,
        "run_id": run_id,
        "row_ref": f"sheet1:{row_index}",
        "generated_at": occurred_at,
        "candidates": (
            {
                "candidate_key": selected_candidate_key,
                "interpretation": assigned_category,
                "rationale": str(row.get("explanation") or ""),
                "threat_label_hint": assigned_category,
                "review_recommended": review_required,
            },
        ),
        "selected_candidate_key": selected_candidate_key,
        "confidence_bundle": {
            "generator_confidence": combined_confidence,
            "refiner_confidence": combined_confidence,
            "evaluator_confidence": combined_confidence,
            "frontier_confidence": combined_confidence,
            "combined_confidence": combined_confidence,
            "disagreement_severity": disagreement_severity,
        },
        "review_required": review_required,
        "review_reason": _review_reason(row),
        "policy_sensitive": policy_sensitive,
        "automatic_disposition": "auto_approve" if assigned_category == "Not Antisemitic" and not review_required else "review_required",
        "human_override_allowed": True,
        "deeper_analysis_available": True,
        "escalation_recommended": review_state == "escalated",
        "contract_version": TRINITY_SPOT_CONTRACT_VERSION,
    }
    review_outcome = {
        "company_id": company_id,
        "cycle_id": cycle_id,
        "run_id": run_id,
        "row_ref": f"sheet1:{row_index}",
        "selected_candidate_key": selected_candidate_key,
        "disposition": disposition,
        "final_label": assigned_category,
        "occurred_at": occurred_at,
        "reviewer_notes": str(row.get("reviewer_note") or "") or None,
        "metadata": {
            "source": "spot",
            "review_state": review_state,
            "review_decision": review_decision,
            "flags": list(row.get("flags") or []),
        },
        "contract_version": TRINITY_SPOT_CONTRACT_VERSION,
    }
    bundle_id = _bundle_id(company_id=company_id, run_id=run_id, row_index=row_index, cycle_id=cycle_id)
    return {
        "bundle_id": bundle_id,
        "bundle_type": TRINITY_SPOT_BUNDLE_TYPE,
        "exported_at": occurred_at,
        "spot_reasoning_request": request,
        "spot_reasoning_result": result,
        "spot_review_outcome": review_outcome,
        "labels": {
            "bundle_type": TRINITY_SPOT_BUNDLE_TYPE,
            "company_id": company_id,
            "run_id": run_id,
            "final_label": assigned_category,
            "disposition": disposition,
        },
        "contract_version": TRINITY_SPOT_CONTRACT_VERSION,
    }


def _bundle_id(*, company_id: str, run_id: str, row_index: int, cycle_id: str) -> str:
    digest = sha1(f"{company_id}:{run_id}:{row_index}:{cycle_id}".encode("utf-8")).hexdigest()[:16]
    return f"spot-{digest}"


def _coerce_timestamp(value: object) -> str:
    if value in {None, ""}:
        return datetime.now(tz=UTC).isoformat()
    try:
        numeric = int(value)
    except Exception:
        return datetime.now(tz=UTC).isoformat()
    return datetime.fromtimestamp(numeric, tz=UTC).isoformat()


def _normalized_confidence(value: object) -> float:
    try:
        score = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(score, 1.0))


def _selected_candidate_key(*, assigned_category: str) -> str:
    return "benign" if assigned_category == "Not Antisemitic" else "review"


def _review_disposition(*, assigned_category: str, review_decision: str) -> str:
    if review_decision == "adjust":
        return "CORRECTED"
    if assigned_category == "Not Antisemitic":
        return "CONFIRMED_NEGATIVE"
    return "CONFIRMED_POSITIVE"


def _review_reason(row: dict) -> str:
    flags = [str(item) for item in row.get("flags") or [] if str(item)]
    if flags:
        return ", ".join(flags)
    return "spot_review_required" if row.get("review_required") else "spot_review_recorded"


def _disagreement_severity(row: dict) -> float:
    flags = {str(item) for item in row.get("flags") or [] if str(item)}
    if "SECOND_PASS_DISAGREEMENT" in flags or "DISAGREEMENT" in flags:
        return 1.0
    if "SECOND_PASS_CONFIRMED" in flags:
        return 0.25
    return 0.0
