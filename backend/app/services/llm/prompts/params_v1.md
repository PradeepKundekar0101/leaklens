You extract machine-readable policy parameters from an Indian health-insurance policy wording.

Return:
- room_rent_cap_pct / icu_cap_pct: the room-rent and ICU caps as a percent of sum insured per day (e.g. "1% of Sum Insured per day" -> 1.0). null when there is no cap.
- copay_pct: co-payment percent. deductible: rupee amount.
- sub_limits: one entry per procedure sub-limit (procedure_code, limit in rupees, clause_no), using only the procedure codes listed in the request; match the wording's procedure names to those codes.
- initial_days, listed_conditions_months, pre_existing_months: waiting periods.
- clause_refs: one entry per parameter (param, clause_no) for room_rent_cap_pct, icu_cap_pct, copay_pct, deductible, initial_days, listed_conditions_months and pre_existing_months.

Copy values exactly as written. Evidence standard: every value must come from a clause in the text; if a value is not stated, return null for it and omit its clause ref.

{{UNTRUSTED_NOTE}}
