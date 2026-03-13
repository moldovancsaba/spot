# {spot} Ingestion Contract

## Accepted Input

- File type: `.xlsx`
- Source of truth: first worksheet only
- One language per run

## Required First Columns

1. `Item number`
2. `Post text`
3. `Category`

The input schema must match this order exactly for MVP.

## Row Handling Rules

- blank fully-empty rows are ignored
- empty text rows are not silently dropped
- empty text is assigned fallback category and flagged
- corrupted workbooks fail fast with an explicit error

## Output

{spot} writes a new `.xlsx` and appends governed metadata columns.
The input sheet remains the base sheet structure.
