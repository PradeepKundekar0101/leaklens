# Reference policy wordings (robustness test)

Documents in this folder test that policy ingestion and clause retrieval cope with a layout and numbering scheme the synthetic LeakLens wordings do not use.

## SWASTHYA_RAKSHA_PLUS.pdf (generated)

A 30-page wording for a fictional insurer's three-plan individual health product, in the IRDAI standard layout: lettered sections, clause numbers such as `C.1.4`, `Def. n` definitions set in two columns, exclusion codes `Excl01`-`Excl18`, plan comparison tables, a specimen policy schedule and form-style annexures.
The text is original and every page is marked as a specimen; it is not an offer of insurance and does not reproduce any insurer's wording.

Regenerate and ingest it as reference product `PUBLIC` with `make reference`.
The content lives in `backend/scripts/datagen/reference_wording.py` and the layout in `backend/scripts/generate_reference_wording.py`.

## Adding a real insurer's wording

A real document is still the stronger test.

- Download it yourself from the insurer's website or the IRDAI product list; the generators never fetch files from the internet.
- Any individual indemnity health product works (for example a product with room-rent limits, sub-limits and waiting periods).
- Keep the original filename, or rename it to `<insurer>_<product>.pdf`, and ingest it with `uv run python -m scripts.ingest_policy --file <path> --product <ID>`.
- Do not commit documents whose licence forbids redistribution; this folder is for local testing.

The synthetic wordings for the three LeakLens products (`SILVER.pdf`, `GOLD.pdf`, `PLATINUM.pdf`) live one level up and are produced by `uv run python -m scripts.generate_policy_docs`.
