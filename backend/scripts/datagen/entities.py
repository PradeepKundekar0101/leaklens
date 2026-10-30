"""Providers, tariffs, agents, members and member policies."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from scripts.datagen.common import TEMPLATES, Product, Reference, add_months

# (city, CGHS-style tier, relative population weight)
CITIES: list[tuple[str, int, float]] = [
    ("Mumbai", 1, 10),
    ("Delhi", 1, 10),
    ("Bengaluru", 1, 9),
    ("Chennai", 1, 7),
    ("Hyderabad", 1, 7),
    ("Kolkata", 1, 6),
    ("Pune", 1, 6),
    ("Ahmedabad", 1, 5),
    ("Jaipur", 2, 4),
    ("Lucknow", 2, 4),
    ("Indore", 2, 3),
    ("Kochi", 2, 3),
    ("Nagpur", 2, 3),
    ("Coimbatore", 2, 3),
    ("Bhubaneswar", 2, 2),
    ("Hubballi", 3, 2),
    ("Kolhapur", 3, 2),
    ("Guntur", 3, 2),
    ("Bareilly", 3, 2),
    ("Ujjain", 3, 1),
]

GENERAL_RENT = {1: 3000, 2: 2200, 3: 1500}  # rupees per day, general ward, tier-1 city
ICU_RENT = {1: 7500, 2: 6000, 3: 4500}
IMPLANT_PRICE_FACTOR = 0.60  # clean implants are billed at 55-65% of MRP

HOSPITAL_PREFIX = [
    "Sanjeevani",
    "Aarogya",
    "Dhanvantari",
    "Shushruta",
    "Lifeline",
    "Sparsh",
    "Amrut",
    "Jeevan",
    "Navjeevan",
    "Suraksha",
    "Sahyadri",
    "Kaveri",
    "Ganga",
    "Narmada",
    "Shanti",
    "Sevadham",
    "Medicity",
    "Vardhan",
    "Prerana",
    "Vatsalya",
    "Anand",
    "Sai Krupa",
    "Matrusree",
    "Om Sai",
    "Shree Balaji",
    "Arunodaya",
    "Chirayu",
    "Ashwini",
    "Swasthya",
    "Niramaya",
    "Sushrut",
    "Charak",
    "Nirmal",
    "Samarpan",
    "Udaan",
    "Sankalp",
    "Asha",
    "Karuna",
    "Vishwas",
    "Pranav",
    "Jivika",
    "Sheetal",
    "Aastha",
    "Mangal",
    "Sparsh Care",
    "Pushpanjali",
    "Sunrise",
    "Nightingale",
    "Silverline",
    "Greenfield",
    "Riverside",
]
HOSPITAL_SUFFIX = {
    1: ["Multispeciality Hospital", "Institute of Medical Sciences", "Super Speciality Hospital", "Medical Centre"],
    2: ["Hospital", "Multispeciality Hospital", "Hospital and Research Centre", "Health City"],
    3: ["Nursing Home", "Hospital", "Clinic and Nursing Home", "Memorial Hospital"],
}

FIRST_M = [
    "Aarav",
    "Vivaan",
    "Aditya",
    "Arjun",
    "Rohan",
    "Rahul",
    "Amit",
    "Suresh",
    "Ramesh",
    "Rajesh",
    "Vikram",
    "Sanjay",
    "Anil",
    "Sunil",
    "Manoj",
    "Prakash",
    "Ganesh",
    "Mahesh",
    "Karthik",
    "Siddharth",
    "Nikhil",
    "Pranav",
    "Harish",
    "Venkatesh",
    "Srinivas",
    "Mohammed",
    "Imran",
    "Faisal",
    "Joseph",
    "Thomas",
    "Gurpreet",
    "Harpreet",
    "Abhishek",
    "Deepak",
    "Naveen",
    "Ashok",
    "Kiran",
    "Vinod",
    "Ravi",
    "Sachin",
    "Yash",
    "Kabir",
    "Ishaan",
    "Dev",
    "Tarun",
]
FIRST_F = [
    "Ananya",
    "Diya",
    "Priya",
    "Pooja",
    "Sneha",
    "Kavya",
    "Lakshmi",
    "Meera",
    "Anjali",
    "Neha",
    "Divya",
    "Swati",
    "Sunita",
    "Geeta",
    "Rekha",
    "Kavita",
    "Asha",
    "Usha",
    "Shalini",
    "Deepa",
    "Radha",
    "Sangeeta",
    "Nisha",
    "Fatima",
    "Ayesha",
    "Mary",
    "Grace",
    "Simran",
    "Harleen",
    "Aishwarya",
    "Bhavna",
    "Jyoti",
    "Madhuri",
    "Nandini",
    "Rupali",
    "Shreya",
    "Tanvi",
    "Varsha",
    "Ishita",
    "Riya",
    "Sarita",
    "Padma",
    "Revathi",
    "Gayatri",
    "Archana",
]
SURNAMES = [
    "Sharma",
    "Verma",
    "Gupta",
    "Iyer",
    "Iyengar",
    "Nair",
    "Menon",
    "Pillai",
    "Reddy",
    "Rao",
    "Naidu",
    "Patel",
    "Shah",
    "Desai",
    "Mehta",
    "Joshi",
    "Kulkarni",
    "Deshpande",
    "Patil",
    "Jadhav",
    "Pawar",
    "Singh",
    "Yadav",
    "Chauhan",
    "Rathore",
    "Mishra",
    "Tiwari",
    "Pandey",
    "Dubey",
    "Srivastava",
    "Banerjee",
    "Chatterjee",
    "Mukherjee",
    "Das",
    "Bose",
    "Ghosh",
    "Sen",
    "Khan",
    "Qureshi",
    "Sheikh",
    "Fernandes",
    "D'Souza",
    "Thomas",
    "Kurian",
    "Gill",
    "Sandhu",
    "Bhatia",
    "Malhotra",
    "Kapoor",
    "Agarwal",
    "Bansal",
    "Jain",
    "Hegde",
    "Shetty",
    "Gowda",
    "Murthy",
    "Krishnan",
    "Subramanian",
    "Rajan",
    "Chaudhary",
]
CHANNELS = (["agency"] * 16) + (["broker"] * 8) + (["bancassurance"] * 7) + (["direct"] * 5) + (["online"] * 4)

# Declared (pre-existing) conditions: ICD-10 code -> relative weight. Some coincide with procedure diagnoses,
# which is what makes the 36-month pre-existing-disease waiting period bite.
CONDITIONS: dict[str, float] = {
    "E11": 10,
    "I10": 12,
    "E78.5": 6,
    "J45.9": 4,
    "E03.9": 4,
    "I25.1": 3,
    "K80.2": 1.5,
    "M17.1": 2.5,
    "N20.0": 1.5,
    "H25.9": 2,
    "N40": 1.5,
    "J44.1": 1.5,
    "D25.9": 1,
}

ADMISSION_START = date(2026, 1, 1)
NEW_POLICY_START = date(2026, 1, 1)
NEW_POLICY_END = date(2026, 9, 15)
OLD_POLICY_START = date(2021, 1, 1)
OLD_POLICY_END = date(2025, 12, 31)
COVER_UNTIL = date(2026, 11, 1)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def make_providers(rng: np.random.Generator, n: int = 50) -> pd.DataFrame:
    names = [c[0] for c in CITIES]
    weights = np.array([c[2] for c in CITIES], dtype=float)
    # every city gets at least one hospital; the rest follow population weight
    extra = rng.choice(len(CITIES), size=n - len(CITIES), p=weights / weights.sum())
    city_idx = np.sort(np.concatenate([np.arange(len(CITIES)), extra]))
    city_tier = np.array([CITIES[i][1] for i in city_idx])
    probs = {1: [0.5, 0.35, 0.15], 2: [0.3, 0.45, 0.25], 3: [0.1, 0.4, 0.5]}
    hosp_tier = np.array([rng.choice([1, 2, 3], p=probs[t]) for t in city_tier])
    nabh_p = np.select([hosp_tier == 1, hosp_tier == 2], [0.95, 0.7], 0.35)
    nabh = rng.random(n) < nabh_p
    beds = np.select(
        [hosp_tier == 1, hosp_tier == 2],
        [rng.integers(200, 701, n), rng.integers(80, 251, n)],
        rng.integers(25, 91, n),
    )
    network = np.zeros(n, dtype=bool)
    network[rng.choice(n, size=35, replace=False)] = True
    joined = [date(2012, 1, 1) + timedelta(days=int(d)) for d in rng.integers(0, 365 * 13, n)]
    prefixes = rng.permutation(HOSPITAL_PREFIX)[:n]
    hosp_names = [f"{prefixes[i]} {HOSPITAL_SUFFIX[int(hosp_tier[i])][int(rng.integers(0, 4))]}" for i in range(n)]
    return pd.DataFrame(
        {
            "id": [f"H{i + 1:03d}" for i in range(n)],
            "name": hosp_names,
            "city": [names[i] for i in city_idx],
            "city_tier": city_tier,
            "hospital_tier": hosp_tier,
            "nabh": nabh,
            "beds": beds,
            "network": network,
            "joined_at": joined,
        }
    )


def cost_factor(ref: Reference, city_tier, hosp_tier, nabh) -> np.ndarray:
    m = ref.multipliers
    ct = np.vectorize(lambda t: m[("city_tier", str(int(t)))])(city_tier)
    ht = np.vectorize(lambda t: m[("hospital_tier", str(int(t)))])(hosp_tier)
    nb = np.vectorize(lambda b: m[("nabh", "true" if b else "false")])(nabh)
    return ct * ht * nb


def make_tariffs(rng: np.random.Generator, ref: Reference, providers: pd.DataFrame) -> pd.DataFrame:
    """Package rate for procedure charges (OT + surgeon) per network provider x procedure."""
    net = providers[providers.network].reset_index(drop=True)
    procs = ref.procedures
    item_mrp = dict(zip(ref.items.item_code, ref.items.mrp_paise, strict=True))
    rows = []
    for p in net.itertuples():
        f = float(cost_factor(ref, [p.city_tier], [p.hospital_tier], [p.nabh])[0])
        city_f = ref.multipliers[("city_tier", str(p.city_tier))]
        for pr in procs.itertuples():
            total = pr.base_rate_paise / 100 * f
            icu_days = pr.icu_days_typical
            ward = max(1, pr.typical_los - icu_days)
            room = GENERAL_RENT[p.hospital_tier] * city_f * ward + ICU_RENT[p.hospital_tier] * city_f * icu_days
            implant = item_mrp[pr.implant_item] / 100 * IMPLANT_PRICE_FACTOR if pr.implant_item else 0.0
            rest = max(total - room - total * pr.typical_pharmacy_share - implant, 0.3 * total)
            w = TEMPLATES[pr.template]
            proc_charges = rest * (w[1] + w[2])
            package = proc_charges * rng.uniform(1.55, 1.80)
            rows.append((p.id, pr.code, int(round(package / 500.0)) * 500 * 100))
    return pd.DataFrame(rows, columns=["provider_id", "procedure_code", "package_paise"])


def make_agents(rng: np.random.Generator, n: int = 40) -> pd.DataFrame:
    names = []
    for _ in range(n):
        first = FIRST_M if rng.random() < 0.6 else FIRST_F
        names.append(f"{first[int(rng.integers(len(first)))]} {SURNAMES[int(rng.integers(len(SURNAMES)))]}")
    return pd.DataFrame(
        {
            "id": [f"A{i + 1:03d}" for i in range(n)],
            "name": names,
            "channel": [CHANNELS[int(i)] for i in rng.integers(0, len(CHANNELS), n)],
        }
    )


def _demand_ages(rng: np.random.Generator, ref: Reference, n: int) -> np.ndarray:
    procs = ref.procedures
    p = procs.frequency.to_numpy(float)
    idx = rng.choice(len(procs), size=n, p=p / p.sum())
    mean = np.array([a["mean"] for a in procs.age])[idx]
    sd = np.array([a["sd"] for a in procs.age])[idx]
    return np.clip(rng.normal(mean, sd), 0, 90)


def make_members(rng: np.random.Generator, ref: Reference, providers: pd.DataFrame, n: int) -> pd.DataFrame:
    # Ages: 60% follow the claim-demand mixture so every procedure finds age-matched members, 40% a population prior.
    n_demand = int(n * 0.6)
    pop = rng.choice(4, size=n - n_demand, p=[0.15, 0.50, 0.25, 0.10])
    lo = np.array([1, 18, 46, 66])[pop]
    hi = np.array([18, 46, 66, 90])[pop]
    ages = np.concatenate([_demand_ages(rng, ref, n_demand), rng.uniform(lo, hi)])
    ages = rng.permutation(np.round(ages).astype(int).clip(1, 90))
    gender = np.where(rng.random(n) < 0.5, "F", "M")
    # members live where the hospitals are, weighted by city population
    city_w = providers.groupby("city").size()
    city_names = city_w.index.to_numpy()
    pop_w = np.array([dict((c[0], c[2]) for c in CITIES)[c] for c in city_names]) * 0.5 + city_w.to_numpy() * 0.5
    city = city_names[rng.choice(len(city_names), size=n, p=pop_w / pop_w.sum())]

    cond_codes = list(CONDITIONS)
    cond_w = np.array(list(CONDITIONS.values()))
    cond_w = cond_w / cond_w.sum()
    p_any = np.clip(0.04 + 0.007 * np.maximum(0, ages - 30), 0, 0.5)
    n_cond = np.where(rng.random(n) < p_any, 1 + (rng.random(n) < 0.35), 0)
    declared = []
    for k in n_cond:
        if k == 0:
            declared.append("[]")
        else:
            codes = sorted(rng.choice(cond_codes, size=int(k), replace=False, p=cond_w).tolist())
            declared.append("[" + ", ".join(f'"{c}"' for c in codes) + "]")

    first = np.where(
        gender == "F",
        np.array(FIRST_F)[rng.integers(0, len(FIRST_F), n)],
        np.array(FIRST_M)[rng.integers(0, len(FIRST_M), n)],
    )
    last = np.array(SURNAMES)[rng.integers(0, len(SURNAMES), n)]
    acct = rng.integers(10**11, 10**12, n)
    phone = rng.integers(6 * 10**9, 10**10, n)
    ids = [f"M{i + 1:06d}" for i in range(n)]
    return pd.DataFrame(
        {
            "id": ids,
            "name": [f"{a} {b}" for a, b in zip(first, last, strict=True)],
            "age": ages,
            "gender": gender,
            "city": city,
            "declared_conditions": declared,
            "n_conditions": n_cond,
            "bank_account_hash": [_sha(f"acct:{a}") for a in acct],
            "phone_hash": [_sha(f"phone:+91{p}") for p in phone],
        }
    )


def make_policies(
    rng: np.random.Generator, members: pd.DataFrame, agents: pd.DataFrame, products: list[Product]
) -> pd.DataFrame:
    n = len(members)
    prod_idx = rng.choice(len(products), size=n, p=[0.45, 0.35, 0.20])
    si = np.empty(n, dtype=np.int64)
    for k, prod in enumerate(products):
        m = prod_idx == k
        opts = np.array([int(float(s)) * 100 for s in prod.sum_insured_options], dtype=np.int64)
        si[m] = opts[rng.choice(len(opts), size=int(m.sum()), p=[0.55, 0.45])]
    new = rng.random(n) < 0.10
    old_span = (OLD_POLICY_END - OLD_POLICY_START).days
    new_span = (NEW_POLICY_END - NEW_POLICY_START).days
    offs = np.where(new, rng.integers(0, new_span + 1, n), rng.integers(0, old_span + 1, n))
    starts = [
        (NEW_POLICY_START if nw else OLD_POLICY_START) + timedelta(days=int(o)) for nw, o in zip(new, offs, strict=True)
    ]
    ends = []
    for s in starts:
        years = 1
        while add_months(s, 12 * years) < COVER_UNTIL:
            years += 1
        ends.append(add_months(s, 12 * years) - timedelta(days=1))
    return pd.DataFrame(
        {
            "id": [f"MP{i + 1:06d}" for i in range(n)],
            "member_id": members.id.to_numpy(),
            "product_idx": prod_idx,
            "product_id": [products[k].id for k in prod_idx],
            "si_paise": si,
            "start_date": starts,
            "end_date": ends,
            "agent_id": agents.id.to_numpy()[rng.integers(0, len(agents), n)],
        }
    )
