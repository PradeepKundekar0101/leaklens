# Public policy wording (robustness test)

Place one publicly available Indian retail health insurance policy wording PDF in this folder.
It is used to test that policy ingestion and clause retrieval cope with a real document whose layout and numbering we did not generate.

Guidelines:

- Download it yourself from the insurer's website or the IRDAI product list; the generator never fetches files from the internet.
- Any individual indemnity health product works (for example a product with room-rent limits, sub-limits and waiting periods).
- Keep the original filename, or rename it to `<insurer>_<product>.pdf`.
- Do not commit documents whose licence forbids redistribution; this folder is for local testing.

The synthetic wordings for the three LeakLens products (`SILVER.pdf`, `GOLD.pdf`, `PLATINUM.pdf`) live one level up and are produced by `uv run python -m scripts.generate_policy_docs`.
