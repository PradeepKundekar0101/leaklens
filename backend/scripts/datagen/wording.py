"""Policy wording content for the synthetic products.

The section and clause structure is fixed; every number that is also a policy parameter is filled in from the
product definition (data/policies/products.json), so the wording and policy_params cannot disagree.
Clause numbers referenced by Product.clause_refs (common.CLAUSE_BASE and the sub-limit clauses) are produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scripts.datagen.common import Product, Reference, sub_limit_clause

INSURER = "Suraksha General Insurance Company Limited (illustrative)"


@dataclass
class Clause:
    number: str
    title: str
    text: str
    bullets: list[str] = field(default_factory=list)


@dataclass
class Section:
    number: int
    title: str
    intro: str
    clauses: list[Clause]
    table: list[list[str]] | None = None


def inr(rupees: float) -> str:
    """Indian digit grouping, no paise when whole: 300000 -> 3,00,000."""
    neg = rupees < 0
    whole = f"{abs(rupees):.2f}"
    w, frac = whole.split(".")
    if len(w) > 3:
        head, tail = w[:-3], w[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        w = ",".join(parts + [tail])
    s = w if frac == "00" else f"{w}.{frac}"
    return f"-{s}" if neg else s


def pct(value: str) -> str:
    """'1.000' -> '1', '12.500' -> '12.5'."""
    s = value.rstrip("0").rstrip(".")
    return s or "0"


# --------------------------------------------------------------------------------------------- definitions
DEFINITIONS: list[tuple[str, str]] = [
    ("Accident", "A sudden, unforeseen and involuntary event caused by external, visible and violent means."),
    (
        "Any one illness",
        "A continuous period of illness, including relapse within 45 days from the date of last consultation with "
        "the hospital or nursing home where treatment was taken.",
    ),
    (
        "AYUSH treatment",
        "Hospitalisation or day care treatment under the Ayurveda, Yoga and Naturopathy, Unani, Siddha and "
        "Homeopathy systems of medicine, taken in an AYUSH hospital that meets the minimum standards notified by "
        "the competent authority.",
    ),
    (
        "Cashless facility",
        "A facility extended by the Company to the Insured Person under which the payment of the costs of treatment "
        "undergone by the Insured Person in accordance with the terms and conditions of this Policy is made directly "
        "to the Network Provider to the extent pre-authorisation is approved.",
    ),
    (
        "Condition precedent",
        "A policy term or condition upon which the Company's liability under the Policy is conditional.",
    ),
    (
        "Congenital anomaly",
        "A condition which is present since birth and which is abnormal with reference to form, structure or "
        "position. An internal congenital anomaly is one not in the visible and accessible parts of the body; an "
        "external congenital anomaly is one in the visible and accessible parts of the body.",
    ),
    (
        "Co-payment",
        "A cost-sharing requirement under this Policy which provides that the Insured Person will bear a specified "
        "percentage of the admissible claim amount. A co-payment does not reduce the Sum Insured.",
    ),
    (
        "Cumulative bonus",
        "Any increase or addition in the Sum Insured granted by the Company without an associated increase in "
        "premium, as specified in the Schedule.",
    ),
    (
        "Day care centre",
        "Any institution established for day care treatment of illness or injury, or a medical setup within a "
        "hospital, which has been registered with the local authorities wherever applicable and is under the "
        "supervision of a registered and qualified Medical Practitioner. It must maintain qualified nursing staff, "
        "a fully equipped operation theatre of its own, and daily records of patients accessible to the Company.",
    ),
    (
        "Day care treatment",
        "Medical treatment or a surgical procedure which is undertaken under general or local anaesthesia in a "
        "hospital or day care centre in less than 24 hours because of technological advancement, and which would "
        "otherwise have required hospitalisation of more than 24 hours. Treatment normally taken on an out-patient "
        "basis is not included in the scope of this definition.",
    ),
    (
        "Deductible",
        "A cost-sharing requirement under this Policy which provides that the Company will not be liable for a "
        "specified rupee amount of the admissible claim, applied before any benefits are payable by the Company. "
        "A deductible does not reduce the Sum Insured.",
    ),
    (
        "Dental treatment",
        "Treatment related to teeth or structures supporting teeth, including examinations, fillings, crowns, "
        "extractions and surgery.",
    ),
    (
        "Disclosure to information norm",
        "The Policy shall be void and all premium paid thereon shall be forfeited to the Company in the event of "
        "misrepresentation, mis-description or non-disclosure of any material fact by the Policyholder.",
    ),
    (
        "Domiciliary hospitalisation",
        "Medical treatment for an illness or injury which in the normal course would require care and treatment at "
        "a hospital but is actually taken while confined at home, because the condition of the patient is such that "
        "he or she is not in a condition to be removed to a hospital, or the patient takes treatment at home on "
        "account of non-availability of a room in a hospital.",
    ),
    (
        "Emergency care",
        "Management for an illness or injury which results in symptoms which occur suddenly and unexpectedly, and "
        "requires immediate care by a Medical Practitioner to prevent death or serious long-term impairment of the "
        "Insured Person's health.",
    ),
    (
        "Grace period",
        "The specified period of time, immediately following the premium due date, during which premium payment "
        "can be made to renew or continue the Policy in force without loss of continuity benefits pertaining to "
        "waiting periods and coverage of pre-existing diseases. Coverage need not be available during the period "
        "for which no premium is received.",
    ),
    (
        "Hospital",
        "Any institution established for in-patient care and day care treatment of illness and injuries which has "
        "been registered as a hospital with the local authorities under the applicable clinical establishments "
        "legislation, or complies with all minimum criteria: at least 10 in-patient beds in towns having a "
        "population of less than 10 lakh and at least 15 in-patient beds in all other places; qualified nursing "
        "staff under its employment round the clock; qualified Medical Practitioners in charge round the clock; a "
        "fully equipped operation theatre of its own where surgical procedures are carried out; and daily records "
        "of patients made accessible to the Company's authorised personnel.",
    ),
    (
        "Hospitalisation",
        "Admission in a hospital for a minimum period of 24 consecutive in-patient care hours, except for specified "
        "procedures and treatments where such admission could be for a period of less than 24 consecutive hours.",
    ),
    (
        "Illness",
        "A sickness or a disease or pathological condition leading to the impairment of normal physiological "
        "function which manifests itself during the Policy period and requires medical treatment.",
    ),
    (
        "Injury",
        "Accidental physical bodily harm excluding illness or disease, solely and directly caused by "
        "external, violent, visible and evident means, which is verified and certified by a Medical Practitioner.",
    ),
    (
        "In-patient care",
        "Treatment for which the Insured Person has to stay in a hospital for more than 24 hours for a covered event.",
    ),
    (
        "Intensive care unit",
        "An identified section, ward or wing of a hospital which is under the constant supervision of a dedicated "
        "Medical Practitioner, and which is specially equipped for the continuous monitoring and treatment of "
        "patients who are in a critical condition or require life support facilities, and where the level of care "
        "and supervision is considerably more sophisticated and intensive than in the ordinary and other wards.",
    ),
    (
        "ICU charges",
        "The amount charged by a hospital towards ICU expenses on a per-day basis, which shall include the expenses "
        "for the ICU bed, general medical support services provided to any ICU patient including monitoring "
        "devices, critical care nursing and intensivist charges.",
    ),
    (
        "Maternity expenses",
        "Medical treatment expenses traceable to childbirth, including complicated deliveries and caesarean "
        "sections incurred during hospitalisation, and expenses towards lawful medical termination of pregnancy "
        "during the Policy period.",
    ),
    (
        "Medical advice",
        "Any consultation or advice from a Medical Practitioner including the issuance of any "
        "prescription or follow-up prescription.",
    ),
    (
        "Medical expenses",
        "Those expenses that an Insured Person has necessarily and actually incurred for medical treatment on "
        "account of illness or accident on the advice of a Medical Practitioner, as long as these are no more than "
        "would have been payable if the Insured Person had not been insured and no more than other hospitals or "
        "doctors in the same locality would have charged for the same medical treatment.",
    ),
    (
        "Medical practitioner",
        "A person who holds a valid registration from the Medical Council of any State, the National Medical "
        "Commission or any other council for Indian medicine or homeopathy set up by the Government of India or a "
        "State Government, and is thereby entitled to practise medicine within its jurisdiction, acting within the "
        "scope and jurisdiction of the licence.",
    ),
    (
        "Medically necessary treatment",
        "Any treatment, test, medication or stay in hospital or part of a stay in hospital which is required for "
        "the medical management of the illness or injury suffered by the Insured Person; must not exceed the level "
        "of care necessary to provide safe, adequate and appropriate medical care in scope, duration or intensity; "
        "must have been prescribed by a Medical Practitioner; and must conform to the professional standards widely "
        "accepted in international medical practice or by the medical community in India.",
    ),
    (
        "Network provider",
        "Hospitals or health care providers enlisted by the Company, or by a TPA and the Company "
        "together, to provide medical services to an Insured Person by a cashless facility.",
    ),
    ("Non-network provider", "Any hospital, day care centre or other provider that is not part of the network."),
    (
        "Notification of claim",
        "The process of intimating a claim to the Company or TPA through any of the recognised modes of communication.",
    ),
    (
        "Package rate",
        "The all-inclusive rate agreed in writing between the Company and a Network Provider for the procedure "
        "charges of a defined treatment or surgery, as set out in the Network Provider's tariff schedule.",
    ),
    (
        "Pre-existing disease",
        "Any condition, ailment, injury or disease that is diagnosed by a physician not more than 36 months prior "
        "to the date of commencement of the Policy issued by the Company or its reinstatement, or for which medical "
        "advice or treatment was recommended by, or received from, a physician not more than 36 months prior to the "
        "date of commencement of the Policy or its reinstatement.",
    ),
    (
        "Pre-hospitalisation medical expenses",
        "Medical expenses incurred during the period immediately before the Insured Person is hospitalised, "
        "provided that such expenses are incurred for the same condition for which the subsequent hospitalisation "
        "was required and the in-patient hospitalisation claim is admissible by the Company.",
    ),
    (
        "Post-hospitalisation medical expenses",
        "Medical expenses incurred during the period immediately after the Insured Person is discharged from the "
        "hospital, provided that such expenses are for the same condition for which the earlier hospitalisation "
        "was required and the in-patient hospitalisation claim is admissible by the Company.",
    ),
    (
        "Reasonable and customary charges",
        "The charges for services or supplies which are the standard charges for the specific provider and "
        "consistent with the prevailing charges in the geographical area for identical or similar services, taking "
        "into account the nature of the illness or injury involved.",
    ),
    (
        "Room rent",
        "The amount charged by a hospital per day towards room and boarding expenses. Nursing, operation theatre "
        "and professional fees are billed separately and are the associated medical expenses referred to in "
        "clause 4.4.",
    ),
    (
        "Maximum retail price (MRP)",
        "The maximum price, inclusive of all taxes, printed on the pack of a drug, consumable, implant or device in "
        "accordance with the Legal Metrology (Packaged Commodities) Rules and the applicable price-control orders.",
    ),
    (
        "Surgery or surgical procedure",
        "Manual and / or operative procedures required for treatment of an illness or injury, correction of "
        "deformities and defects, diagnosis and cure of diseases, relief from suffering or prolongation of life, "
        "performed in a hospital or day care centre by a Medical Practitioner.",
    ),
    (
        "Unproven / experimental treatment",
        "Treatment, including drug experimental therapy, which is not based on established medical practice in India.",
    ),
    (
        "Waiting period",
        "A period from the inception of this Policy during which specified diseases, procedures or treatments are "
        "not covered. On completion of the period, those diseases, procedures or treatments are covered provided "
        "the Policy has been continuously renewed without any break.",
    ),
]

EXCLUSIONS: list[tuple[str, str]] = [
    (
        "Investigation and evaluation",
        "Expenses related to any admission primarily for diagnostics and evaluation "
        "purposes only, and any diagnostic expenses which are not related or not incidental to the current diagnosis "
        "and treatment.",
    ),
    (
        "Rest cure, rehabilitation and respite care",
        "Expenses related to any admission primarily for enforced bed "
        "rest and not for receiving treatment, including custodial care at home or in a nursing facility, and any "
        "services for people who are terminally ill to address physical, social, emotional and spiritual needs.",
    ),
    (
        "Obesity and weight control",
        "Expenses related to the surgical treatment of obesity unless the conditions "
        "prescribed in the applicable regulatory guidance, including a body mass index threshold with documented "
        "co-morbidities and failure of less invasive methods of weight loss, are all fulfilled.",
    ),
    (
        "Change of gender treatments",
        "Expenses related to any treatment, including surgical management, to change "
        "characteristics of the body to those of the opposite sex.",
    ),
    (
        "Cosmetic or plastic surgery",
        "Expenses for cosmetic or plastic surgery or any treatment to change "
        "appearance unless for reconstruction following an accident, burn or cancer, or as part of medically "
        "necessary treatment to remove a direct and immediate health risk, certified by the attending practitioner.",
    ),
    (
        "Hazardous or adventure sports",
        "Expenses related to any treatment necessitated due to participation as a "
        "professional in hazardous or adventure sports, including para-jumping, rock climbing, mountaineering, "
        "rafting, motor racing, horse racing, scuba diving and hand gliding.",
    ),
    (
        "Breach of law",
        "Expenses for treatment directly arising from or consequent upon any Insured Person "
        "committing or attempting to commit a breach of law with criminal intent.",
    ),
    (
        "Excluded providers",
        "Expenses incurred towards treatment in any hospital or by any Medical Practitioner or "
        "other provider specifically excluded by the Company and disclosed on its website or notified to the "
        "policyholders, except for life-threatening situations or following an accident up to the stage of "
        "stabilisation.",
    ),
    (
        "Substance abuse",
        "Treatment for alcoholism, drug or substance abuse or any addictive condition and the consequences thereof.",
    ),
    (
        "Health hydros and wellness",
        "Treatments received in health hydros, nature cure clinics, spas or similar "
        "establishments, or private beds registered as a nursing home attached to such establishments, or where "
        "admission is arranged wholly or partly for domestic reasons.",
    ),
    (
        "Dietary supplements",
        "Dietary supplements and substances that can be purchased without prescription, "
        "including vitamins, minerals and organic substances, unless prescribed by a Medical Practitioner as part of "
        "hospitalisation or day care treatment.",
    ),
    (
        "Refractive error",
        "Expenses related to the treatment for correction of eyesight due to refractive error less than 7.5 dioptres.",
    ),
    (
        "Unproven treatments",
        "Expenses related to any unproven treatment, services and supplies for or in "
        "connection with any treatment. Unproven treatments are those lacking significant medical documentation to "
        "support their effectiveness.",
    ),
    (
        "Non-payable items",
        "Items of expenditure listed in Annexure I (the list of items not payable, items "
        "subsumed into room charges, items subsumed into procedure charges and items subsumed into the cost of "
        "treatment, as standardised by the Authority) are not payable under this Policy. These include, without "
        "limitation, gloves, masks, caps, shoe covers, admission kits, attendant charges, toiletries, diapers, "
        "television charges, laundry charges, thermometers, nebuliser kits and crepe bandages. Where such items are "
        "billed separately they shall be deducted in full from the admissible claim.",
    ),
    (
        "Sterility and infertility",
        "Expenses related to sterility and infertility, including any type of "
        "contraception, sterilisation, assisted reproduction services such as artificial insemination and advanced "
        "reproductive technologies, gestational surrogacy and reversal of sterilisation.",
    ),
    (
        "Maternity outside the benefit",
        "Medical treatment expenses traceable to childbirth, except to the extent "
        "covered under clause 2.10 and subject to the sub-limits in Section 6.",
    ),
    (
        "War and nuclear perils",
        "Treatment directly or indirectly arising from war, invasion, acts of foreign "
        "enemies, hostilities, civil war, rebellion or revolution, or from nuclear, chemical or biological "
        "weapons, or radioactive contamination.",
    ),
    (
        "Self-inflicted injury",
        "Intentional self-inflicted injury or attempted suicide while sane or insane, to "
        "the extent permitted by the applicable law.",
    ),
    ("Dental treatment", "Dental treatment, unless necessitated by an accident and requiring hospitalisation."),
    (
        "Domiciliary items",
        "Any expenses for external durable medical equipment of any kind used for diagnosis or "
        "treatment, including CPAP, CAPD, infusion pumps, ambulatory devices and walkers, wheelchairs and crutches.",
    ),
]

GENERAL_CONDITIONS: list[tuple[str, str]] = [
    (
        "Disclosure of information",
        "The Policy shall be void and all premium paid thereon shall be forfeited to "
        "the Company in the event of misrepresentation, mis-description or non-disclosure of any material fact by "
        "the Policyholder. Material facts include all relevant information sought by the Company in the proposal "
        "form and other connected documents to enable it to take an informed decision on underwriting the risk.",
    ),
    (
        "Condition precedent to admission of liability",
        "The terms and conditions of the Policy must be fulfilled "
        "by the Insured Person for the Company to make any payment for a claim arising under the Policy.",
    ),
    (
        "Material change",
        "The Insured Person shall notify the Company in writing of any material change in the risk "
        "in relation to the declaration made in the proposal form or medical examination report at each renewal, "
        "and the Company may adjust the scope of cover or premium accordingly.",
    ),
    (
        "Records to be maintained",
        "The Insured Person shall keep an accurate record containing all relevant "
        "medical records and shall allow the Company or its representatives to inspect such records. The "
        "Policyholder or Insured Person shall furnish such additional information as the Company may require for "
        "assessment of the claim within the timelines specified.",
    ),
    (
        "Fraud",
        "If any claim made by the Insured Person is in any respect fraudulent, or if any false statement or "
        "declaration is made or used in support thereof, or if any fraudulent means or devices are used by the "
        "Insured Person or anyone acting on his or her behalf to obtain any benefit under this Policy, all benefits "
        "under this Policy and the premium paid shall be forfeited. Any amount already paid against claims found "
        "fraudulent shall be repaid by the recipients, who shall be jointly and severally liable. Fraud includes "
        "the suggestion as a fact of that which is not true, the active concealment of a fact, any other act "
        "fitted to deceive, and the submission of the same bill or document in support of more than one claim. The "
        "Company shall not repudiate the claim or forfeit the Policy benefits on the ground of fraud if the Insured "
        "Person proves that the misstatement was true to the best of his or her knowledge and there was no "
        "deliberate intention to suppress the fact.",
    ),
    (
        "Cancellation",
        "The Policyholder may cancel this Policy by giving 7 days' written notice. The Company shall "
        "refund the premium for the unexpired policy period on a proportionate basis provided no claim has been "
        "made. The Company may cancel the Policy at any time on grounds of misrepresentation, non-disclosure of "
        "material facts or fraud by the Insured Person, by giving 15 days' written notice, without refund of "
        "premium.",
    ),
    (
        "Renewal of policy",
        "The Policy shall ordinarily be renewable except on grounds of fraud or "
        "misrepresentation by the Insured Person. Renewal shall not be denied on the ground that the Insured Person "
        "had made a claim or claims in the preceding policy years. A grace period of 30 days is available for "
        "annual premium payment; coverage is not available for the period for which no premium is received.",
    ),
    (
        "Migration",
        "The Insured Person may migrate to a similar health insurance policy offered by the Company at "
        "the time of renewal, with credit for completed waiting periods to the extent of the previous sum insured, "
        "subject to the applicable regulatory guidance.",
    ),
    (
        "Portability",
        "The Insured Person may port the Policy to another insurer by applying at least 15 days "
        "before, but not earlier than 60 days from, the premium renewal date. On portability, the accrued "
        "continuity benefits in waiting periods shall be passed on to the acquiring insurer to the extent of the "
        "previous sum insured.",
    ),
    (
        "Moratorium period",
        "After completion of sixty continuous months of coverage, including portability and "
        "migration, no claim shall be contestable by the Company on grounds of non-disclosure or "
        "misrepresentation, except on grounds of established fraud. Claims remain subject to the policy limits, "
        "sub-limits, co-payments and deductibles as per the policy contract.",
    ),
    (
        "Free look period",
        "The Policyholder has 30 days from the date of receipt of the policy document to review "
        "the terms and conditions and to return the Policy if not acceptable, provided no claim has been made. "
        "The Company shall refund the premium after deducting proportionate risk premium for the period of cover "
        "and the expenses incurred on medical examination and stamp duty.",
    ),
    (
        "Premium payment in instalments",
        "Where the Policyholder has opted to pay the premium in instalments, a "
        "grace period of 15 days is allowed for each instalment. Coverage is not available for the period for "
        "which no instalment is received, and the Company may recover the outstanding instalments from any claim "
        "payable during the policy year.",
    ),
    (
        "Possibility of revision of terms",
        "The Company may revise or modify the terms of the Policy, including "
        "premium rates, with prior approval of the Authority. The Insured Person shall be notified at least 90 days "
        "before the revision is effective.",
    ),
    (
        "Withdrawal of policy",
        "In the likelihood of this product being withdrawn in future, the Company will "
        "intimate the Insured Person at least 90 days prior to the expiry of the Policy, and the Insured Person "
        "will have the option to migrate to a similar product available with the Company at the time of renewal.",
    ),
    (
        "Nomination",
        "The Policyholder is required at the inception of the Policy to make a nomination for the "
        "purpose of payment of claims in the event of the death of the Policyholder. Any change of nomination "
        "shall be communicated to the Company in writing and becomes effective on endorsement.",
    ),
    (
        "Multiple policies",
        "Where the Insured Person holds more than one indemnity policy, he or she may choose the "
        "policy under which a claim is settled. Where the admissible amount exceeds the sum insured under a single "
        "policy, the balance may be claimed under the other policies, subject to their terms.",
    ),
    (
        "Territorial limit",
        "All medical treatment for the purpose of this Policy will have to be taken in India "
        "only, and claims shall be payable in Indian rupees.",
    ),
    (
        "Notices",
        "Any notice, direction, instruction or other communication related to the Policy should be made "
        "in writing to the address or electronic contact details specified in the Schedule, and shall be deemed "
        "received when delivered.",
    ),
]

CLAIMS_PROCEDURE: list[tuple[str, str]] = [
    (
        "Notification of claim",
        "The Insured Person shall notify the Company or its TPA of any hospitalisation "
        "within 24 hours of an emergency admission, and at least 48 hours before a planned admission, quoting the "
        "policy number, the name of the hospital, the provisional diagnosis and the expected date of admission. "
        "Delay in notification may be condoned where the Insured Person demonstrates that it was unavoidable.",
    ),
    (
        "Cashless facility",
        "Cashless treatment is available only at Network Providers. The Network Provider shall "
        "submit a pre-authorisation request in the prescribed format, which the Company shall decide within one "
        "hour of receipt of complete information. Final authorisation shall be issued within three hours of "
        "receipt of the discharge request from the hospital.",
    ),
    (
        "Reimbursement claims",
        "For treatment at a Non-network Provider, or where cashless treatment is denied or "
        "not availed, the Insured Person shall submit the claim with the documents listed in Annexure III within "
        "30 days of discharge from hospital. Claims for post-hospitalisation expenses shall be submitted within 15 "
        "days of completion of the post-hospitalisation treatment.",
    ),
    (
        "Claim documents",
        "The claim must be supported by the original final bill with an itemised break-up, "
        "payment receipts, the discharge summary, investigation reports, prescriptions, pharmacy bills, implant "
        "invoices and stickers where applicable, and a cancelled cheque or bank details of the proposer. The "
        "Company may call for additional documents only once, within seven days of receipt of the claim.",
    ),
    (
        "Assessment of claim",
        "Claims are assessed against the policy terms in the following order: removal of "
        "non-payable items and items not related to the stay; capping of items at contracted package rates and at "
        "MRP; room-rent and ICU limits with proportionate deduction; procedure sub-limits; deductible; co-payment; "
        "and finally the available Sum Insured.",
    ),
    (
        "Network tariff",
        "For treatment at a Network Provider, the Company's liability for procedure charges shall "
        "not exceed the package rate agreed with that Network Provider for the procedure, as set out in clause 4.6.",
    ),
    (
        "Duplicate and overlapping claims",
        "A claim submitted for the same Insured Person, hospital, date of "
        "admission and amount as a claim already submitted shall be treated as a duplicate and shall not be "
        "payable. Bills or documents already relied upon in another claim shall not be accepted in support of a "
        "fresh claim.",
    ),
    (
        "Settlement of claim",
        "The Company shall settle or reject a claim within 30 days of receipt of the last "
        "necessary document. In case of delay, the Company shall pay interest at a rate 2% above the bank rate "
        "from the date of receipt of the last necessary document to the date of payment.",
    ),
    (
        "Rejection of claim",
        "Where a claim is rejected or partially settled, the Company shall communicate the "
        "specific reasons in writing, quoting the relevant clause of the Policy, and shall inform the Insured "
        "Person of the grievance redressal avenues available under Section 10.",
    ),
    (
        "Payment of claim",
        "All claims shall be paid in Indian rupees by electronic transfer to the bank account of "
        "the proposer or the Network Provider, as applicable.",
    ),
]

GRIEVANCE: list[tuple[str, str]] = [
    (
        "Grievance officer",
        "In case of any grievance, the Insured Person may contact the Company's grievance "
        "officer at any branch office or through the contact details in the Schedule. The Company shall acknowledge "
        "the grievance within three working days and resolve it within 14 days.",
    ),
    (
        "Escalation",
        "If the Insured Person is not satisfied with the resolution, the grievance may be escalated to "
        "the Chief Grievance Officer of the Company, who shall respond within seven days.",
    ),
    (
        "Integrated grievance management system",
        "Grievances may also be registered on the Authority's online "
        "grievance management portal (Bima Bharosa) for tracking and escalation.",
    ),
    (
        "Insurance Ombudsman",
        "If the grievance remains unresolved for 30 days, or the Insured Person is not "
        "satisfied with the response, he or she may approach the Insurance Ombudsman having jurisdiction, in "
        "accordance with the Insurance Ombudsman Rules, within one year of the Company's final reply.",
    ),
    (
        "Senior citizens",
        "Grievances of Insured Persons aged 60 years or more shall be handled through a separate "
        "channel with priority resolution.",
    ),
]

NON_PAYABLE_LISTS: dict[str, list[str]] = {
    "List I - items for which coverage is not available": [
        "Baby food",
        "Baby utilities charges",
        "Beauty services",
        "Belts / braces",
        "Buds",
        "Cold pack / hot pack",
        "Carry bags",
        "Email / internet charges",
        "Food charges (other than the patient's diet)",
        "Leggings",
        "Laundry charges",
        "Mineral water",
        "Sanitary pad",
        "Telephone charges",
        "Guest services",
        "Crepe bandage",
        "Diaper of any type",
        "Eyelet collar",
        "Slings",
        "Blood grouping and cross-matching of donor samples",
        "Service charges where nursing charge is also charged",
        "Television charges",
        "Surcharges",
        "Attendant charges",
        "Extra diet of patient (other than that which forms part of the bed charge)",
        "Birth certificate",
        "Certificate charges",
        "Courier charges",
        "Conveyance charges",
        "Medical certificate",
        "Medical records",
        "Photocopies charges",
        "Mortuary charges",
        "Walking aids charges",
        "Oxygen cylinder (for usage outside the hospital)",
        "Spacer",
        "Spirometer",
        "Nebuliser kit",
        "Steam inhaler",
        "Arm sling",
        "Thermometer",
        "Cervical collar",
        "Splint",
        "Diabetic footwear",
        "Knee braces (long / short / hinged)",
        "Knee immobiliser / shoulder immobiliser",
        "Lumbo-sacral belt",
        "Nimbus bed or water or air bed charges",
        "Ambulance collar",
        "Ambulance equipment",
        "Abdominal binder",
        "Private nurses charges - special nursing charges",
        "Sugar-free tablets",
        "Creams, powders, lotions (toiletries)",
        "ECG electrodes",
        "Gloves",
        "Nebulisation kit",
        "Any kit with no details mentioned (delivery kit, ortho kit, recovery kit, etc.)",
        "Kidney tray",
        "Mask",
        "Ounce glass",
        "Oxygen mask",
        "Pelvic traction belt",
        "Pan can",
        "Trolley cover",
        "Urometer, urine jug",
        "Vasofix safety",
    ],
    "List II - items subsumed into room charges": [
        "Baby charges (unless specified / indicated)",
        "Hand wash",
        "Shoe cover",
        "Caps",
        "Cradle charges",
        "Comb",
        "Eau-de-cologne / room fresheners",
        "Foot cover",
        "Gown",
        "Slippers",
        "Tissue paper",
        "Toothpaste",
        "Toothbrush",
        "Bed pan",
        "Face mask",
        "Flexi mask",
        "Hand holder",
        "Sputum cup",
        "Disinfectant lotions",
        "Luxury tax",
        "HVAC",
        "House-keeping charges",
        "Air conditioner charges",
        "IM / IV injection charges",
        "Clean sheet",
        "Blanket / warmer blanket",
        "Admission kit",
        "Diabetic chart charges",
        "Documentation charges / administrative expenses",
        "Discharge procedure charges",
        "Daily chart charges",
        "Entrance pass / visitors pass charges",
        "Expenses related to prescription on discharge",
        "File opening charges",
        "Incidental expenses / miscellaneous charges (not explained)",
        "Patient identification band / name tag",
        "Pulse oximeter charges",
    ],
    "List III - items subsumed into procedure charges": [
        "Hair removal cream",
        "Disposables razors charges (for site preparations)",
        "Eye pad",
        "Eye shield",
        "Camera cover",
        "DVD, CD charges",
        "Gauze soft",
        "Gauze",
        "Ward and theatre booking charges",
        "Arthroscopy and endoscopy instruments",
        "Microscope cover",
        "Surgical blades, harmonic scalpel, shaver",
        "Surgical drill",
        "Eye kit",
        "Eye drape",
        "X-ray film",
        "Boyles apparatus charges",
        "Cotton",
        "Cotton bandage",
        "Surgical tape",
        "Apron",
        "Torniquet",
        "Orthobundle, gynaec bundle",
    ],
    "List IV - items subsumed into costs of treatment": [
        "Admission / registration charges",
        "Hospitalisation for evaluation / diagnostic purpose",
        "Urine container",
        "Blood reservation charges and ante-natal booking charges",
        "Bipap machine",
        "CPAP / CAPD equipment",
        "Infusion pump - cost",
        "Hydrogen peroxide, spirit, disinfectants etc.",
        "Nutrition planning charges - dietician charges - diet charges",
        "HIV kit",
        "Antiseptic mouthwash",
        "Lozenges",
        "Mouth paint",
        "Vaccination charges",
        "Alcohol swabs",
        "Scrub solution / sterillium",
        "Glucometer and strips",
        "Urine bag",
    ],
}

DAY_CARE = [
    "Cataract surgery",
    "Lithotripsy",
    "Coronary angiography",
    "Dialysis",
    "Radiotherapy",
    "Chemotherapy",
    "Tonsillectomy",
    "Adenoidectomy",
    "Septoplasty",
    "Functional endoscopic sinus surgery",
    "Myringoplasty",
    "Tympanoplasty",
    "Stapedectomy",
    "Mastoidectomy",
    "Excision of nasal polyp",
    "Dacryocystorhinostomy",
    "Trabeculectomy",
    "Vitrectomy",
    "Squint correction",
    "Pterygium excision",
    "Chalazion excision",
    "Laser photocoagulation",
    "Corneal transplant",
    "Haemorrhoidectomy",
    "Fistulectomy",
    "Fissurectomy",
    "Pilonidal sinus excision",
    "Incision and drainage of abscess",
    "Excision of lipoma",
    "Excision of sebaceous cyst",
    "Inguinal hernia repair (laparoscopic)",
    "Umbilical hernia repair",
    "Hydrocele surgery",
    "Varicocele surgery",
    "Circumcision",
    "Orchidopexy",
    "Cystoscopy with biopsy",
    "Ureteroscopy",
    "Removal of DJ stent",
    "TURBT",
    "Percutaneous nephrostomy",
    "Endoscopic retrograde cholangiopancreatography",
    "Upper GI endoscopy with banding",
    "Colonoscopy with polypectomy",
    "Liver biopsy",
    "Bone marrow aspiration",
    "Arthroscopic meniscectomy",
    "Arthroscopic debridement",
    "Carpal tunnel release",
    "Trigger finger release",
    "Ganglion excision",
    "Closed reduction of fracture",
    "Removal of implant",
    "Tendon repair",
    "Dilatation and curettage",
    "Hysteroscopy",
    "Colposcopy with biopsy",
    "Cervical cerclage",
    "Laparoscopic tubal procedures",
    "Breast lump excision",
    "Fine-needle aspiration cytology under guidance",
    "Thyroid nodule biopsy",
    "Skin grafting (small area)",
    "Wound debridement",
    "Burns dressing under anaesthesia",
    "Pleural tapping",
    "Ascitic tapping",
    "Lumbar puncture",
    "Central line insertion",
    "Pacemaker battery replacement",
    "Balloon valvotomy",
    "Peripheral angioplasty",
    "AV fistula creation",
    "Varicose vein ablation",
    "Sclerotherapy",
    "Brachytherapy",
    "Intravitreal injection",
    "Botulinum injection for medical indications",
    "Nerve block for pain management",
    "Epidural steroid injection",
    "Electroconvulsive therapy",
    "Endometrial ablation",
    "Excision of skin malignancy",
    "Biopsy of lymph node",
    "Tracheostomy",
    "Foreign body removal (ENT)",
    "Foreign body removal (eye)",
    "Nasal bone reduction",
    "Frenotomy",
    "Excision of ranula",
    "Sialolithotomy",
    "Parotid duct procedures",
    "Prostate biopsy",
    "Urethral dilatation",
    "Meatotomy",
    "Paracentesis of eye",
    "YAG capsulotomy",
]

CLAIM_DOCS = [
    "Duly completed and signed claim form",
    "Photo identity proof of the patient and the proposer",
    "Original final hospital bill with itemised break-up of every charge",
    "Original payment receipts",
    "Discharge summary signed by the treating doctor",
    "Investigation reports with prescriptions advising the investigations",
    "Pharmacy bills with corresponding prescriptions",
    "Implant invoice and implant stickers, where an implant has been used",
    "Operation theatre notes for surgical procedures",
    "First information report or medico-legal certificate for accident cases, where applicable",
    "Cancelled cheque or bank account details of the proposer (KYC compliant)",
    "Pre-authorisation approval letter, for cashless claims",
]


def build_sections(product: Product, ref: Reference) -> list[Section]:
    """All numbered sections for one product. Clause numbers here must cover product.clause_refs."""
    si_opts = [float(s) for s in product.sum_insured_options]
    procs = ref.procedures.set_index("code")
    rr, ic = product.room_rent_cap_pct, product.icu_cap_pct
    wp = product.waiting_periods
    secs: list[Section] = []

    secs.append(
        Section(
            1,
            "Definitions",
            "The terms defined below have the meanings ascribed to them wherever they appear in this Policy. Words "
            "in the singular include the plural and references to the masculine include the feminine.",
            [Clause(f"1.{i}", t, d) for i, (t, d) in enumerate(DEFINITIONS, start=1)],
        )
    )

    si_text = ", ".join(f"Rs {inr(s)}" for s in si_opts)
    secs.append(
        Section(
            2,
            "Coverage",
            "The Company will indemnify the Insured Person for medically necessary expenses incurred during the "
            "Policy period, up to the Sum Insured, subject to the limits, waiting periods, exclusions and "
            "conditions of this Policy.",
            [
                Clause(
                    "2.1",
                    "In-patient hospitalisation",
                    "The Company will pay for room, boarding, nursing, "
                    "ICU, surgeon, anaesthetist, consultant and specialist fees, anaesthesia, blood, oxygen, "
                    "operation theatre charges, surgical appliances, medicines and drugs, consumables, "
                    "diagnostic procedures and the cost of prosthetic and other devices or equipment implanted "
                    "internally during a surgical procedure, where the Insured Person is hospitalised for at "
                    "least 24 consecutive hours, subject to Section 4.",
                ),
                Clause(
                    "2.2",
                    "Sum insured",
                    f"The Sum Insured available under {product.name} is one of "
                    f"{si_text} per policy year, as stated in the Schedule. The Sum Insured is the Company's "
                    "maximum liability for all claims in a policy year. Claims paid reduce the Sum Insured "
                    "available for the rest of the policy year; the remaining amount is the balance Sum "
                    "Insured, and no claim shall be payable in excess of it.",
                ),
                Clause(
                    "2.3",
                    "Pre-hospitalisation",
                    "Medical expenses incurred in the 30 days immediately before "
                    "the date of admission, for the same condition, are payable provided the in-patient claim "
                    "is admissible.",
                ),
                Clause(
                    "2.4",
                    "Post-hospitalisation",
                    "Medical expenses incurred in the 60 days immediately after "
                    "discharge, for the same condition, are payable provided the in-patient claim is "
                    "admissible.",
                ),
                Clause(
                    "2.5",
                    "Day care treatment",
                    "Expenses for day care treatment listed in Annexure II, "
                    "undertaken in a hospital or day care centre, are payable, but not expenses for "
                    "out-patient treatment.",
                ),
                Clause(
                    "2.6",
                    "Road ambulance",
                    "Expenses for road ambulance services to transfer the Insured "
                    "Person to a hospital in an emergency, or from one hospital to another for better medical "
                    "facilities, are payable up to Rs 2,000 per hospitalisation.",
                ),
                Clause(
                    "2.7",
                    "Domiciliary hospitalisation",
                    "Domiciliary hospitalisation for a period exceeding "
                    "three consecutive days is payable up to 10% of the Sum Insured, subject to the "
                    "definition in clause 1.14.",
                ),
                Clause(
                    "2.8",
                    "AYUSH treatment",
                    "In-patient AYUSH treatment taken in an AYUSH hospital is payable up to the Sum Insured.",
                ),
                Clause(
                    "2.9",
                    "Organ donor expenses",
                    "In-patient expenses of the donor for harvesting an organ "
                    "donated to the Insured Person are payable, excluding pre- and post-hospitalisation "
                    "expenses of the donor and the cost of the organ.",
                ),
                Clause(
                    "2.10",
                    "Maternity",
                    "Maternity expenses for up to two deliveries during the lifetime of "
                    "the Policy are payable for the female Insured Person, subject to the sub-limits stated in "
                    "Section 6 for the relevant procedure.",
                ),
                Clause(
                    "2.11",
                    "Modern treatment methods",
                    "Robotic surgeries, stereotactic radio-surgery, "
                    "bronchial thermoplasty, oral chemotherapy, immunotherapy and intra-vitreal injections are "
                    "payable up to 50% of the Sum Insured when taken as in-patient or day care treatment.",
                ),
            ],
        )
    )

    secs.append(
        Section(
            3,
            "Exclusions",
            "The Company shall not be liable to make any payment under this Policy for expenses caused by, based "
            "on, arising out of or attributable to any of the following, in addition to the waiting periods in "
            "Section 5.",
            [Clause(f"3.{i}", t, d) for i, (t, d) in enumerate(EXCLUSIONS, start=1)],
        )
    )

    if rr is None:
        rr_text = (
            "There is no limit on room rent under this product; the Insured Person may occupy any room "
            "category, including a single private or deluxe room. Room rent remains subject to the "
            "reasonable and customary charges of the hospital."
        )
        ic_text = "There is no limit on ICU charges under this product, subject to reasonable and customary charges."
        table = None
    else:
        rr_text = (
            f"Room rent and boarding expenses as provided by the hospital are payable up to "
            f"{pct(rr)}% of the Sum Insured per day of hospitalisation. For the Sum Insured options under "
            "this product the daily room-rent limit is shown in the table below."
        )
        ic_text = (
            f"ICU charges are payable up to {pct(ic)}% of the Sum Insured per day of admission in the "
            "intensive care unit."
        )
        table = [
            ["Sum Insured (Rs)", f"Room rent limit per day (Rs) - {pct(rr)}%", f"ICU limit per day (Rs) - {pct(ic)}%"]
        ]
        for s in si_opts:
            table.append([inr(s), inr(s * float(rr) / 100), inr(s * float(ic) / 100)])
    secs.append(
        Section(
            4,
            "Room rent, ICU and related limits",
            "The limits in this Section apply per day of hospitalisation and per claim, before the sub-limits in "
            "Section 6 and the cost-sharing in Section 7.",
            [
                Clause(
                    "4.1",
                    "Application of limits",
                    "The limits below apply to every hospitalisation claim, "
                    "whether settled on a cashless or reimbursement basis.",
                ),
                Clause("4.2", "Room rent", rr_text),
                Clause("4.3", "Intensive care unit", ic_text),
                Clause(
                    "4.4",
                    "Proportionate deduction",
                    "If the Insured Person occupies a room or ICU bed whose "
                    "daily charge exceeds the limit in clause 4.2 or 4.3, the Company shall, in addition to "
                    "the excess room or ICU charge, reduce the associated medical expenses in the same "
                    "proportion as the admissible daily limit bears to the actual daily charge. Associated "
                    "medical expenses are nursing charges, operation theatre charges and surgeon, "
                    "anaesthetist and consultant fees. Proportionate deduction shall not be applied to "
                    "pharmacy and medicines, consumables, implants, diagnostics and ICU charges, and shall not "
                    "be applied where the hospital does not differentiate charges by room category. Where both "
                    "the room and the ICU limits are exceeded, only the larger deduction is applied.",
                ),
                Clause(
                    "4.5",
                    "Maximum retail price",
                    "Drugs, consumables, implants and devices are payable at the "
                    "price billed, but not above the maximum retail price printed on the pack. Any amount "
                    "billed above the maximum retail price shall be deducted.",
                ),
                Clause(
                    "4.6",
                    "Network package rates",
                    "Where treatment is taken at a Network Provider that has "
                    "agreed a package rate with the Company for the procedure, the procedure charges, being "
                    "the operation theatre charges and the surgeon and anaesthetist fees, are payable up to "
                    "that package rate. Any excess is not payable by the Company and shall not be recovered "
                    "from the Insured Person by the Network Provider.",
                ),
                Clause(
                    "4.7",
                    "Reasonable and customary charges",
                    "All expenses are payable only to the extent "
                    "they are reasonable and customary for the treatment in the locality.",
                ),
            ],
            table,
        )
    )

    listed = [c for c in wp["listed_procedures"]]
    bullets = [f"{procs.loc[c, 'name']} ({c}, ICD-10 {procs.loc[c, 'icd10']})" for c in listed]
    secs.append(
        Section(
            5,
            "Waiting periods",
            "Expenses related to the treatment of the conditions below are not payable until the stated waiting "
            "period has been served with continuous coverage under this Policy.",
            [
                Clause(
                    "5.1",
                    "General",
                    "Waiting periods are counted from the date of inception of the first "
                    "policy with the Company, provided the Policy has been renewed without a break. Where the "
                    "Sum Insured is increased, the waiting periods apply afresh to the increased amount.",
                ),
                Clause(
                    "5.2",
                    "Initial waiting period",
                    f"Expenses related to the treatment of any illness within "
                    f"{wp['initial_days']} days from the first policy commencement date are excluded, except "
                    "claims arising due to an accident.",
                ),
                Clause(
                    "5.3",
                    "Specified diseases and procedures",
                    f"Expenses related to the treatment of the "
                    f"following listed conditions, surgeries and treatments are excluded until the expiry of "
                    f"{wp['listed_conditions_months']} months of continuous coverage after the date of "
                    "inception of the first policy, unless they arise from an accident:",
                    bullets,
                ),
                Clause(
                    "5.4",
                    "Pre-existing diseases",
                    f"Expenses related to the treatment of a pre-existing "
                    f"disease declared in the proposal form, or found at the time of a claim to have been "
                    f"pre-existing, and its direct complications, are excluded until the expiry of "
                    f"{wp['pre_existing_months']} months of continuous coverage after the date of inception of "
                    "the first policy.",
                ),
                Clause(
                    "5.5",
                    "Credit for prior coverage",
                    "Where the Insured Person was covered under a health "
                    "insurance policy with an Indian insurer without a break, the waiting periods shall be "
                    "reduced by the period of prior continuous coverage to the extent of the prior sum "
                    "insured.",
                ),
            ],
        )
    )

    sub_clauses = [
        Clause(
            "6.1",
            "General",
            "The following sub-limits are the maximum amounts payable for all expenses of a "
            "hospitalisation for the stated procedure, after the limits in Section 4 and before the deductible "
            "and co-payment in Section 7. They form part of, and do not increase, the Sum Insured."
            + ("" if product.sub_limits else " No procedure sub-limits apply under this product."),
        ),
    ]
    for i, (code, value) in enumerate(product.sub_limits.items()):
        name = procs.loc[code, "name"]
        unit = (
            " per eye"
            if code == "PR_CATARACT"
            else " per delivery"
            if "DELIVERY" in code or "CSECTION" in code
            else " per hospitalisation"
        )
        sub_clauses.append(
            Clause(
                sub_limit_clause(i),
                name,
                f"Expenses for {name.lower()} ({code}) are payable up to "
                f"Rs {inr(float(value))}{unit}, including pre- and post-hospitalisation expenses.",
            )
        )
    secs.append(Section(6, "Sub-limits", "Sub-limits apply per Insured Person per policy year.", sub_clauses))

    cp, ded = float(product.copay_pct), float(product.deductible)
    secs.append(
        Section(
            7,
            "Co-payment and deductible",
            "The cost-sharing below is borne by the Insured Person. It is not a deduction for an inadmissible "
            "expense and does not reduce the Sum Insured.",
            [
                Clause(
                    "7.1",
                    "Co-payment",
                    (
                        f"A co-payment of {pct(product.copay_pct)}% applies to every admissible "
                        "claim, after the deductible, and is borne by the Insured Person."
                    )
                    if cp
                    else "No co-payment applies under this product (co-payment 0%).",
                ),
                Clause(
                    "7.2",
                    "Deductible",
                    (
                        f"A deductible of Rs {inr(ded)} per claim applies to every "
                        "admissible claim before the co-payment, and is borne by the Insured Person."
                    )
                    if ded
                    else "No deductible applies under this product (deductible Rs 0).",
                ),
                Clause(
                    "7.3",
                    "Order of application",
                    "The deductible is applied to the admissible amount after "
                    "Sections 4 and 6; the co-payment is then applied to the remainder; the Company's payment "
                    "is finally limited to the balance Sum Insured under clause 2.2.",
                ),
            ],
        )
    )

    secs.append(
        Section(
            8,
            "Claims procedure",
            "Compliance with the procedure below is a condition precedent to the admission of liability.",
            [Clause(f"8.{i}", t, d) for i, (t, d) in enumerate(CLAIMS_PROCEDURE, start=1)],
        )
    )
    secs.append(
        Section(
            9,
            "General terms and conditions",
            "The following conditions apply to the Policy as a whole.",
            [Clause(f"9.{i}", t, d) for i, (t, d) in enumerate(GENERAL_CONDITIONS, start=1)],
        )
    )
    secs.append(
        Section(
            10,
            "Grievance redressal",
            "The Company is committed to fair treatment of its customers and to prompt resolution of grievances.",
            [Clause(f"10.{i}", t, d) for i, (t, d) in enumerate(GRIEVANCE, start=1)],
        )
    )
    return secs


def clause_numbers(sections: list[Section]) -> set[str]:
    return {c.number for s in sections for c in s.clauses}


def illustration_rows(product: Product) -> list[list[str]]:
    """Worked examples of the room-rent proportionate deduction, one per Sum Insured option."""
    if product.room_rent_cap_pct is None:
        return []
    rows = [
        [
            "Sum Insured",
            "Daily limit",
            "Room charged / day",
            "Days",
            "Excess rent",
            "Associated charges",
            "Proportionate cut",
            "Total deduction",
        ]
    ]
    for s in [float(x) for x in product.sum_insured_options]:
        cap = s * float(product.room_rent_cap_pct) / 100
        rent = cap * 1.5
        days = 3
        excess = (rent - cap) * days
        assoc = 60000.0
        cut = assoc * (1 - cap / rent)
        rows.append(
            [
                inr(s),
                inr(cap),
                inr(rent),
                str(days),
                inr(excess),
                inr(assoc),
                inr(round(cut, 2)),
                inr(round(excess + cut, 2)),
            ]
        )
    return rows
