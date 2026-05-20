# {spot} Ingestion Contract

Current canonical intake schema version: `spot.input-row.v1alpha1`

## Principle

The important contract is not `.xlsx` itself.
The important contract is the canonical input row schema that every importer must produce before classification.

Today, `{spot}` ships only the `.xlsx` adapter.
That workbook adapter is one source-specific parser that normalizes accepted rows into the canonical intake shape.

## Accepted Source Today

- file type: `.xlsx`
- source of truth: first worksheet only
- one language per run

## Workbook Adapter Requirements

Required first columns:

1. `Item number`
2. `Post text`
3. `Category`

Current workbook intake rules:

- the first worksheet must exist
- the required first columns must match exactly
- fully blank rows are ignored
- empty text rows are retained for governed fallback handling
- corrupted workbooks fail fast with an explicit error
- `Original Row Index` is honored when present

## Canonical Input Row Schema

Every accepted row is normalized into a canonical row with:

- `schema_version`
- `sequence_index`
- `row_index`
- `item_number`
- `post_text`
- `source_category`
- `row_hash`
- `post_text_sha256`
- `post_text_length`
- `normalization_status`
- `provenance.source_type`
- `provenance.source_name`
- `provenance.source_sheet`
- `provenance.source_row_index`

Semantics:

- `sequence_index`: stable position within the accepted input stream
- `row_index`: canonical row identity used by downstream runtime surfaces
- `source_category`: source-supplied category field, if any; not live classification truth
- `row_hash`: deterministic hash of `item_number` and `post_text`
- `normalization_status`: currently `accepted` for the workbook adapter
- provenance fields: preserve where the row came from before classification

## Validation Boundary

Validation happens before classification.

The workbook adapter must reject or fail fast for:

- non-`.xlsx` input
- oversized workbook files
- invalid workbook structure
- invalid header order
- null-byte text content
- rows exceeding maximum post-text length
- workbooks exceeding the maximum row count
- workbooks with no data rows

## Runtime Boundary

After normalization:

- `{spot}` should work from canonical persisted rows
- source format should no longer matter to classification
- exporters should render from canonical rows, not from hidden source-specific assumptions

## Output

Today, `{spot}` still writes a governed `.xlsx` output and appends governed metadata columns.
That output contract is separate from the canonical intake contract.
