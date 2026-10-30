"""Content of the reference policy wording (a fictional insurer's three-plan individual indemnity product).

This document is deliberately unlike the three synthetic LeakLens wordings: it follows the IRDAI standard layout
(lettered sections, alphanumeric clause numbers such as C.1 and D.2.4, "Def. n" definitions, exclusion codes
Excl01-Excl18, plan comparison tables). It tests that ingestion and clause retrieval cope with numbering and
layout the pipeline was not designed around. The text is original; it is not copied from any insurer's wording.

Every value that a claim decision could depend on is defined once in PLANS and quoted from there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scripts.datagen.wording import inr

INSURER = "Sahyadri General Insurance Company Limited"
PRODUCT = "Swasthya Raksha Plus"
UIN = "SGIHLIP27001V012627"
VERSION = "1.0"
CONTACT = "Toll free 1800 000 0000 (specimen) | care@sahyadri-general.example"
REG_OFFICE = (
    "Registered office (fictional): 4th Floor, Specimen Towers, Senapati Bapat Road, Pune 411016. "
    "IRDAI Reg. No. 000 (specimen). CIN U00000MH2026PLC000000 (specimen)."
)
DISCLAIMER = (
    "SPECIMEN DOCUMENT. Sahyadri General Insurance Company Limited and Swasthya Raksha Plus are fictional. "
    "This wording was written to test the LeakLens claims auditor and is not an offer of insurance."
)

PLAN_NAMES = ("Classic", "Premier", "Elite")


@dataclass(frozen=True)
class Plan:
    name: str
    sum_insured: tuple[int, ...]
    room_rent: str
    icu: str
    pre_post_days: tuple[int, int]
    domiciliary: str
    ayush: str
    road_ambulance: str
    air_ambulance: str
    modern_treatment: str
    cataract: str
    maternity: str
    cumulative_bonus: str
    restoration: str
    health_checkup: str
    pre_existing_months: int
    zone_copay: str
    senior_copay: str


PLANS: dict[str, Plan] = {
    "Classic": Plan(
        name="Classic",
        sum_insured=(300000, 500000),
        room_rent="1% of Sum Insured per day, maximum Rs. 5,000 per day",
        icu="2% of Sum Insured per day, maximum Rs. 10,000 per day",
        pre_post_days=(30, 60),
        domiciliary="10% of Sum Insured, maximum Rs. 50,000",
        ayush="25% of Sum Insured",
        road_ambulance="Rs. 2,000 per hospitalisation",
        air_ambulance="Not covered",
        modern_treatment="50% of Sum Insured for each listed treatment",
        cataract="Rs. 40,000 per eye",
        maternity="Not covered (Excl18 applies)",
        cumulative_bonus="10% of the expiring base Sum Insured per claim-free year, maximum 50%",
        restoration="Not available",
        health_checkup="Once every two claim-free years, up to Rs. 1,500",
        pre_existing_months=36,
        zone_copay="15% if the Insured Person pays a Zone B premium and is treated in Zone A",
        senior_copay="20% of every admissible claim if the entry age is 61 years or more",
    ),
    "Premier": Plan(
        name="Premier",
        sum_insured=(500000, 1000000, 1500000),
        room_rent="Single private air-conditioned room",
        icu="Actual charges, up to Sum Insured",
        pre_post_days=(60, 90),
        domiciliary="20% of Sum Insured",
        ayush="Up to Sum Insured",
        road_ambulance="Rs. 5,000 per hospitalisation",
        air_ambulance="Not covered",
        modern_treatment="50% of Sum Insured for each listed treatment",
        cataract="Rs. 60,000 per eye",
        maternity="Rs. 50,000 normal delivery / Rs. 75,000 caesarean section, after 24 months",
        cumulative_bonus="20% of the expiring base Sum Insured per claim-free year, maximum 100%",
        restoration="100% of base Sum Insured, once per Policy Year",
        health_checkup="Every Policy Year, up to Rs. 2,500",
        pre_existing_months=36,
        zone_copay="15% if the Insured Person pays a Zone B premium and is treated in Zone A",
        senior_copay="20% of every admissible claim if the entry age is 61 years or more",
    ),
    "Elite": Plan(
        name="Elite",
        sum_insured=(2500000, 5000000, 10000000),
        room_rent="Any room category except suite or above",
        icu="Actual charges, up to Sum Insured",
        pre_post_days=(60, 180),
        domiciliary="Up to Sum Insured",
        ayush="Up to Sum Insured",
        road_ambulance="Actual charges",
        air_ambulance="Up to Rs. 5,00,000 per Policy Year",
        modern_treatment="Up to Sum Insured",
        cataract="Actual charges, up to Sum Insured",
        maternity="Rs. 1,00,000 normal delivery / Rs. 1,50,000 caesarean section, after 24 months",
        cumulative_bonus="50% of the expiring base Sum Insured per claim-free year, maximum 100%",
        restoration="100% of base Sum Insured, unlimited times per Policy Year",
        health_checkup="Every Policy Year, up to Rs. 5,000",
        pre_existing_months=24,
        zone_copay="Not applicable",
        senior_copay="Not applicable",
    ),
}


@dataclass
class Clause:
    number: str  # e.g. "C.1", "D.2.4", "Def. 12", "Excl05"
    title: str
    paras: list[str]
    bullets: list[str] = field(default_factory=list)
    table: list[list[str]] | None = None
    widths: tuple[float, ...] | None = None  # table column widths in mm


@dataclass
class Section:
    letter: str
    title: str
    intro: str
    clauses: list[Clause]
    two_column: bool = False


def lakh(rupees: int) -> str:
    """300000 -> 'Rs. 3 lakh', 10000000 -> 'Rs. 1 crore'."""
    if rupees >= 10_000_000:
        v, unit = rupees / 10_000_000, "crore"
    else:
        v, unit = rupees / 100_000, "lakh"
    return f"Rs. {v:g} {unit}"


def plan_row(label: str, attr: str) -> list[str]:
    return [label] + [str(getattr(PLANS[p], attr)) for p in PLAN_NAMES]


# --- Section B: definitions -------------------------------------------------------------------------------------

STANDARD_DEFINITIONS: list[tuple[str, str]] = [
    ("Accident", "a sudden, unforeseen and involuntary event caused by external, visible and violent means."),
    (
        "Any One Illness",
        "a continuous period of illness, including any relapse within 45 days from the date of the last "
        "consultation with the Hospital or Nursing Home where treatment was taken.",
    ),
    (
        "AYUSH Treatment",
        "hospitalisation treatment given under the Ayurveda, Yoga and Naturopathy, Unani, Siddha and Homeopathy "
        "systems of medicine.",
    ),
    (
        "AYUSH Hospital",
        "a healthcare facility in which medical, surgical or para-surgical treatment under an AYUSH system is "
        "carried out, which is either a teaching hospital attached to a recognised AYUSH college, a government "
        "AYUSH hospital, or a facility registered with the local authority that has at least five in-patient "
        "beds, a qualified AYUSH Medical Practitioner in charge round the clock, a dedicated procedure room and "
        "daily records of patients.",
    ),
    (
        "Cashless Facility",
        "a facility under which the Company, directly or through its TPA, pays the Network Provider for the "
        "treatment of an Insured Person to the extent pre-authorisation is approved.",
    ),
    (
        "Condition Precedent",
        "a Policy term or condition on which the Company's liability under the Policy depends.",
    ),
    (
        "Congenital Anomaly",
        "a condition present from birth that is abnormal with reference to form, structure or position. An "
        "Internal Congenital Anomaly is one that is not in the visible and accessible parts of the body; an "
        "External Congenital Anomaly is one that is.",
    ),
    (
        "Co-payment",
        "a cost-sharing requirement under which the Insured Person bears a specified percentage of the "
        "admissible claim amount. A Co-payment does not reduce the Sum Insured.",
    ),
    (
        "Cumulative Bonus",
        "an increase in the Sum Insured granted on renewal for a claim-free Policy Year, without any increase in "
        "premium.",
    ),
    (
        "Day Care Centre",
        "an institution established for day care treatment of illness or injury, or a part of a Hospital, which "
        "is registered with the local authority, is under the supervision of a registered Medical Practitioner, "
        "has qualified nursing staff, a fully equipped operation theatre, and keeps daily records of patients.",
    ),
    (
        "Day Care Treatment",
        "medical treatment or a surgical procedure that is undertaken under general or local anaesthesia in a "
        "Hospital or Day Care Centre in less than 24 hours because of technological advancement, and which would "
        "otherwise have required hospitalisation of more than 24 hours. Treatment normally taken on an "
        "out-patient basis is not Day Care Treatment.",
    ),
    (
        "Deductible",
        "a cost-sharing requirement under which the Company is not liable for a specified rupee amount of the "
        "covered expenses, which the Insured Person bears before any benefit is payable. A Deductible does not "
        "reduce the Sum Insured.",
    ),
    (
        "Dental Treatment",
        "treatment by a dentist, including examinations, fillings, crowns, extractions and surgery.",
    ),
    (
        "Disclosure to Information Norm",
        "the principle that the Policy is void if any material fact is misrepresented, misdescribed or not disclosed.",
    ),
    (
        "Domiciliary Hospitalisation",
        "medical treatment for an illness or injury which in the normal course would require care in a "
        "Hospital but is taken at home because the patient's condition does not allow moving to a Hospital, or "
        "because no Hospital bed was available.",
    ),
    (
        "Emergency Care",
        "management of an illness or injury with symptoms that occur suddenly and unexpectedly, and that require "
        "immediate care by a Medical Practitioner to prevent death or serious long-term impairment.",
    ),
    (
        "Grace Period",
        "the period immediately after the premium due date during which the premium may be paid to renew or "
        "continue the Policy without loss of continuity benefits. Coverage is not available for the period for "
        "which no premium is received.",
    ),
    (
        "Hospital",
        "an institution established for in-patient care and day care treatment of illness or injury which is "
        "registered as a hospital with the local authority under the Clinical Establishments Act, 2010 or the "
        "applicable state law, or which complies with all of the following: at least 10 in-patient beds in "
        "towns with a population of less than ten lakh and at least 15 beds elsewhere; qualified nursing staff "
        "round the clock; qualified Medical Practitioners in charge round the clock; a fully equipped operation "
        "theatre of its own where surgical procedures are carried out; and daily records of patients that are "
        "available to the Company.",
    ),
    (
        "Hospitalisation",
        "admission in a Hospital for a minimum period of 24 consecutive in-patient care hours, except for the "
        "procedures and treatments listed in Annexure I, where the admission may be for less than 24 hours.",
    ),
    (
        "Illness",
        "a sickness, disease or pathological condition leading to the impairment of normal physiological "
        "function that requires medical treatment. An Acute Condition responds quickly to treatment and aims to "
        "return the person to the state of health immediately before the illness. A Chronic Condition has one or "
        "more of the following characteristics: it needs ongoing or long-term monitoring; it continues "
        "indefinitely; it recurs or is likely to recur; it has no known cure; or it needs rehabilitation or "
        "special training.",
    ),
    (
        "Injury",
        "accidental physical bodily harm, excluding illness or disease, solely and directly caused by external, "
        "violent, visible and evident means, which is verified and certified by a Medical Practitioner.",
    ),
    (
        "Inpatient Care",
        "treatment for which the Insured Person has to stay in a Hospital for more than 24 hours for a covered event.",
    ),
    (
        "Intensive Care Unit",
        "an identified section, ward or wing of a Hospital under the constant supervision of a dedicated Medical "
        "Practitioner, specially equipped for the continuous monitoring and treatment of patients in a critical "
        "condition or on life support.",
    ),
    (
        "ICU Charges",
        "the amount charged by a Hospital towards ICU expenses on a per-day basis, which includes the expenses "
        "for the ICU bed, general medical support services provided to an ICU patient including monitoring "
        "devices, critical care nursing and intensivist charges.",
    ),
    (
        "Maternity Expenses",
        "medical treatment expenses traceable to childbirth, including complicated deliveries and caesarean "
        "sections incurred during hospitalisation, and expenses towards lawful medical termination of "
        "pregnancy during the Policy Period.",
    ),
    (
        "Medical Advice",
        "any consultation or advice from a Medical Practitioner, including the issue of a prescription or "
        "follow-up prescription.",
    ),
    (
        "Medical Expenses",
        "expenses that an Insured Person has necessarily and actually incurred for medical treatment on the "
        "advice of a Medical Practitioner, which are no more than would have been payable had the Insured Person "
        "not been insured and no more than other Hospitals or doctors in the same locality would have charged for "
        "the same treatment.",
    ),
    (
        "Medical Practitioner",
        "a person who holds a valid registration from the Medical Council of a state, the National Medical "
        "Commission or the councils for Indian medicine or homeopathy, and is acting within the scope and "
        "jurisdiction of that licence. The Medical Practitioner must not be the Insured Person or a close family "
        "member.",
    ),
    (
        "Medically Necessary Treatment",
        "any treatment, test, medication or stay in Hospital or part of a stay which is required for the medical "
        "management of the illness or injury, does not exceed the level of care necessary to provide safe, "
        "adequate and appropriate medical care in scope, duration or intensity, has been prescribed by a Medical "
        "Practitioner, and conforms to the professional standards widely accepted in medical practice in India.",
    ),
    (
        "Migration",
        "the right given to the Policyholder to transfer the credit gained for pre-existing diseases and time "
        "bound exclusions to another health insurance policy with the same insurer.",
    ),
    (
        "Network Provider",
        "a Hospital enlisted by the Company, a TPA or both to provide medical services to an Insured Person "
        "through a Cashless Facility.",
    ),
    (
        "Newborn Baby",
        "a baby born during the Policy Period and aged up to 90 days.",
    ),
    (
        "Non-Network Provider",
        "any Hospital, Day Care Centre or other provider that is not part of the network.",
    ),
    (
        "Notification of Claim",
        "the process of intimating a claim to the Company or TPA through any of the recognised modes of communication.",
    ),
    (
        "OPD Treatment",
        "treatment in which the Insured Person visits a clinic, Hospital or associated facility for diagnosis "
        "and treatment on the advice of a Medical Practitioner without being admitted as a day care patient or "
        "in-patient.",
    ),
    (
        "Portability",
        "the right given to the Policyholder to transfer the credit gained for pre-existing diseases and time "
        "bound exclusions from one insurer to another.",
    ),
    (
        "Pre-Existing Disease",
        "any condition, ailment, injury or disease that was diagnosed by a physician, or for which medical "
        "advice or treatment was recommended by or received from a physician, within 36 months before the date "
        "of commencement of the first policy issued by the Company.",
    ),
    (
        "Pre-hospitalisation Medical Expenses",
        "Medical Expenses incurred during the period before the Insured Person is hospitalised, provided they "
        "are incurred for the same condition for which the hospitalisation was required, and the in-patient "
        "hospitalisation claim is admissible.",
    ),
    (
        "Post-hospitalisation Medical Expenses",
        "Medical Expenses incurred during the period immediately after the Insured Person is discharged from "
        "Hospital, provided they are incurred for the same condition for which the hospitalisation was "
        "required, and the in-patient hospitalisation claim is admissible.",
    ),
    (
        "Qualified Nurse",
        "a person who holds a valid registration from the Nursing Council of India or the nursing council of "
        "any state in India.",
    ),
    (
        "Reasonable and Customary Charges",
        "the charges for services or supplies which are the standard charges for the specific provider and are "
        "consistent with the prevailing charges in the geographical area for identical or similar services, "
        "taking into account the nature of the illness or injury involved.",
    ),
    (
        "Renewal",
        "the terms on which the contract of insurance can be renewed on mutual consent with a provision of Grace "
        "Period for treating the renewal as continuous for the purpose of gaining credit for pre-existing "
        "diseases, time-bound exclusions and all waiting periods.",
    ),
    (
        "Room Rent",
        "the amount charged by a Hospital towards room and boarding expenses, including the associated medical "
        "expenses, on a per-day basis.",
    ),
    (
        "Unproven or Experimental Treatment",
        "treatment, including drug therapy, which is not based on established medical practice in India.",
    ),
]

SPECIFIC_DEFINITIONS: list[tuple[str, str]] = [
    (
        "Associated Medical Expenses",
        "Room Rent, nursing charges, operation theatre charges, fees of the Medical Practitioner, surgeon, "
        "anaesthetist and specialist, and investigation charges, when conducted within the same Hospital where "
        "the Insured Person was admitted. Pharmacy, consumables, cost of implants, medical devices and "
        "diagnostics are not Associated Medical Expenses.",
    ),
    (
        "Base Sum Insured",
        "the amount stated in the Policy Schedule against the plan opted, before any Cumulative Bonus or "
        "Restoration Amount.",
    ),
    ("Insured Person", "a person named in the Policy Schedule as insured under this Policy."),
    (
        "Package Rate",
        "the all-inclusive rate agreed between the Company or its TPA and a Network Provider for a defined "
        "procedure or treatment, covering every charge listed in the package agreement.",
    ),
    (
        "Policy Period",
        "the period between the date of commencement and the expiry date stated in the Policy Schedule.",
    ),
    (
        "Policy Year",
        "a period of 12 months beginning on the date of commencement of the Policy Period and ending on the last "
        "day of that 12-month period, or any subsequent 12-month period within the Policy Period.",
    ),
    (
        "Proportionate Deduction",
        "the reduction applied to Associated Medical Expenses when the Insured Person occupies a room whose "
        "charge exceeds the room eligibility under the plan opted, as set out in clause C.1.4.",
    ),
    (
        "Restoration Amount",
        "the amount reinstated to the Sum Insured under clause C.14 after the Sum Insured is exhausted or "
        "partly utilised in a Policy Year.",
    ),
    (
        "Single Private Air-Conditioned Room",
        "the most basic category of single-occupancy air-conditioned room with an attached washroom in the "
        "Hospital, without a separate attendant area or sitting area.",
    ),
    (
        "Sum Insured",
        "the Base Sum Insured plus any Cumulative Bonus and Restoration Amount available, which represents the "
        "Company's maximum liability for all claims in a Policy Year.",
    ),
    (
        "TPA",
        "a Third Party Administrator licensed by the IRDAI and engaged by the Company to provide health services "
        "under this Policy.",
    ),
    (
        "Zone",
        "the pricing zone of the city in which the Insured Person resides. Zone A comprises Delhi NCR, Mumbai "
        "(including Thane and Navi Mumbai), Kolkata, Ahmedabad and Vadodara. Zone B comprises all other cities "
        "and towns in India.",
    ),
]


# --- Section C: modern treatments, specified diseases -----------------------------------------------------------

MODERN_TREATMENTS = [
    "Uterine artery embolisation and high-intensity focused ultrasound (HIFU)",
    "Balloon sinuplasty",
    "Deep brain stimulation",
    "Oral chemotherapy",
    "Immunotherapy - monoclonal antibody given as injection",
    "Intra-vitreal injections",
    "Robotic surgeries",
    "Stereotactic radio surgeries",
    "Bronchial thermoplasty",
    "Vaporisation of the prostate (green laser or holmium laser treatment)",
    "Intra-operative neuro monitoring (IONM)",
    "Stem cell therapy: haematopoietic stem cells for bone marrow transplant for haematological conditions",
]

SPECIFIED_DISEASES: list[tuple[str, str]] = [
    ("ENT", "Tonsillectomy, adenoidectomy, mastoidectomy, tympanoplasty, surgery of the nasal septum and sinuses"),
    ("Eye", "Cataract, retinal detachment, glaucoma"),
    (
        "Gynaecology",
        "Hysterectomy (unless for malignancy), fibroids, endometriosis, polycystic ovarian disease, prolapse of "
        "the uterus",
    ),
    ("Gastro-intestinal", "Cholelithiasis and cholecystectomy, pancreatitis, gastric and duodenal ulcers, GERD"),
    ("Proctology", "Haemorrhoids, fissure and fistula in ano, pilonidal sinus"),
    ("Hernia", "All types of hernia, hydrocele, varicocele"),
    ("Urology", "Calculus of the urinary tract, benign prostatic hypertrophy, stricture of the urethra"),
    (
        "Orthopaedics",
        "Joint replacement (unless necessitated by an Accident), arthroscopic knee and shoulder surgery, "
        "osteoarthritis, prolapsed intervertebral disc (unless due to an Accident)",
    ),
    ("Vascular", "Varicose veins and varicose ulcers"),
    ("Skin and soft tissue", "Non-malignant cysts, nodules, polyps and tumours of any kind, including breast lumps"),
    ("Endocrine", "Goitre and other non-malignant disorders of the thyroid gland"),
]

DAY_CARE_BY_SPECIALTY: dict[str, list[str]] = {
    "Cardiology": [
        "Coronary angiography",
        "Percutaneous transluminal coronary angioplasty",
        "Pacemaker implantation",
        "Electrophysiology study and radiofrequency ablation",
        "Insertion of a cardiac loop recorder",
        "Pericardiocentesis",
        "Balloon valvotomy",
    ],
    "Oncology": [
        "Chemotherapy (intravenous and intra-arterial)",
        "Radiotherapy, including brachytherapy",
        "Immunotherapy infusion",
        "Hormone therapy infusion for cancer",
        "Bone marrow aspiration and biopsy",
        "Port-a-cath insertion and removal",
        "Excision of a malignant skin lesion",
    ],
    "Nephrology and urology": [
        "Haemodialysis",
        "Peritoneal dialysis catheter insertion",
        "Extracorporeal shock wave lithotripsy",
        "Ureteroscopic stone removal",
        "Percutaneous nephrostomy",
        "Cystoscopic removal of a stent",
        "Transurethral resection of a bladder tumour",
        "Urethral dilatation",
        "Circumcision (medically necessary)",
        "Meatotomy",
    ],
    "Ophthalmology": [
        "Cataract surgery with intra-ocular lens",
        "Trabeculectomy",
        "Vitrectomy",
        "Laser photocoagulation of the retina",
        "Intra-vitreal injection",
        "Excision of pterygium",
        "Dacryocystorhinostomy",
        "Squint correction",
        "Corneal foreign body removal under anaesthesia",
        "Chalazion excision",
    ],
    "ENT": [
        "Tonsillectomy",
        "Adenoidectomy",
        "Myringotomy with grommet insertion",
        "Septoplasty",
        "Functional endoscopic sinus surgery",
        "Excision of a nasal polyp",
        "Tympanoplasty",
        "Stapedectomy",
        "Direct laryngoscopy with biopsy",
        "Removal of a foreign body from the ear, nose or throat under anaesthesia",
    ],
    "Gastroenterology": [
        "Diagnostic and therapeutic upper GI endoscopy",
        "Colonoscopy with polypectomy",
        "Endoscopic retrograde cholangiopancreatography (ERCP)",
        "Endoscopic variceal banding",
        "Oesophageal dilatation",
        "Percutaneous endoscopic gastrostomy",
        "Liver biopsy",
        "Paracentesis",
    ],
    "General and laparoscopic surgery": [
        "Laparoscopic cholecystectomy",
        "Laparoscopic appendicectomy",
        "Hernia repair (inguinal, umbilical, incisional)",
        "Haemorrhoidectomy",
        "Fissurectomy and sphincterotomy",
        "Fistulectomy",
        "Excision of a pilonidal sinus",
        "Incision and drainage of an abscess",
        "Excision of a lipoma or sebaceous cyst",
        "Breast lump excision",
        "Varicose vein ablation",
        "Hydrocele repair",
        "Thyroid nodule fine needle aspiration under guidance",
    ],
    "Gynaecology": [
        "Dilatation and curettage",
        "Hysteroscopy with polypectomy",
        "Diagnostic laparoscopy",
        "Cervical cerclage",
        "Loop electrosurgical excision of the cervix",
        "Marsupialisation of a Bartholin cyst",
        "Medical termination of pregnancy (where covered)",
        "Ovarian cyst aspiration",
    ],
    "Orthopaedics": [
        "Closed reduction of a fracture or dislocation",
        "Arthroscopic meniscectomy",
        "Arthroscopic ligament repair",
        "Removal of implants",
        "Carpal tunnel release",
        "Trigger finger release",
        "Excision of a ganglion",
        "Tendon repair",
        "Application of a plaster cast under anaesthesia",
        "Joint aspiration and injection under anaesthesia",
    ],
    "Neurology and neurosurgery": [
        "Lumbar puncture (therapeutic)",
        "Nerve block for intractable pain",
        "Botulinum toxin injection for spasticity",
        "Burr hole aspiration",
        "Percutaneous vertebroplasty",
        "Epidural steroid injection",
    ],
    "Pulmonology": [
        "Bronchoscopy with biopsy",
        "Thoracocentesis",
        "Pleural biopsy",
        "Intercostal drain insertion",
        "Bronchial thermoplasty",
    ],
    "Plastic and reconstructive surgery": [
        "Skin grafting after burns or injury",
        "Excision and repair of a scar following an Accident",
        "Repair of a facial laceration",
        "Release of a burn contracture",
    ],
    "Dental and maxillofacial (after Accident only)": [
        "Open reduction of a mandible fracture",
        "Surgical removal of an impacted tooth causing a cyst",
        "Repair of oral lacerations",
    ],
    "Other": [
        "Blood transfusion for a covered illness",
        "Plasmapheresis",
        "Treatment of a snake or animal bite requiring observation under anaesthesia",
        "Desensitisation under supervision for anaphylaxis",
        "Hyperbaric oxygen therapy for a covered condition",
    ],
}

CLAIM_DOCUMENTS = [
    "Duly completed and signed claim form (Annexure V)",
    "Photo identity proof and address proof of the Insured Person",
    "Medical Practitioner's prescription advising admission",
    "Original final bill with a detailed break-up, and the payment receipt",
    "Original discharge summary or discharge certificate",
    "Investigation reports with the Medical Practitioner's prescription for each test",
    "Original pharmacy bills with the prescriptions",
    "Operation theatre notes and the surgeon's certificate (for surgical cases)",
    "Implant invoice and sticker, where an implant is used",
    "First information report or medico-legal certificate (for Accident cases, where conducted)",
    "Indoor case papers, if requested by the Company",
    "Cancelled cheque or bank details with the account holder's name, for electronic payment",
    "KYC documents of the proposer, where the claim exceeds Rs. 1,00,000",
]


# --- Sections ---------------------------------------------------------------------------------------------------


def schedule_rows() -> list[list[str]]:
    p = PLANS
    rows = [
        ["Benefit", "Classic", "Premier", "Elite", "Clause"],
        ["Base Sum Insured options"] + [", ".join(lakh(s) for s in p[n].sum_insured) for n in PLAN_NAMES] + ["E.1.14"],
        plan_row("Room rent eligibility", "room_rent") + ["C.1.2"],
        plan_row("ICU charges", "icu") + ["C.1.3"],
        ["Pre- / post-hospitalisation"]
        + [f"{p[n].pre_post_days[0]} days / {p[n].pre_post_days[1]} days" for n in PLAN_NAMES]
        + ["C.2, C.3"],
        ["Day care treatment", "Up to Sum Insured", "Up to Sum Insured", "Up to Sum Insured", "C.4"],
        plan_row("Domiciliary hospitalisation", "domiciliary") + ["C.5"],
        plan_row("AYUSH treatment", "ayush") + ["C.6"],
        ["Organ donor expenses", "Up to Sum Insured", "Up to Sum Insured", "Up to Sum Insured", "C.7"],
        plan_row("Road ambulance", "road_ambulance") + ["C.8"],
        plan_row("Air ambulance", "air_ambulance") + ["C.9"],
        plan_row("Modern treatments", "modern_treatment") + ["C.10"],
        plan_row("Cataract (per eye)", "cataract") + ["C.1.6"],
        plan_row("Maternity", "maternity") + ["C.11"],
        plan_row("Cumulative bonus", "cumulative_bonus") + ["C.13"],
        plan_row("Restoration", "restoration") + ["C.14"],
        plan_row("Preventive health check-up", "health_checkup") + ["C.15"],
        plan_row("Co-payment for senior entry age", "senior_copay") + ["C.17.1"],
        plan_row("Zone-based co-payment", "zone_copay") + ["C.17.2"],
        ["Initial waiting period", "30 days", "30 days", "30 days", "D.1.3"],
        ["Specified diseases waiting period", "24 months", "24 months", "24 months", "D.1.2"],
        ["Pre-existing diseases waiting period"]
        + [f"{p[n].pre_existing_months} months" for n in PLAN_NAMES]
        + ["D.1.1"],
    ]
    return rows


def section_a() -> Section:
    return Section(
        "A",
        "Preamble",
        "",
        [
            Clause(
                "A.1",
                "The contract",
                [
                    f"This Policy is issued by {INSURER} (the Company) to the Policyholder named in the Policy "
                    "Schedule. The proposal form, the declarations made in it, the Policy Schedule, this wording and "
                    "any endorsement together form a single contract, and must be read together.",
                    "In consideration of the premium paid, and subject to the terms, conditions, exclusions and "
                    "limits of this Policy, the Company will pay or reimburse the Medical Expenses incurred by an "
                    "Insured Person for an illness or injury that occurs during the Policy Period, up to the Sum "
                    "Insured and the limits of the plan stated in the Policy Schedule.",
                ],
            ),
            Clause(
                "A.2",
                "How to read this wording",
                [
                    "Words that start with a capital letter have the meaning given in Section B. Headings are for "
                    "convenience only. Each provision is identified by its clause number (for example C.1.4 or "
                    "Excl12), and claim decisions quote these numbers.",
                    "Where a benefit is described as 'up to Sum Insured', it is payable up to the Sum Insured "
                    "available at the time of the claim, after all earlier claims in the same Policy Year. Every "
                    "limit is per Insured Person and per Policy Year unless stated otherwise.",
                ],
            ),
            Clause(
                "A.3",
                "Order of application of limits",
                [
                    "An admissible claim is assessed in the following order: first, items that are not payable under "
                    "Section D or Annexure II are removed; second, charges are restricted to the Package Rate or "
                    "Reasonable and Customary Charges, and medicines and consumables to their maximum retail price; "
                    "third, the room and ICU eligibility in clause C.1 is applied, with Proportionate Deduction where "
                    "relevant; fourth, any sub-limit is applied; fifth, the Deductible and then the Co-payment are "
                    "applied; and finally the amount is restricted to the Sum Insured available.",
                ],
            ),
        ],
    )


def section_b() -> Section:
    std = [Clause(f"Def. {i}", t, [f'"{t}" means {d}']) for i, (t, d) in enumerate(STANDARD_DEFINITIONS, start=1)]
    n = len(std)
    spec = [Clause(f"Def. {i}", t, [f'"{t}" means {d}']) for i, (t, d) in enumerate(SPECIFIC_DEFINITIONS, start=n + 1)]
    return Section(
        "B",
        "Definitions",
        "The definitions in B.1 are the standard definitions applicable to all retail health insurance products. "
        "The definitions in B.2 are specific to this Policy. Words in the singular include the plural and the "
        "masculine includes every gender.",
        [Clause("B.1", "Standard definitions", [])] + std + [Clause("B.2", "Specific definitions", [])] + spec,
        two_column=True,
    )


def section_c() -> Section:
    p = PLANS
    c = [
        Clause(
            "C.1",
            "In-patient hospitalisation treatment",
            [
                "The Company will pay the Medical Expenses for Inpatient Care of an Insured Person who is "
                "hospitalised for more than 24 consecutive hours on the written advice of a Medical Practitioner for "
                "an illness contracted or an injury sustained during the Policy Period. The admission must be "
                "Medically Necessary Treatment.",
            ],
        ),
        Clause(
            "C.1.1",
            "Expenses covered",
            ["Subject to clauses C.1.2 to C.1.6, the following are covered:"],
            bullets=[
                "Room, boarding and nursing charges provided by the Hospital.",
                "ICU and intensive cardiac care unit charges.",
                "Fees of the surgeon, anaesthetist, Medical Practitioner, consultants and specialists.",
                "Anaesthesia, blood, oxygen, operation theatre charges, surgical appliances.",
                "Medicines and drugs consumed during the hospitalisation.",
                "Diagnostic procedures and investigations.",
                "Cost of prosthetic and other devices or equipment implanted internally during a surgical "
                "procedure, such as a pacemaker, stent or orthopaedic implant.",
                "Dialysis, chemotherapy and radiotherapy.",
            ],
        ),
        Clause(
            "C.1.2",
            "Room rent eligibility",
            [
                "Room charges are payable up to the eligibility of the plan opted, as follows:",
            ],
            table=[["Plan", "Room eligibility per day"]] + [[n, p[n].room_rent] for n in PLAN_NAMES],
            widths=(40, 126),
        ),
        Clause(
            "C.1.3",
            "ICU eligibility",
            [
                "ICU Charges are payable up to the eligibility of the plan opted. Proportionate Deduction under "
                "C.1.4 does not apply to ICU Charges.",
            ],
            table=[["Plan", "ICU eligibility per day"]] + [[n, p[n].icu] for n in PLAN_NAMES],
            widths=(40, 126),
        ),
        Clause(
            "C.1.4",
            "Proportionate deduction",
            [
                "If the Insured Person occupies a room whose charge per day exceeds the room eligibility in C.1.2, "
                "the Company will pay the Associated Medical Expenses in the same proportion as the eligible room "
                "charge bears to the actual room charge. The reduction applies only to Associated Medical Expenses. "
                "It does not apply to pharmacy, consumables, implants, medical devices or diagnostics, and it does "
                "not apply in a Hospital that does not have a room in the eligible category. An illustration is "
                "given in Annexure IV.",
                "Where the Hospital charges a different rate for a procedure according to the room category, the "
                "rate applicable to the eligible room category is used before any further deduction.",
            ],
        ),
        Clause(
            "C.1.5",
            "Network and package rates",
            [
                "In a Network Provider, the Company is liable only up to the Package Rate agreed for the procedure, "
                "or the Hospital's agreed tariff for items outside a package. Charges above the agreed rate are not "
                "payable and must not be collected from the Insured Person by the Network Provider.",
            ],
        ),
        Clause(
            "C.1.6",
            "Cataract",
            [
                "Expenses for cataract surgery are payable up to the following limit for each eye, per Policy Year, "
                "including the cost of the intra-ocular lens and all associated expenses:",
            ],
            table=[["Plan", "Limit per eye"]] + [[n, p[n].cataract] for n in PLAN_NAMES],
            widths=(40, 126),
        ),
        Clause(
            "C.2",
            "Pre-hospitalisation medical expenses",
            [
                "The Company will pay Pre-hospitalisation Medical Expenses for the number of days before admission "
                "shown below, provided the in-patient hospitalisation claim under C.1 is admissible. Expenses "
                f"incurred more than the stated days before admission are not payable. The periods are: Classic "
                f"{p['Classic'].pre_post_days[0]} days, Premier {p['Premier'].pre_post_days[0]} days and Elite "
                f"{p['Elite'].pre_post_days[0]} days.",
            ],
        ),
        Clause(
            "C.3",
            "Post-hospitalisation medical expenses",
            [
                "The Company will pay Post-hospitalisation Medical Expenses for the number of days after discharge "
                "shown below, provided the in-patient hospitalisation claim under C.1 is admissible. The periods are: "
                f"Classic {p['Classic'].pre_post_days[1]} days, Premier {p['Premier'].pre_post_days[1]} days and "
                f"Elite {p['Elite'].pre_post_days[1]} days. Claims for post-hospitalisation expenses must be "
                "submitted within 15 days of the end of the post-hospitalisation period.",
            ],
        ),
        Clause(
            "C.4",
            "Day care treatment",
            [
                "The Company will pay the Medical Expenses for Day Care Treatment in a Hospital or Day Care Centre "
                "for the procedures listed in Annexure I, up to Sum Insured. Pre- and post-hospitalisation expenses "
                "for day care procedures are payable under C.2 and C.3. Treatment taken in the out-patient "
                "department is not covered.",
            ],
        ),
        Clause(
            "C.5",
            "Domiciliary hospitalisation",
            [
                "The Company will pay the Medical Expenses for Domiciliary Hospitalisation for more than three "
                "consecutive days on the advice of a Medical Practitioner, up to the limit of the plan opted: "
                f"Classic {p['Classic'].domiciliary}; Premier {p['Premier'].domiciliary}; Elite "
                f"{p['Elite'].domiciliary}. Domiciliary Hospitalisation is not payable for asthma, bronchitis, "
                "chronic nephritis, diarrhoea and dysentery, diabetes, epilepsy, hypertension, influenza, cough and "
                "cold, psychiatric disorders, arthritis and gout, or pyrexia of unknown origin.",
            ],
        ),
        Clause(
            "C.6",
            "AYUSH treatment",
            [
                "The Company will pay the Medical Expenses for in-patient AYUSH Treatment in an AYUSH Hospital, up "
                f"to the limit of the plan opted: Classic {p['Classic'].ayush}; Premier {p['Premier'].ayush}; "
                f"Elite {p['Elite'].ayush}. Treatment in a health resort, spa or nature cure centre is not covered.",
            ],
        ),
        Clause(
            "C.7",
            "Organ donor expenses",
            [
                "The Company will pay the in-patient Medical Expenses incurred for harvesting the organ from a donor "
                "for an organ transplant on the Insured Person, up to Sum Insured, provided the transplant complies "
                "with the Transplantation of Human Organs Act, 1994 and the claim for the Insured Person's "
                "transplant is admissible. Pre- and post-hospitalisation expenses of the donor, costs of acquiring "
                "the organ and screening of donors are not covered.",
            ],
        ),
        Clause(
            "C.8",
            "Road ambulance",
            [
                "The Company will pay the reasonable expenses of a registered road ambulance for transferring the "
                "Insured Person to a Hospital in an emergency, or from one Hospital to another for better medical "
                "care on the advice of a Medical Practitioner, up to the limit of the plan opted: Classic "
                f"{p['Classic'].road_ambulance}; Premier {p['Premier'].road_ambulance}; Elite "
                f"{p['Elite'].road_ambulance}.",
            ],
        ),
        Clause(
            "C.9",
            "Air ambulance (Elite plan only)",
            [
                "Under the Elite plan, the Company will pay air ambulance expenses "
                f"{PLANS['Elite'].air_ambulance.lower()}, for transfer to the nearest Hospital able to provide the "
                "required treatment, when the Insured Person needs Emergency Care that cannot be provided at the "
                "place of the event and road transfer is not possible. Return transport is not covered. This "
                "benefit is not available under the Classic and Premier plans.",
            ],
        ),
        Clause(
            "C.10",
            "Modern treatment methods and advancement in technologies",
            [
                "The following procedures and treatments are covered when taken as in-patient or Day Care Treatment, "
                "up to the limit shown for the plan opted, which applies to each treatment per Policy Year:",
            ],
            table=[["S. No.", "Treatment", "Classic / Premier", "Elite"]]
            + [[str(i), t, "50% of Sum Insured", "Up to Sum Insured"] for i, t in enumerate(MODERN_TREATMENTS, 1)],
            widths=(14, 92, 32, 28),
        ),
        Clause(
            "C.11",
            "Maternity (Premier and Elite plans)",
            [
                "Under the Premier and Elite plans, the Company will pay Maternity Expenses for the delivery of a "
                "child, or the lawful medical termination of pregnancy, after a waiting period of 24 months of "
                "continuous coverage of the Insured Person under this Policy. The benefit is limited to two "
                "deliveries or terminations during the lifetime of the Insured Person. The limits are:",
            ],
            table=[
                ["Plan", "Normal delivery", "Caesarean section"],
                ["Classic", "Not covered", "Not covered"],
                ["Premier", "Rs. 50,000", "Rs. 75,000"],
                ["Elite", "Rs. 1,00,000", "Rs. 1,50,000"],
            ],
            widths=(40, 63, 63),
        ),
        Clause(
            "C.11.1",
            "Pre- and post-natal expenses",
            [
                "Pre-natal and post-natal expenses are payable only when they are incurred during the hospitalisation "
                "for delivery. Ectopic pregnancy is covered under C.1 and is not subject to the maternity limit or "
                "waiting period.",
            ],
        ),
        Clause(
            "C.12",
            "Newborn baby cover",
            [
                "Where a maternity claim under C.11 is admissible, the Medical Expenses of the Newborn Baby, "
                "including vaccinations in the first 90 days, are covered within the maternity limit. The Newborn "
                "Baby can be added to the Policy from birth on payment of the additional premium within 90 days.",
            ],
        ),
        Clause(
            "C.13",
            "Cumulative bonus",
            [
                "For every claim-free Policy Year, the Sum Insured on renewal is increased by the Cumulative Bonus "
                f"of the plan opted: Classic {p['Classic'].cumulative_bonus}; Premier "
                f"{p['Premier'].cumulative_bonus}; Elite {p['Elite'].cumulative_bonus}. If a claim is made in a "
                "Policy Year, the Cumulative Bonus is reduced on renewal at the same rate at which it accrued, but "
                "never below zero and never below the Base Sum Insured. Cumulative Bonus is not available if the "
                "Policy is not renewed within the Grace Period.",
            ],
        ),
        Clause(
            "C.14",
            "Restoration of Sum Insured (Premier and Elite plans)",
            [
                "If the Sum Insured (including Cumulative Bonus) is exhausted or partly used during a Policy Year, "
                "the Company will reinstate 100% of the Base Sum Insured. Under the Premier plan the restoration is "
                "available once per Policy Year; under the Elite plan it is available any number of times. The "
                "Restoration Amount is not available for a claim for the same illness or injury for which a claim "
                "was paid in the same Policy Year, cannot be used for the first claim, and unused amounts do not "
                "carry forward.",
            ],
        ),
        Clause(
            "C.15",
            "Preventive health check-up",
            [
                "The Insured Person may undergo a health check-up at a Network Provider, irrespective of claims, as "
                f"follows: Classic {p['Classic'].health_checkup}; Premier {p['Premier'].health_checkup}; Elite "
                f"{p['Elite'].health_checkup}. Payment under this clause does not affect the Cumulative Bonus.",
            ],
        ),
        Clause(
            "C.16",
            "Second medical opinion",
            [
                "The Insured Person may obtain a second medical opinion from the Company's panel of Medical "
                "Practitioners for a major illness diagnosed during the Policy Period. The opinion is advisory, is "
                "provided without additional cost, and does not affect the Sum Insured.",
            ],
        ),
        Clause(
            "C.17",
            "Cost sharing",
            [
                "The following cost-sharing provisions apply to every admissible claim after the limits in "
                "C.1 to C.16 have been applied, in the order set out in A.3.",
            ],
        ),
        Clause(
            "C.17.1",
            "Co-payment for senior entry age",
            [
                "Under the Classic and Premier plans, where the Insured Person was aged 61 years or more on the date "
                "of first enrolment, the Insured Person bears a Co-payment of 20% of every admissible claim. The "
                "Co-payment does not apply under the Elite plan, and is not waived by renewal.",
            ],
        ),
        Clause(
            "C.17.2",
            "Zone-based co-payment",
            [
                "Under the Classic and Premier plans, an Insured Person who pays a Zone B premium and takes "
                "treatment in a Zone A city bears a Co-payment of 15% of the admissible claim, except for treatment "
                "taken as Emergency Care or following an Accident. Where C.17.1 also applies, the two Co-payments "
                "are applied one after the other.",
            ],
        ),
        Clause(
            "C.17.3",
            "Voluntary deductible",
            [
                "The Policyholder may opt for a voluntary Deductible of Rs. 25,000, Rs. 50,000 or Rs. 1,00,000 per "
                "Policy Year, for a premium discount. The Deductible is applied to the aggregate of admissible claims "
                "in the Policy Year before any Co-payment, and is shown in the Policy Schedule.",
            ],
        ),
    ]
    return Section(
        "C",
        "Benefits covered under the Policy",
        "The benefits below are available under the plan stated in the Policy Schedule, subject to the Sum Insured, "
        "the limits in this Section, the waiting periods and exclusions in Section D and the conditions in Section "
        "E. A summary of all plan limits is given in the Schedule of Benefits.",
        c,
    )


STANDARD_EXCLUSIONS: list[tuple[str, str, str]] = [
    (
        "Excl04",
        "Investigation and evaluation",
        "Expenses related to any admission primarily for diagnostics and evaluation purposes, and any diagnostic "
        "expenses that are not related or incidental to the current diagnosis and treatment.",
    ),
    (
        "Excl05",
        "Rest cure, rehabilitation and respite care",
        "Expenses related to any admission primarily for enforced bed rest and not for receiving treatment, "
        "including custodial care for personal needs such as bathing, dressing, moving around or eating, and any "
        "services for people who are terminally ill to address physical, social, emotional and spiritual needs.",
    ),
    (
        "Excl06",
        "Obesity and weight control",
        "Expenses related to the surgical treatment of obesity, unless all of the following are met: the surgery "
        "is advised by a Medical Practitioner following evidence-based clinical protocols; the Insured Person is "
        "18 years or older; and the body mass index is 40 or more, or 35 or more with a serious co-morbidity such "
        "as obesity-related cardiomyopathy, coronary heart disease, severe sleep apnoea or uncontrolled type 2 "
        "diabetes, after failure of less invasive methods of weight loss.",
    ),
    (
        "Excl07",
        "Change-of-gender treatments",
        "Expenses related to any treatment, including surgical management, to change the characteristics of the "
        "body to those of the opposite sex.",
    ),
    (
        "Excl08",
        "Cosmetic or plastic surgery",
        "Expenses for cosmetic or plastic surgery or any treatment to change appearance, unless it is for "
        "reconstruction following an Accident, burns or cancer, or is part of Medically Necessary Treatment to "
        "remove a direct and immediate health risk, certified by the attending Medical Practitioner.",
    ),
    (
        "Excl09",
        "Hazardous or adventure sports",
        "Expenses related to any treatment necessitated by participation as a professional in hazardous or "
        "adventure sports, including para-jumping, rock climbing, mountaineering, rafting, motor racing, horse "
        "racing, scuba diving, hand gliding, sky diving and deep-sea diving.",
    ),
    (
        "Excl10",
        "Breach of law",
        "Expenses for treatment directly arising from or as a consequence of the Insured Person committing or "
        "attempting to commit a breach of law with criminal intent.",
    ),
    (
        "Excl11",
        "Excluded providers",
        "Expenses incurred at a Hospital or by a Medical Practitioner specifically excluded by the Company and "
        "disclosed on its website or notified to the Policyholder. In a life-threatening situation or following an "
        "Accident, expenses up to the stage of stabilisation are payable, but not the complete claim.",
    ),
    (
        "Excl12",
        "Alcoholism and drug abuse",
        "Treatment for alcoholism, drug or substance abuse or any addictive condition, and the consequences of these.",
    ),
    (
        "Excl13",
        "Non-hospital stays",
        "Treatments received in health hydros, nature cure clinics, spas or similar establishments, or private beds "
        "registered as a nursing home attached to such establishments, or where admission is arranged wholly or "
        "partly for domestic reasons.",
    ),
    (
        "Excl14",
        "Supplements",
        "Dietary supplements and substances that can be purchased without a prescription, including vitamins, "
        "minerals and organic substances, unless prescribed by a Medical Practitioner as part of hospitalisation or "
        "day care treatment.",
    ),
    (
        "Excl15",
        "Refractive error",
        "Expenses related to the treatment for correction of eyesight due to refractive error of less than 7.5 "
        "dioptres.",
    ),
    (
        "Excl16",
        "Unproven treatments",
        "Expenses related to any unproven treatment, services and supplies for or in connection with any "
        "treatment. Unproven treatments are treatments, procedures or supplies that lack significant medical "
        "documentation to support their effectiveness.",
    ),
    (
        "Excl17",
        "Sterility and infertility",
        "Expenses related to sterility and infertility, including any type of contraception or sterilisation, "
        "assisted reproduction services such as artificial insemination and advanced reproductive technologies "
        "(IVF, ZIFT, GIFT, ICSI), gestational surrogacy and reversal of sterilisation.",
    ),
    (
        "Excl18",
        "Maternity",
        "Medical treatment expenses traceable to childbirth, including complicated deliveries and caesarean "
        "sections, and expenses towards miscarriage or medical termination of pregnancy, except ectopic pregnancy "
        "and except to the extent covered under C.11 for the Premier and Elite plans.",
    ),
]

SPECIFIC_EXCLUSIONS: list[tuple[str, str]] = [
    (
        "War and nuclear risks",
        "Treatment directly or indirectly caused by war, invasion, act of foreign enemy, hostilities, civil war, "
        "rebellion or revolution, or by nuclear, chemical or biological weapons, or radioactive contamination.",
    ),
    (
        "External congenital anomalies",
        "Treatment of External Congenital Anomalies and of any complication arising from them.",
    ),
    (
        "Dental treatment",
        "Dental Treatment of any kind, including dentures and implants, unless required because of an Accident "
        "and requiring hospitalisation.",
    ),
    (
        "Spectacles, hearing aids and walking aids",
        "Cost of spectacles, contact lenses, hearing aids, crutches, wheelchairs, walkers and other external "
        "durable medical equipment, whether or not prescribed.",
    ),
    (
        "Out-patient treatment",
        "OPD Treatment, except as specifically provided under C.15 and C.16.",
    ),
    (
        "Self-inflicted injury",
        "Intentional self-injury or attempted suicide, except where the Insured Person is diagnosed with a mental "
        "illness and the treatment is Medically Necessary Treatment.",
    ),
    (
        "Treatment outside India",
        "Any treatment taken outside India.",
    ),
    (
        "Non-allopathic treatment",
        "Any non-allopathic treatment other than AYUSH Treatment covered under C.6.",
    ),
    (
        "Items listed in Annexure II",
        "Items of expense that are not payable, or are subsumed into room, procedure or treatment charges, as "
        "listed in Annexure II. Where such items are billed separately, the amount billed is deducted.",
    ),
    (
        "Charges by family members",
        "Charges for treatment or services provided by the Insured Person's spouse, parents, children or siblings.",
    ),
    (
        "Service and registration charges",
        "Registration, admission, service, surcharge or documentation charges levied by the Hospital, where these "
        "are not part of an agreed Package Rate.",
    ),
]


def section_d() -> Section:
    p = PLANS
    clauses = [
        Clause("D.1", "Waiting periods", ["The following waiting periods apply to each Insured Person."]),
        Clause(
            "D.1.1",
            "Pre-existing diseases (Code - Excl01)",
            [
                "Expenses related to the treatment of a Pre-Existing Disease and its direct complications are "
                "excluded until the expiry of the following months of continuous coverage after the date of "
                f"inception of the first policy with the Company: Classic {p['Classic'].pre_existing_months} "
                f"months, Premier {p['Premier'].pre_existing_months} months and Elite "
                f"{p['Elite'].pre_existing_months} months.",
                "In case of an enhancement of the Sum Insured, the exclusion applies afresh to the extent of the "
                "increase. If the Insured Person is continuously covered without any break as defined under the "
                "portability norms of the IRDAI, the waiting period is reduced to the extent of prior coverage. "
                "Coverage after the waiting period is subject to the Pre-Existing Disease having been declared in "
                "the proposal and accepted by the Company.",
            ],
        ),
        Clause(
            "D.1.2",
            "Specified diseases and procedures (Code - Excl02)",
            [
                "Expenses related to the treatment of the illnesses and procedures listed below are excluded until "
                "the expiry of 24 months of continuous coverage after the date of inception of the first policy with "
                "the Company. This exclusion does not apply to claims arising from an Accident or from cancer. If a "
                "listed condition is also a Pre-Existing Disease, the longer of the two waiting periods applies.",
            ],
            table=[["S. No.", "System", "Illnesses and procedures"]]
            + [[str(i), s, d] for i, (s, d) in enumerate(SPECIFIED_DISEASES, 1)],
            widths=(14, 36, 116),
        ),
        Clause(
            "D.1.3",
            "First 30 days waiting period (Code - Excl03)",
            [
                "Expenses related to the treatment of any illness within 30 days from the first Policy commencement "
                "date are excluded, except claims arising due to an Accident. The exclusion does not apply on "
                "renewal without a break or to the extent of continuous prior coverage.",
            ],
        ),
        Clause(
            "D.1.4",
            "Bariatric surgery",
            [
                "Bariatric surgery, where admissible under Excl06, is covered only after 36 months of continuous "
                "coverage.",
            ],
        ),
        Clause(
            "D.2",
            "Standard permanent exclusions",
            [
                "The Company will not be liable to make any payment for any claim directly or indirectly caused by, "
                "based on, arising out of or attributable to any of the following:",
            ],
        ),
    ]
    for i, (code, title, text) in enumerate(STANDARD_EXCLUSIONS, start=1):
        clauses.append(Clause(f"D.2.{i}", f"{title} (Code - {code})", [text]))
    clauses.append(Clause("D.3", "Specific exclusions", ["In addition, the following are excluded under this Policy:"]))
    for i, (title, text) in enumerate(SPECIFIC_EXCLUSIONS, start=1):
        clauses.append(Clause(f"D.3.{i}", title, [text]))
    return Section(
        "D",
        "Waiting periods and exclusions",
        "The waiting periods and exclusions in this Section apply to every plan, except where a plan is named.",
        clauses,
    )


def section_e() -> Section:
    gtc: list[tuple[str, list[str]]] = [
        (
            "Disclosure of information",
            [
                "The Policy shall be void and all premium paid shall be forfeited to the Company in the event of "
                "misrepresentation, misdescription or non-disclosure of any material fact by the Policyholder. A "
                "material fact is any information that has a bearing on the acceptance of the risk.",
            ],
        ),
        (
            "Condition precedent to admission of liability",
            [
                "The terms and conditions of the Policy must be fulfilled by the Insured Person for the Company to "
                "make any payment for a claim arising under the Policy.",
            ],
        ),
        (
            "Claim settlement",
            [
                "The Company will settle or reject a claim within 15 days of the receipt of the last necessary "
                "document. In case of delay in payment, the Company will pay interest from the date of receipt of "
                "the last necessary document to the date of payment, at 2% above the bank rate. Where the "
                "circumstances of a claim warrant an investigation, the Company will complete the investigation and "
                "settle or reject the claim within 30 days of the last necessary document, and pay interest at 2% "
                "above the bank rate for any delay beyond that period.",
            ],
        ),
        (
            "Complete discharge",
            [
                "Any payment to the Policyholder, Insured Person, nominee or legal representative, or to the "
                "Hospital, shall be a valid discharge towards the payment of the claim to that extent.",
            ],
        ),
        (
            "Multiple policies",
            [
                "If two or more policies are taken by an Insured Person from one or more insurers to cover the same "
                "risk on indemnity basis, the Insured Person may choose the policy under which the claim is to be "
                "settled. Where the amount to be claimed exceeds the Sum Insured under a single policy, the Insured "
                "Person may choose the insurers by whom the balance is to be settled. The Company will not apply a "
                "contribution clause.",
            ],
        ),
        (
            "Fraud",
            [
                "If any claim made by the Insured Person is in any respect fraudulent, or if any false statement or "
                "declaration is made or used in support of it, or if any fraudulent means or devices are used by the "
                "Insured Person or anyone acting on their behalf to obtain any benefit, all benefits under this "
                "Policy and the premium paid shall be forfeited. Any amount already paid against claims found "
                "fraudulent shall be repaid by the recipients, who shall be jointly and severally liable.",
                "Fraud means any of the following acts committed by the Insured Person or by their agent or the "
                "Hospital in order to obtain a benefit: the suggestion, as a fact, of that which is not true and "
                "which the person does not believe to be true; the active concealment of a fact; any other act "
                "fitted to deceive; and any act or omission that the law specially declares to be fraudulent.",
                "The Company shall not repudiate a claim or forfeit the Policy benefits on the ground of fraud if "
                "the Insured Person proves that the misstatement was true to the best of their knowledge and there "
                "was no deliberate intention to suppress the fact.",
            ],
        ),
        (
            "Cancellation",
            [
                "The Policyholder may cancel this Policy at any time by giving 7 days' notice in writing. Where no "
                "claim has been made, the Company will refund premium for the unexpired period as below. Where a "
                "claim has been made, no refund is due.",
                "The Company may cancel the Policy only on the grounds of established fraud, by giving 7 days' "
                "notice in writing, and no refund of premium will be made.",
            ],
        ),
        (
            "Migration",
            [
                "The Insured Person may migrate to another health insurance policy of the Company at the time of "
                "renewal, with all accrued continuity benefits such as waiver of waiting periods, subject to the "
                "IRDAI guidelines on migration.",
            ],
        ),
        (
            "Portability",
            [
                "The Insured Person may port the Policy to another insurer by applying at least 15 days and not more "
                "than 60 days before the renewal date. If the Insured Person was continuously covered without any "
                "lapse under any health insurance policy, they are entitled to the accrued continuity benefits in "
                "waiting periods, as per the IRDAI guidelines on portability.",
            ],
        ),
        (
            "Renewal of policy",
            [
                "The Policy shall ordinarily be renewable except on grounds of fraud, misrepresentation by the "
                "Insured Person, or moral hazard. The Company will not refuse renewal on the ground that the Insured "
                "Person made a claim. A Grace Period of 30 days is allowed for renewal (15 days where premium is paid "
                "monthly), and coverage is not available during the period in which no premium is received.",
            ],
        ),
        (
            "Premium payment in instalments",
            [
                "The Policyholder may pay the premium in monthly, quarterly or half-yearly instalments, as shown in "
                "the Policy Schedule. If an instalment is not paid within the Grace Period, the Policy is cancelled. "
                "In case of a claim, the remaining instalments for the Policy Year are deducted from the claim "
                "amount or must be paid before the claim is settled.",
            ],
        ),
        (
            "Moratorium period",
            [
                "After completion of 60 continuous months of coverage, including portability and migration, no "
                "policy or claim shall be contestable by the Company on grounds of non-disclosure or "
                "misrepresentation, except on grounds of established fraud. The moratorium applies to the Sum "
                "Insured of the first policy, and to any enhanced Sum Insured from the date of the enhancement.",
            ],
        ),
        (
            "Possibility of revision of terms",
            [
                "The Company may revise or modify the terms, premium or benefits of the Policy with the prior "
                "approval of the IRDAI, and will notify the Policyholder at least 90 days before the revision takes "
                "effect.",
            ],
        ),
        (
            "Sum insured and enhancement",
            [
                "The Base Sum Insured options for each plan are given in the Schedule of Benefits. The Sum Insured "
                "may be enhanced only at renewal, subject to underwriting. Waiting periods under D.1 apply afresh "
                "to the enhanced portion.",
            ],
        ),
        (
            "Free look period",
            [
                "The Policyholder has a period of 30 days from the date of receipt of the Policy document to review "
                "the terms of a new Policy. If the Policyholder is not satisfied, the Policy may be returned for "
                "cancellation stating the reasons, and the Company will refund the premium after deducting "
                "proportionate risk premium for the period of cover, stamp duty and the cost of any medical "
                "examination. The free look period does not apply to renewals.",
            ],
        ),
        (
            "Nomination",
            [
                "The Policyholder must nominate a person at the inception of the Policy to receive claim payments in "
                "the event of the death of the Policyholder. The nomination may be changed by a written "
                "endorsement.",
            ],
        ),
        (
            "Withdrawal of product",
            [
                "If this product is withdrawn, the Policyholder will be offered the option to migrate to a similar "
                "product of the Company with continuity benefits, with 90 days' notice before the renewal date.",
            ],
        ),
        (
            "Arbitration and jurisdiction",
            [
                "Disputes as to the quantum of a claim, where liability is admitted, may be referred to arbitration "
                "under the Arbitration and Conciliation Act, 1996. The Policy is governed by the laws of India and "
                "the courts of India have exclusive jurisdiction.",
            ],
        ),
    ]
    clauses = [Clause("E.1", "Standard general terms and clauses", [])]
    for i, (title, paras) in enumerate(gtc, start=1):
        cl = Clause(f"E.1.{i}", title, paras)
        if title == "Cancellation":
            cl.table = [
                ["Period on risk", "Annual policy refund", "Two-year policy refund", "Three-year policy refund"],
                ["Up to 30 days", "75.0%", "87.5%", "91.5%"],
                ["31 to 90 days", "50.0%", "75.0%", "83.0%"],
                ["91 to 180 days", "25.0%", "62.5%", "75.0%"],
                ["181 to 365 days", "0.0%", "50.0%", "66.5%"],
                ["366 to 545 days", "-", "25.0%", "50.0%"],
                ["546 to 730 days", "-", "12.5%", "33.0%"],
                ["Beyond 730 days", "-", "-", "16.5%"],
            ]
            cl.widths = (40, 42, 42, 42)
        clauses.append(cl)
    clauses += [
        Clause("E.2", "Specific terms and clauses", []),
        Clause(
            "E.2.1",
            "Medical examination",
            [
                "The Company may require any Insured Person to be examined by a Medical Practitioner nominated by "
                "the Company, at the Company's cost, as often as it considers necessary while a claim is pending.",
            ],
        ),
        Clause(
            "E.2.2",
            "Change of plan",
            [
                "The plan may be changed only at renewal. Where the change is to a higher plan, the waiting "
                "periods under D.1 apply afresh to the additional benefits.",
            ],
        ),
        Clause(
            "E.2.3",
            "Territorial limit",
            ["All treatment must be taken in India, and all claims are payable in Indian rupees."],
        ),
        Clause(
            "E.2.4",
            "Hospital tariff",
            [
                "Where a Hospital charges different tariffs to insured and uninsured patients, the Company is liable "
                "only for the tariff applicable to an uninsured patient for the same room category.",
            ],
        ),
    ]
    return Section(
        "E",
        "General terms and clauses",
        "The terms and clauses in this Section apply to the Policy as a whole.",
        clauses,
    )


def section_f() -> Section:
    return Section(
        "F",
        "Claim procedure",
        "Claims may be made on a cashless basis at a Network Provider or by reimbursement. The Company may "
        "service claims through a TPA named in the Policy Schedule.",
        [
            Clause(
                "F.1",
                "Notification of claim",
                [
                    "Notice of a claim with the policy number, the Insured Person's name, the nature of the illness or "
                    "injury and the name and address of the Hospital must be given to the Company or TPA:",
                ],
                bullets=[
                    "at least 72 hours before a planned hospitalisation; and",
                    "within 24 hours of admission in an emergency hospitalisation, or before discharge, whichever is "
                    "earlier.",
                ],
            ),
            Clause(
                "F.2",
                "Cashless facility",
                [
                    "Cashless Facility is available only at Network Providers. The Insured Person must present the "
                    "health card and photo identity proof at the Hospital, which sends the pre-authorisation request "
                    "to the TPA. The TPA will decide on the request within one hour of receipt, and on the final "
                    "discharge authorisation within three hours of receipt of the discharge request from the "
                    "Hospital. Charges above the authorised amount, non-payable items and cost-sharing amounts are "
                    "settled by the Insured Person directly with the Hospital.",
                    "A denial of cashless authorisation is not a rejection of the claim. The Insured Person may take "
                    "treatment and submit a reimbursement claim under F.3.",
                ],
            ),
            Clause(
                "F.3",
                "Reimbursement claims",
                [
                    "For reimbursement, the documents listed in F.4 must be submitted within the following time "
                    "limits. Delay may be condoned on merit where the Insured Person shows that it was caused by "
                    "circumstances beyond their control.",
                ],
                table=[
                    ["Type of claim", "Time limit for submission"],
                    ["Hospitalisation, day care and pre-hospitalisation", "Within 30 days of discharge"],
                    ["Post-hospitalisation", "Within 15 days of completion of the post-hospitalisation period"],
                    ["Domiciliary hospitalisation", "Within 30 days of completion of the treatment"],
                    ["Health check-up", "Within 30 days of the check-up"],
                ],
                widths=(76, 90),
            ),
            Clause(
                "F.4",
                "Documents required",
                ["The claim must be supported by the following documents, as applicable:"],
                table=[["S. No.", "Document"]] + [[str(i), d] for i, d in enumerate(CLAIM_DOCUMENTS, 1)],
                widths=(14, 152),
            ),
            Clause(
                "F.5",
                "Claim payment",
                [
                    "Claims are paid in Indian rupees by electronic transfer to the bank account of the "
                    "Policyholder or the Network Provider. The Company's liability for any one claim is limited to "
                    "the Sum Insured available and the applicable limits, after the application of cost sharing "
                    "under C.17.",
                    "Where a claim is rejected or partly paid, the Company will communicate the reasons in writing, "
                    "quoting the clauses of this Policy relied on, and the right to seek a review under Section G.",
                ],
            ),
        ],
    )


def section_g() -> Section:
    return Section(
        "G",
        "Redressal of grievances",
        "",
        [
            Clause(
                "G.1",
                "Contacting the Company",
                [
                    f"For any grievance, the Insured Person may contact the Company: {CONTACT}. Complaints may also "
                    "be made at any branch office or through the Company's website. The Company will acknowledge a "
                    "grievance within three working days.",
                ],
            ),
            Clause(
                "G.2",
                "Grievance Redressal Officer",
                [
                    "If the response is not satisfactory, or if no response is received within 14 days, the Insured "
                    "Person may write to the Grievance Redressal Officer of the Company at the address in the Policy "
                    "Schedule. Senior citizens may write to the dedicated senior citizen desk.",
                ],
            ),
            Clause(
                "G.3",
                "Bima Bharosa and Insurance Ombudsman",
                [
                    "If the grievance remains unresolved, the Insured Person may register it on the IRDAI's Bima "
                    "Bharosa portal (bimabharosa.irdai.gov.in), or approach the Insurance Ombudsman under the "
                    "Insurance Ombudsman Rules, 2017, within one year of the Company's final reply. The addresses "
                    "of the Ombudsman offices and their jurisdictions are published by the Council for Insurance "
                    "Ombudsmen at www.cioins.co.in.",
                ],
            ),
        ],
    )


def sections() -> list[Section]:
    return [section_a(), section_b(), section_c(), section_d(), section_e(), section_f(), section_g()]


def illustration_rows() -> list[list[str]]:
    """Proportionate deduction under C.1.4 for a Classic Rs. 3 lakh policy (room eligibility Rs. 3,000)."""
    eligible, actual, days = 3000, 6000, 4
    ratio = eligible / actual
    rows = [["Item", "Billed (Rs.)", "Basis", "Payable (Rs.)"]]
    items = [
        ("Room rent (4 days at Rs. 6,000)", actual * days, "Restricted to eligibility", eligible * days),
        ("Nursing charges", 8000, "Associated, proportionate", 8000 * ratio),
        ("Surgeon and anaesthetist fees", 60000, "Associated, proportionate", 60000 * ratio),
        ("Operation theatre charges", 20000, "Associated, proportionate", 20000 * ratio),
        ("Investigations in the Hospital", 12000, "Associated, proportionate", 12000 * ratio),
        ("Pharmacy and consumables", 25000, "Not reduced", 25000),
        ("Implant (mesh)", 18000, "Not reduced", 18000),
    ]
    total_billed = total_paid = 0.0
    for name, billed, basis, paid in items:
        rows.append([name, inr(billed), basis, inr(paid)])
        total_billed += billed
        total_paid += paid
    rows.append(["Total", inr(total_billed), "", inr(total_paid)])
    return rows
