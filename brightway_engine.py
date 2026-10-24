"""
Dynamic Brightway LCA Engine.

Converts arbitrary, user-defined Product models (multi-process, multi-stage,
inputs, outputs, and transportation) into Brightway databases and activities,
executes Life Cycle Inventory (LCI) and Impact Assessment (LCIA), and returns
rich contribution analytics.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import bw2calc as bc
import bw2data as bd
import numpy as np

from product_model import Exchange, Process, Product, Transportation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PROJECT = "brightway_learning_project"
BACKGROUND_DB_NAME = "lca_background_library"

# Standard CML 2016 GWP100 impact method
DEFAULT_LCIA_METHOD = (
    "CML v4.8 2016 no LT",
    "climate change no LT",
    "global warming potential (GWP100) no LT",
)

# Canonical UUIDs in biosphere3 for standard elementary emissions
BIOSPHERE3_FLOWS = {
    "co2_fossil": ("biosphere3", "349b29d1-3e58-4c66-98b9-9d1a076efd2e"),
    "methane_fossil": ("biosphere3", "0795345f-c7ae-410c-ad25-1845784c75f5"),
    "nitrous_oxide": ("biosphere3", "20185046-64bb-4c09-a8e7-e8a9e144ca98"),
    "nitrogen_oxides": ("biosphere3", "c1b91234-6f24-417b-8309-46111d09c457"),
    "sulfur_dioxide": ("biosphere3", "fd7aa71c-508c-480d-81a6-8052aad92646"),
    "carbon_monoxide": ("biosphere3", "ba2f3f82-c93a-47a5-822a-37ec97495275"),
}

# ---------------------------------------------------------------------------
# Data classes for LCA Results
# ---------------------------------------------------------------------------


@dataclass
class ProcessContribution:
    process_id: str
    process_name: str
    stage: str
    score: float
    percentage: float
    unit: str = "kg CO2-eq"


@dataclass
class StageContribution:
    stage: str
    score: float
    percentage: float
    unit: str = "kg CO2-eq"


@dataclass
class FlowContribution:
    flow_name: str
    category: str
    amount: float
    unit: str
    score: float
    percentage: float


@dataclass
class TransportContribution:
    process_id: str
    process_name: str
    mode: str
    distance_km: float
    mass_kg: float
    tkm: float
    score: float
    percentage: float


@dataclass
class LCAResult:
    product_id: str
    product_name: str
    functional_unit_amount: float
    functional_unit: str
    method_name: str
    method_unit: str
    total_score: float
    process_contributions: list[ProcessContribution] = field(default_factory=list)
    stage_contributions: list[StageContribution] = field(default_factory=list)
    flow_contributions: list[FlowContribution] = field(default_factory=list)
    transport_contributions: list[TransportContribution] = field(default_factory=list)
    transport_score: float = 0.0
    transport_percentage: float = 0.0
    inventory_summary: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Background Library Definition & Initialization
# ---------------------------------------------------------------------------

STANDARD_BACKGROUND_ACTIVITIES: dict[str, dict[str, Any]] = {
    # Electricity grid & generation (per kWh)
    "electricity_grid": {
        "name": "Electricity, grid average",
        "unit": "kWh",
        "co2_factor": 0.450,  # kg CO2 / kWh
        "aliases": ["electricity", "power", "grid electricity", "manufacturing electricity", "electric power"],
    },
    "electricity_coal": {
        "name": "Electricity, coal-fired",
        "unit": "kWh",
        "co2_factor": 0.950,
        "aliases": ["coal electricity", "coal power"],
    },
    "electricity_gas": {
        "name": "Electricity, natural gas combined cycle",
        "unit": "kWh",
        "co2_factor": 0.420,
        "aliases": ["gas electricity", "gas power"],
    },
    "electricity_solar": {
        "name": "Electricity, solar photovoltaic",
        "unit": "kWh",
        "co2_factor": 0.040,
        "aliases": ["solar", "solar electricity", "pv electricity"],
    },
    "electricity_wind": {
        "name": "Electricity, wind onshore",
        "unit": "kWh",
        "co2_factor": 0.015,
        "aliases": ["wind electricity", "wind power"],
    },
    "electricity_hydro": {
        "name": "Electricity, hydropower",
        "unit": "kWh",
        "co2_factor": 0.020,
        "aliases": ["hydro electricity", "hydropower"],
    },
    # Fuels and heat (per kg, L, or m3)
    "diesel_fuel": {
        "name": "Diesel fuel, burned in industrial boiler/equipment",
        "unit": "kg",
        "co2_factor": 3.150,  # kg CO2 / kg diesel
        "aliases": ["diesel", "diesel fuel", "gasoil"],
    },
    "petrol_fuel": {
        "name": "Petrol / gasoline, burned",
        "unit": "kg",
        "co2_factor": 3.100,
        "aliases": ["petrol", "gasoline"],
    },
    "natural_gas": {
        "name": "Natural gas, burned in boiler",
        "unit": "m3",
        "co2_factor": 2.000,
        "aliases": ["natural gas", "gas fuel", "methane gas"],
    },
    "heavy_fuel_oil": {
        "name": "Heavy fuel oil, burned",
        "unit": "kg",
        "co2_factor": 3.150,
        "aliases": ["heavy fuel oil", "hfo"],
    },
    # Freight transport (per tonne*km / tkm)
    "transport_truck": {
        "name": "Freight transport, truck (road)",
        "unit": "metric ton*km",
        "co2_factor": 0.120,  # kg CO2 / tkm
        "aliases": ["truck", "lorry", "road", "road transport", "truck transport", "truck_16t", "truck 16t"],
    },
    "transport_train": {
        "name": "Freight transport, rail / train",
        "unit": "metric ton*km",
        "co2_factor": 0.035,
        "aliases": ["train", "rail", "rail transport", "train transport"],
    },
    "transport_ship": {
        "name": "Freight transport, maritime sea ship / container",
        "unit": "metric ton*km",
        "co2_factor": 0.015,
        "aliases": ["ship", "sea", "maritime", "boat", "vessel", "ocean freight"],
    },
    "transport_air": {
        "name": "Freight transport, air cargo flight",
        "unit": "metric ton*km",
        "co2_factor": 0.850,
        "aliases": ["air", "plane", "aircraft", "flight", "air freight"],
    },
    # Common raw materials (generic baseline factors if user has not modeled sub-processes)
    "plastic_granules": {
        "name": "Plastic granules / pellets (generic)",
        "unit": "kg",
        "co2_factor": 2.000,
        "aliases": ["plastic granules", "plastic", "polymer", "polyethylene", "pe", "pp", "plastic resin", "broom bristles"],
    },
    "steel_generic": {
        "name": "Steel, structural generic",
        "unit": "kg",
        "co2_factor": 1.800,
        "aliases": ["steel", "iron", "structural steel", "carbon steel"],
    },
    "aluminum_generic": {
        "name": "Aluminum, primary/secondary generic",
        "unit": "kg",
        "co2_factor": 8.500,
        "aliases": ["aluminum", "aluminium"],
    },
    "copper_generic": {
        "name": "Copper, refined generic",
        "unit": "kg",
        "co2_factor": 4.500,
        "aliases": ["copper"],
    },
    "glass_generic": {
        "name": "Glass, container/flat generic",
        "unit": "kg",
        "co2_factor": 0.850,
        "aliases": ["glass"],
    },
    "cardboard_generic": {
        "name": "Cardboard, corrugated packaging",
        "unit": "kg",
        "co2_factor": 0.900,
        "aliases": ["cardboard", "corrugated board", "carton", "box"],
    },
    "paper_generic": {
        "name": "Paper, office/printing generic",
        "unit": "kg",
        "co2_factor": 1.100,
        "aliases": ["paper", "kraft paper"],
    },
    "wood_generic": {
        "name": "Wood, sawn timber",
        "unit": "kg",
        "co2_factor": 0.250,
        "aliases": ["wood", "timber", "lumber"],
    },
    "water_tap": {
        "name": "Tap water, municipal",
        "unit": "kg",
        "co2_factor": 0.0003,
        "aliases": ["water", "tap water", "process water"],
    },
    # Refinery & Petrochemical Feedstocks & Utilities
    "crude_oil": {
        "name": "Crude oil, petroleum at extraction/refinery gate",
        "unit": "kg",
        "co2_factor": 0.120,  # kg CO2 / kg crude oil
        "aliases": ["crude_oil", "crude oil", "petroleum crude", "crude", "oil crude"],
    },
    "natural_gas_heat": {
        "name": "Process heat, from natural gas boiler",
        "unit": "kWh",
        "co2_factor": 0.220,  # kg CO2 / kWh heat
        "aliases": ["natural_gas_heat", "process heat", "heat, natural gas", "natural gas heat", "industrial heat"],
    },
    "electricity_grid_sa": {
        "name": "Electricity, national grid (SA / regional)",
        "unit": "kWh",
        "co2_factor": 0.580,  # kg CO2 / kWh
        "aliases": ["electricity_grid_sa", "process electricity", "grid sa", "electricity sa"],
    },
    "hydrogen_smr": {
        "name": "Hydrogen, steam methane reforming (hydrotreating)",
        "unit": "kg",
        "co2_factor": 9.500,  # kg CO2 / kg H2
        "aliases": ["hydrogen_smr", "hydrogen (hydrotreating)", "hydrogen", "smr hydrogen", "h2"],
    },
    "wastewater_treatment": {
        "name": "Process wastewater treatment",
        "unit": "m3",
        "co2_factor": 0.350,  # kg CO2 / m3
        "aliases": ["wastewater_treatment", "process wastewater", "wastewater", "effluent"],
    },
    "hazardous_waste_incineration": {
        "name": "Hazardous waste incineration / spent catalyst",
        "unit": "kg",
        "co2_factor": 1.200,  # kg CO2 / kg
        "aliases": ["hazardous_waste_incineration", "spent catalyst", "catalyst waste", "hazardous waste"],
    },
}


def ensure_background_database(
    project_name: str = DEFAULT_PROJECT,
    force_recreate: bool = False,
) -> bd.Database:
    """Ensure that the standard background library database is registered and populated."""
    bd.projects.set_current(project_name)

    if force_recreate and BACKGROUND_DB_NAME in bd.databases:
        del bd.databases[BACKGROUND_DB_NAME]

    if BACKGROUND_DB_NAME in bd.databases:
        db = bd.Database(BACKGROUND_DB_NAME)
        all_exist = True
        for code in STANDARD_BACKGROUND_ACTIVITIES:
            try:
                db.get(code)
            except Exception:
                all_exist = False
                break
        if all_exist:
            return db
        # If incomplete, delete and recreate cleanly
        del bd.databases[BACKGROUND_DB_NAME]

    db = bd.Database(BACKGROUND_DB_NAME)
    db.register()

    # Retrieve canonical fossil CO2 from biosphere3
    bio_db = bd.Database("biosphere3")
    co2_flow = bio_db.get(BIOSPHERE3_FLOWS["co2_fossil"][1])

    for code, info in STANDARD_BACKGROUND_ACTIVITIES.items():
        act = db.new_activity(
            code=code,
            name=info["name"],
            unit=info["unit"],
            type="process",
        )
        # 1 unit reference output
        act.new_exchange(
            input=act.key,
            amount=1.0,
            type="production",
        ).save()

        # Environmental emission exchange
        if info.get("co2_factor", 0) > 0:
            act.new_exchange(
                input=co2_flow.key,
                amount=info["co2_factor"],
                type="biosphere",
            ).save()

        act.save()

    return db


# ---------------------------------------------------------------------------
# Flow Resolution (Internal Process vs Background vs Biosphere Emission)
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Normalize names for case-insensitive, punctuation-tolerant matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def match_background_activity(flow_name: str, bg_db: bd.Database) -> bd.Activity | None:
    """Find a background activity matching a flow name or alias."""
    norm = _normalize_name(flow_name)

    # 1. Exact or alias matching
    for code, info in STANDARD_BACKGROUND_ACTIVITIES.items():
        if norm == _normalize_name(code) or norm == _normalize_name(info["name"]):
            return bg_db.get(code)
        for alias in info.get("aliases", []):
            if norm == _normalize_name(alias):
                return bg_db.get(code)

    # 2. Substring matching
    for code, info in STANDARD_BACKGROUND_ACTIVITIES.items():
        for alias in info.get("aliases", []):
            alias_norm = _normalize_name(alias)
            if alias_norm in norm or norm in alias_norm:
                return bg_db.get(code)

    return None


def match_biosphere_emission(flow_name: str) -> bd.Activity | None:
    """Match an output flow name to an elementary emission in biosphere3."""
    norm = _normalize_name(flow_name)
    bio_db = bd.Database("biosphere3")

    if any(k in norm for k in ["co2", "carbondioxide", "carbon"]):
        return bio_db.get(BIOSPHERE3_FLOWS["co2_fossil"][1])
    if any(k in norm for k in ["ch4", "methane"]):
        return bio_db.get(BIOSPHERE3_FLOWS["methane_fossil"][1])
    if any(k in norm for k in ["n2o", "nitrousoxide", "dinitrogenmonoxide"]):
        return bio_db.get(BIOSPHERE3_FLOWS["nitrous_oxide"][1])
    if any(k in norm for k in ["nox", "nitrogenoxides", "nitrogenoxide"]):
        return bio_db.get(BIOSPHERE3_FLOWS["nitrogen_oxides"][1])
    if any(k in norm for k in ["so2", "sulfurdioxide"]):
        return bio_db.get(BIOSPHERE3_FLOWS["sulfur_dioxide"][1])
    if any(k in norm for k in ["co", "carbonmonoxide"]) and "dioxide" not in norm:
        return bio_db.get(BIOSPHERE3_FLOWS["carbon_monoxide"][1])

    return None


def match_transport_mode(mode_name: str, bg_db: bd.Database) -> bd.Activity:
    """Map a transport mode string to the standard background freight activity."""
    norm = _normalize_name(mode_name)

    if any(k in norm for k in ["rail", "train"]):
        return bg_db.get("transport_train")
    if any(k in norm for k in ["ship", "sea", "ocean", "boat", "marine", "water"]):
        return bg_db.get("transport_ship")
    if any(k in norm for k in ["air", "plane", "flight", "cargo"]):
        return bg_db.get("transport_air")

    # Default to road truck
    return bg_db.get("transport_truck")


# ---------------------------------------------------------------------------
# Dynamic Product Compiler
# ---------------------------------------------------------------------------


def compile_product_to_brightway(
    product: Product,
    project_name: str = DEFAULT_PROJECT,
) -> tuple[bd.Activity, bd.Database, list[str]]:
    """Compile a Product into a Brightway database with connected exchanges.

    Returns:
        (root_activity, product_database, list_of_warning_messages)
    """
    bd.projects.set_current(project_name)
    bg_db = ensure_background_database(project_name)

    warnings: list[str] = []

    # Clean safe database name for the user product
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", product.product_id.strip().lower())
    db_name = f"user_prod_{clean_id}"

    if db_name in bd.databases:
        del bd.databases[db_name]

    prod_db = bd.Database(db_name)
    prod_db.register()

    # 1. Create all process activities
    activities_by_id: dict[str, bd.Activity] = {}
    activities_by_name: dict[str, bd.Activity] = {}

    for process in product.processes:
        proc_code = f"proc_{_normalize_name(process.process_id)}"
        act = prod_db.new_activity(
            code=proc_code,
            name=process.process_name,
            unit="unit",
            type="process",
            stage=process.stage,
            original_id=process.process_id,
        )
        # Reference production exchange (1 unit of output)
        act.new_exchange(
            input=act.key,
            amount=1.0,
            type="production",
        ).save()
        act.save()

        activities_by_id[process.process_id.strip()] = act
        activities_by_name[_normalize_name(process.process_name)] = act

    # 2. Add exchanges (inputs, outputs, emissions)
    for process in product.processes:
        current_act = activities_by_id[process.process_id.strip()]

        for exc in process.exchanges:
            flow_name = exc.flow_name.strip()
            norm_flow = _normalize_name(flow_name)
            amount = float(exc.amount)

            if exc.exchange_type.lower() == "output":
                # Check if it represents an elementary emission (e.g. CO2, CH4)
                bio_flow = match_biosphere_emission(flow_name)
                if bio_flow:
                    current_act.new_exchange(
                        input=bio_flow.key,
                        amount=amount,
                        type="biosphere",
                    ).save()
                else:
                    # Output is a product/co-product or custom flow
                    pass

            else:
                # exchange_type == "input"
                # A. Check if it's an internal process in this product
                matched_internal = None
                for pid, act in activities_by_id.items():
                    if norm_flow == _normalize_name(pid):
                        matched_internal = act
                        break
                if not matched_internal and norm_flow in activities_by_name:
                    matched_internal = activities_by_name[norm_flow]

                if matched_internal:
                    current_act.new_exchange(
                        input=matched_internal.key,
                        amount=amount,
                        type="technosphere",
                    ).save()
                else:
                    # B. Check if it matches a background activity
                    bg_act = match_background_activity(flow_name, bg_db)
                    if bg_act:
                        current_act.new_exchange(
                            input=bg_act.key,
                            amount=amount,
                            type="technosphere",
                        ).save()
                    else:
                        # C. Unrecognized external input: create a placeholder so model succeeds
                        placeholder_code = f"input_{norm_flow}"
                        if placeholder_code in prod_db:
                            p_act = prod_db.get(placeholder_code)
                        else:
                            p_act = prod_db.new_activity(
                                code=placeholder_code,
                                name=f"{flow_name} (unlinked input)",
                                unit=exc.unit or "kg",
                                type="process",
                            )
                            p_act.new_exchange(
                                input=p_act.key,
                                amount=1.0,
                                type="production",
                            ).save()
                            p_act.save()

                        current_act.new_exchange(
                            input=p_act.key,
                            amount=amount,
                            type="technosphere",
                        ).save()
                        warnings.append(
                            f"Process '{process.process_name}': Input flow '{flow_name}' "
                            "was not found in internal processes or background database. "
                            "A placeholder activity with 0 direct emissions was created."
                        )

        # 3. Add transportation legs
        for transport in process.transportation:
            dist_km = float(transport.distance)
            if dist_km <= 0:
                continue

            # Mass conversion to metric tonnes
            mass_kg = transport.transported_mass
            if mass_kg is None or mass_kg <= 0:
                # Default to 1 kg if mass not specified
                mass_kg = 1.0
            elif transport.mass_unit and transport.mass_unit.lower() in ["t", "tonne", "ton", "tonnes"]:
                mass_kg = mass_kg * 1000.0

            mass_tonnes = mass_kg / 1000.0
            tkm = dist_km * mass_tonnes

            t_act = match_transport_mode(transport.transport_mode, bg_db)
            current_act.new_exchange(
                input=t_act.key,
                amount=tkm,
                type="technosphere",
            ).save()

        current_act.save()

    # 4. Determine or create Root Activity
    # Find processes that are not consumed by any other process
    consumed_keys = set()
    for act in prod_db:
        for exc in act.technosphere():
            consumed_keys.add(exc.input.key)

    top_level_acts = [
        act for act in activities_by_id.values() if act.key not in consumed_keys
    ]

    if len(top_level_acts) == 1:
        root_act = top_level_acts[0]
    elif len(top_level_acts) > 1:
        # Create an overarching root aggregator activity for the functional unit
        root_act = prod_db.new_activity(
            code="product_functional_unit",
            name=f"{product.product_name} (Functional Unit)",
            unit=product.functional_unit,
            type="process",
            stage="Product System",
        )
        root_act.new_exchange(
            input=root_act.key,
            amount=1.0,
            type="production",
        ).save()

        # Connect each top-level unconsumed stage
        for act in top_level_acts:
            root_act.new_exchange(
                input=act.key,
                amount=1.0,
                type="technosphere",
            ).save()

        root_act.save()
    else:
        # If there's a circularity or single process
        root_act = list(activities_by_id.values())[-1]

    return root_act, prod_db, warnings


# ---------------------------------------------------------------------------
# Dynamic LCA Calculation & Contribution Analysis
# ---------------------------------------------------------------------------


def calculate_product_lca(
    product: Product,
    method: tuple[str, ...] | None = None,
    project_name: str = DEFAULT_PROJECT,
) -> LCAResult:
    """Compile a Product and calculate full Life Cycle Impact Assessment (LCIA)
    with process, stage, flow, and transportation contribution breakdowns.
    """
    if method is None:
        method = DEFAULT_LCIA_METHOD

    # 1. Compile product model into Brightway
    root_act, prod_db, warnings = compile_product_to_brightway(
        product=product,
        project_name=project_name,
    )

    # 2. Run LCA
    demand = {root_act: float(product.functional_unit_amount)}
    lca = bc.LCA(demand, method=method)
    lca.lci()
    lca.lcia()

    total_score = float(lca.score)
    method_name = " / ".join(method)
    method_unit = "kg CO2-eq"

    # 3. Process & Activity Contributions
    # Column sum of characterized_inventory gives contribution per activity
    col_sums = np.array(lca.characterized_inventory.sum(axis=0)).flatten()
    inv_activity_dict = {idx: key for key, idx in lca.activity_dict.items()}

    process_contribs: list[ProcessContribution] = []
    transport_contribs: list[TransportContribution] = []
    transport_total_score = 0.0

    # Build process metadata map
    proc_meta_by_name = {
        _normalize_name(p.process_name): p for p in product.processes
    }
    proc_meta_by_id = {p.process_id: p for p in product.processes}

    stage_scores: dict[str, float] = {}

    for idx, act_score in enumerate(col_sums):
        score_val = float(act_score)
        act_key = inv_activity_dict[idx]

        try:
            act = bd.get_activity(act_key)
            db_origin = act.key[0]
            act_name = act["name"]
            stage = act.get("stage", "Supply Chain / Background")

            # Check if this is a background transport activity
            if "Freight transport" in act_name:
                transport_total_score += score_val

            # Map to user process if possible
            matching_proc = None
            if act.get("original_id") and act["original_id"] in proc_meta_by_id:
                matching_proc = proc_meta_by_id[act["original_id"]]
            elif _normalize_name(act_name) in proc_meta_by_name:
                matching_proc = proc_meta_by_name[_normalize_name(act_name)]

            if matching_proc:
                p_id = matching_proc.process_id
                p_name = matching_proc.process_name
                stage = matching_proc.stage or "Unspecified"
            elif db_origin == BACKGROUND_DB_NAME:
                p_id = act["code"]
                p_name = act_name
                stage = "Materials & Energy (Background)"
            else:
                p_id = act.get("code", str(act_key))
                p_name = act_name

            percentage = (score_val / total_score * 100.0) if total_score > 0 else 0.0

            if abs(score_val) > 1e-9 or percentage > 0.01:
                process_contribs.append(
                    ProcessContribution(
                        process_id=p_id,
                        process_name=p_name,
                        stage=stage,
                        score=score_val,
                        percentage=percentage,
                        unit=method_unit,
                    )
                )

            stage_scores[stage] = stage_scores.get(stage, 0.0) + score_val

        except Exception:
            continue

    # Sort processes descending by score
    process_contribs.sort(key=lambda x: x.score, reverse=True)

    # 4. Stage Contributions
    stage_contribs: list[StageContribution] = []
    for stage_name, s_val in stage_scores.items():
        pct = (s_val / total_score * 100.0) if total_score > 0 else 0.0
        stage_contribs.append(
            StageContribution(
                stage=stage_name,
                score=s_val,
                percentage=pct,
                unit=method_unit,
            )
        )
    stage_contribs.sort(key=lambda x: x.score, reverse=True)

    # 5. Biosphere Flow Contributions
    # Row sum of characterized_inventory gives contribution per biosphere flow
    row_sums = np.array(lca.characterized_inventory.sum(axis=1)).flatten()
    inv_biosphere_dict = {idx: key for key, idx in lca.biosphere_dict.items()}

    flow_contribs: list[FlowContribution] = []
    for idx, f_score in enumerate(row_sums):
        score_val = float(f_score)
        if abs(score_val) < 1e-9:
            continue

        flow_key = inv_biosphere_dict[idx]
        try:
            flow_act = bd.get_activity(flow_key)
            f_name = flow_act["name"]
            cats = flow_act.get("categories", ("air",))
            cat_str = " / ".join(cats) if isinstance(cats, (tuple, list)) else str(cats)
            f_unit = flow_act.get("unit", "kg")
            amount = float(lca.inventory[idx, :].sum())

            pct = (score_val / total_score * 100.0) if total_score > 0 else 0.0
            flow_contribs.append(
                FlowContribution(
                    flow_name=f_name,
                    category=cat_str,
                    amount=amount,
                    unit=f_unit,
                    score=score_val,
                    percentage=pct,
                )
            )
        except Exception:
            continue

    flow_contribs.sort(key=lambda x: x.score, reverse=True)

    # 6. Detailed Transportation Legs Breakdown
    for process in product.processes:
        for t in process.transportation:
            dist = float(t.distance)
            mass_kg = t.transported_mass or 1.0
            if t.mass_unit and t.mass_unit.lower() in ["t", "tonne", "ton", "tonnes"]:
                mass_kg = mass_kg * 1000.0
            tkm = dist * (mass_kg / 1000.0)

            # Estimate transport impact
            t_act = match_transport_mode(t.transport_mode, ensure_background_database(project_name))
            info = STANDARD_BACKGROUND_ACTIVITIES.get(t_act["code"], {"co2_factor": 0.12})
            t_score = tkm * info.get("co2_factor", 0.12)
            pct = (t_score / total_score * 100.0) if total_score > 0 else 0.0

            transport_contribs.append(
                TransportContribution(
                    process_id=process.process_id,
                    process_name=process.process_name,
                    mode=t.transport_mode,
                    distance_km=dist,
                    mass_kg=mass_kg,
                    tkm=tkm,
                    score=t_score,
                    percentage=pct,
                )
            )

    transport_contribs.sort(key=lambda x: x.score, reverse=True)
    t_pct = (transport_total_score / total_score * 100.0) if total_score > 0 else 0.0

    return LCAResult(
        product_id=product.product_id,
        product_name=product.product_name,
        functional_unit_amount=product.functional_unit_amount,
        functional_unit=product.functional_unit,
        method_name=method_name,
        method_unit=method_unit,
        total_score=total_score,
        process_contributions=process_contribs,
        stage_contributions=stage_contribs,
        flow_contributions=flow_contribs,
        transport_contributions=transport_contribs,
        transport_score=transport_total_score,
        transport_percentage=t_pct,
        inventory_summary={
            "total_co2_kg": float(lca.inventory.sum()),
            "transport_tkm": sum(t.tkm for t in transport_contribs),
        },
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# LCIA Method Utilities
# ---------------------------------------------------------------------------


def get_available_methods(search: str | None = None, limit: int = 50) -> list[tuple[tuple[str, ...], str]]:
    """List available LCIA methods with human-readable display names."""
    bd.projects.set_current(DEFAULT_PROJECT)
    all_methods = list(bd.methods)

    if not search:
        # Prioritize standard climate and CML methods
        preferred = [m for m in all_methods if "climate" in str(m).lower() or "cml" in str(m).lower()]
        selected = preferred[:limit] if preferred else all_methods[:limit]
    else:
        q = search.lower()
        selected = [m for m in all_methods if q in str(m).lower()][:limit]

    return [(m, " → ".join(m)) for m in selected]


# ---------------------------------------------------------------------------
# Dynamic PCF LCA Project & Calculation Solver (Driven by PostgreSQL)
# ---------------------------------------------------------------------------

PCF_PROJECT = os.getenv("BW_PROJECT", "pcf_lca_api")
PCF_BIO = "lca_bio"
PCF_DB = "lca_db"
PCF_SCRATCH = "lca_runs"


def sync_pcf_lca_project(force: bool = False) -> None:
    """Synchronize the Brightway project with flows, methods, and activities
    dynamically defined in the PostgreSQL database.
    """
    import db

    bd.projects.set_current(PCF_PROJECT)

    if not force and PCF_BIO in bd.databases and PCF_DB in bd.databases:
        # Check if already initialized with current methods count
        db_methods_count = len(db.get_all_methods_db())
        current_bw_methods = [m for m in bd.methods if m[0] in ["IPCC AR6", "DEMO"]]
        if len(current_bw_methods) >= db_methods_count:
            return

    # Clear old databases
    for name in (PCF_BIO, PCF_DB, PCF_SCRATCH):
        if name in bd.databases:
            del bd.databases[name]

    # 1. Load from PostgreSQL
    flows = db.get_all_flows_db()
    methods = db.get_all_methods_db()
    activities = db.get_all_activities_db()
    valid_flow_codes = {f["code"] for f in flows}

    # Deregister existing methods in project
    for m in methods:
        mt = tuple(m["method_tuple"])
        if mt in bd.methods:
            bd.Method(mt).deregister()

    # 2. Write Biosphere Database (lca_bio)
    bd.Database(PCF_BIO).write({
        (PCF_BIO, f["code"]): {
            "name": f["name"],
            "unit": f["unit"],
            "categories": (f.get("categories", "air"),),
            "type": f.get("flow_type", "emission"),
        }
        for f in flows
    })

    # 3. Write LCIA Methods
    for m in methods:
        mt = tuple(m["method_tuple"])
        bm = bd.Method(mt)
        bm.register(unit=m["unit"])
        bm.write([
            ((PCF_BIO, flow_code), factor)
            for flow_code, factor in m["cfs"].items()
            if flow_code in valid_flow_codes
        ])

    # 4. Write Technosphere Activities Database (lca_db)
    data = {}
    for a in activities:
        code = a["code"]
        name = a["name"]
        unit = a["unit"]
        loc = a.get("location", "GLO")
        bio_ex = a.get("emissions") or {}
        tech_ex = a.get("technosphere") or {}

        ex = [{"input": (PCF_DB, code), "output": (PCF_DB, code), "amount": 1.0, "type": "production"}]
        ex += [{"input": (PCF_BIO, f), "output": (PCF_DB, code), "amount": amt, "type": "biosphere"}
               for f, amt in bio_ex.items()]
        ex += [{"input": (PCF_DB, o), "output": (PCF_DB, code), "amount": amt, "type": "technosphere"}
               for o, amt in tech_ex.items()]

        data[(PCF_DB, code)] = {
            "name": name,
            "unit": unit,
            "location": loc,
            "reference product": name,
            "exchanges": ex,
        }

    bd.Database(PCF_DB).write(data)

    if PCF_SCRATCH not in bd.databases:
        bd.Database(PCF_SCRATCH).register()


def sync_single_activity(code: str) -> None:
    """Incrementally synchronize a single activity into lca_db without wiping the database."""
    import db
    bd.projects.set_current(PCF_PROJECT)
    if PCF_DB not in bd.databases or PCF_BIO not in bd.databases:
        sync_pcf_lca_project(force=False)

    activities = db.get_all_activities_db()
    a = next((act for act in activities if act["code"] == code), None)
    if not a:
        return

    lca_db = bd.Database(PCF_DB)
    if (PCF_DB, code) in lca_db:
        act = lca_db.get(code)
        for exc in list(act.exchanges()):
            exc.delete()
    else:
        act = lca_db.new_activity(code=code)

    act["name"] = a["name"]
    act["unit"] = a["unit"]
    act["location"] = a.get("location", "GLO")
    act["reference product"] = a["name"]
    act.save()

    act.new_exchange(input=act.key, amount=1.0, type="production").save()
    for f, amt in (a.get("emissions") or {}).items():
        act.new_exchange(input=(PCF_BIO, f), amount=amt, type="biosphere").save()
    for o, amt in (a.get("technosphere") or {}).items():
        act.new_exchange(input=(PCF_DB, o), amount=amt, type="technosphere").save()
    act.save()


def delete_single_activity(code: str) -> None:
    """Remove a single activity node from lca_db without rebuilding the database."""
    bd.projects.set_current(PCF_PROJECT)
    if PCF_DB in bd.databases:
        lca_db = bd.Database(PCF_DB)
        if (PCF_DB, code) in lca_db:
            lca_db.get(code).delete()


def sync_single_flow(code: str) -> None:
    """Incrementally synchronize an elementary emission flow in lca_bio."""
    import db
    bd.projects.set_current(PCF_PROJECT)
    if PCF_BIO not in bd.databases:
        sync_pcf_lca_project(force=False)

    flows = db.get_all_flows_db()
    f_data = next((fl for fl in flows if fl["code"] == code), None)
    if not f_data:
        return

    lca_bio = bd.Database(PCF_BIO)
    if (PCF_BIO, code) in lca_bio:
        flow_act = lca_bio.get(code)
    else:
        flow_act = lca_bio.new_activity(code=code)

    flow_act["name"] = f_data["name"]
    flow_act["unit"] = f_data["unit"]
    flow_act["categories"] = (f_data.get("categories", "air"),)
    flow_act["type"] = f_data.get("flow_type", "emission")
    flow_act.save()


def delete_single_flow(code: str) -> None:
    """Remove a single elementary flow from lca_bio."""
    bd.projects.set_current(PCF_PROJECT)
    if PCF_BIO in bd.databases:
        lca_bio = bd.Database(PCF_BIO)
        if (PCF_BIO, code) in lca_bio:
            lca_bio.get(code).delete()


def sync_single_method(key: str) -> None:
    """Incrementally register or update a single LCIA method."""
    import db
    bd.projects.set_current(PCF_PROJECT)
    methods = db.get_all_methods_db()
    m_data = next((m for m in methods if m["key"] == key), None)
    if not m_data:
        return

    mt = tuple(m_data["method_tuple"])
    if mt in bd.methods:
        bd.Method(mt).deregister()

    flows = db.get_all_flows_db()
    valid_flow_codes = {f["code"] for f in flows}

    bm = bd.Method(mt)
    bm.register(unit=m_data["unit"])
    bm.write([
        ((PCF_BIO, flow_code), factor)
        for flow_code, factor in m_data["cfs"].items()
        if flow_code in valid_flow_codes
    ])


def delete_single_method(key: str) -> None:
    """Deregister a single LCIA method."""
    import db
    bd.projects.set_current(PCF_PROJECT)
    methods = db.get_all_methods_db()
    m_data = next((m for m in methods if m["key"] == key), None)
    if m_data:
        mt = tuple(m_data["method_tuple"])
        if mt in bd.methods:
            bd.Method(mt).deregister()


LHV_DEFAULTS: dict[str, float] = {
    "diesel": 43.0,
    "diesel, refinery gate": 43.0,
    "gasoline": 44.0,
    "petrol": 44.0,
    "lpg": 46.1,
    "liquefied petroleum gas": 46.1,
    "crude_oil": 42.5,
    "crude oil": 42.5,
    "natural_gas": 48.0,
    "natural gas": 48.0,
    "methane": 50.0,
    "hydrogen": 120.0,
    "heavy fuel oil": 40.5,
    "fuel oil": 40.5,
    "kerosene": 43.5,
    "jet fuel": 43.5,
    "naphtha": 44.5,
    "coal": 24.0,
    "biomass": 17.5,
    "wood pellets": 18.0,
    "electricity": 3.6,
}


def get_output_lhv(item: dict[str, Any]) -> float:
    """Retrieve Lower Heating Value / Net Calorific Value (in MJ/kg or MJ/unit)."""
    if "lhv" in item:
        return float(item["lhv"])
    if "energy_density" in item:
        return float(item["energy_density"])
    name = str(item.get("name", "")).lower().strip()
    for k, v in LHV_DEFAULTS.items():
        if k in name:
            return v
    return 42.0


def calculate_pcf_lca(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute dynamic multi-method LCA on a raw PCF payload with:
    1. ISO 14044 Allocation: Mass, Economic, and Energy (LHV Net Calorific Value)
    2. Dynamic Unit Conversion pipeline across all inputs, transport, waste, and emissions
    3. Thread-safe execution using isolated scratch database (lca_runs)
    4. Comprehensive characterized impacts across all configured LCIA methods
    """
    import db

    sync_pcf_lca_project(force=False)
    bd.projects.set_current(PCF_PROJECT)

    scratch_db = bd.Database(PCF_SCRATCH)
    if PCF_SCRATCH not in bd.databases:
        scratch_db.register()

    lca_db = bd.Database(PCF_DB)
    lca_bio = bd.Database(PCF_BIO)

    # 1. Product info
    prod_data = payload.get("product") or {}
    product_name = prod_data.get("name", "Product")
    fu_str = prod_data.get("functional_unit", "1 kg")

    # 2. Allocation Calculation (ISO 14044: Mass, Economic, Energy / LHV)
    alloc_data = payload.get("allocation") or {}
    alloc_method = str(alloc_data.get("method", "mass")).lower().strip()

    outputs = payload.get("outputs") or []
    main_prod = next((o for o in outputs if o.get("type") == "product"), None)
    main_amount = float(main_prod.get("amount", 1.0)) if main_prod else 1.0
    main_price = float(main_prod.get("price", 1.0)) if main_prod else 1.0

    co_prods = [o for o in outputs if o.get("type") in ["co_product", "coproduct"]]
    emissions = [o for o in outputs if o.get("type") == "emission"]
    wastes = [o for o in outputs if o.get("type") in ["waste", "byproduct_waste"]]

    alloc_factor = 1.0
    total_mass = main_amount + sum(float(cp.get("amount", 0.0)) for cp in co_prods)

    main_energy: float | None = None
    total_energy: float | None = None

    if co_prods:
        if alloc_method in ["energy", "lhv", "calorific"]:
            main_lhv = get_output_lhv(main_prod) if main_prod else 43.0
            main_energy = main_amount * main_lhv
            co_energy = sum(float(cp.get("amount", 0.0)) * get_output_lhv(cp) for cp in co_prods)
            total_energy = main_energy + co_energy
            alloc_factor = (main_energy / total_energy) if total_energy > 0 else 1.0
        elif alloc_method == "economic":
            total_rev = (main_amount * main_price) + sum(
                float(cp.get("amount", 0.0)) * float(cp.get("price", 1.0)) for cp in co_prods
            )
            alloc_factor = ((main_amount * main_price) / total_rev) if total_rev > 0 else 1.0
        else:
            # Default to ISO 14044 mass allocation
            alloc_factor = (main_amount / total_mass) if total_mass > 0 else 1.0

    # 3. Create foreground activity in dedicated scratch database (lca_runs)
    # This keeps lca_db immutable, preventing concurrency collisions and file locks
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    act_code = f"eval_{run_id}"

    act = scratch_db.new_activity(
        code=act_code,
        name=product_name,
        unit="kilogram",
        type="process",
    )
    act.new_exchange(input=act.key, amount=1.0, type="production").save()

    # Track components for hotspot breakdown
    component_activities: list[tuple[str, str, Any, float]] = []

    # Add Inputs with automatic unit conversion
    for inp in payload.get("inputs") or []:
        raw_amt = float(inp.get("amount", inp.get("mass", 0.0)))
        input_unit = inp.get("unit") or inp.get("mass_unit")

        if "distance_km" in inp or "distance" in inp:
            dist_val = float(inp.get("distance_km", inp.get("distance", 0.0)))
            dist_unit = inp.get("distance_unit", "km")
            dist_km = db.convert_unit_db(dist_val, dist_unit, "km")

            mass_val = raw_amt
            mass_u = input_unit or "kg"
            mass_kg = db.convert_unit_db(mass_val, mass_u, "kg")

            tkm = (mass_kg / 1000.0) * dist_km
            allocated_tkm = tkm * alloc_factor
            mode_key = inp.get("key", "truck_16t")

            try:
                t_act = lca_db.get(mode_key)
                act.new_exchange(input=t_act.key, amount=allocated_tkm, type="technosphere").save()
                component_activities.append(("technosphere", inp.get("name", mode_key), t_act, allocated_tkm))
            except Exception:
                pass
        else:
            flow_key = inp.get("key", inp.get("name"))
            try:
                in_act = lca_db.get(flow_key)
                expected_unit = in_act.get("unit", "kilogram")
                converted_amt = db.convert_unit_db(raw_amt, input_unit or expected_unit, expected_unit)
                allocated_amt = converted_amt * alloc_factor
                act.new_exchange(input=in_act.key, amount=allocated_amt, type="technosphere").save()
                component_activities.append(("technosphere", inp.get("name", flow_key), in_act, allocated_amt))
            except Exception:
                pass

    # Add Waste treatments with automatic unit conversion
    for w in wastes:
        waste_key = w.get("key", w.get("name"))
        raw_w_amt = float(w.get("amount", 0.0))
        w_unit = w.get("unit")
        try:
            w_act = lca_db.get(waste_key)
            expected_w_unit = w_act.get("unit", "cubic meter")
            converted_w_amt = db.convert_unit_db(raw_w_amt, w_unit or expected_w_unit, expected_w_unit)
            w_amt = converted_w_amt * alloc_factor
            act.new_exchange(input=w_act.key, amount=w_amt, type="technosphere").save()
            component_activities.append(("technosphere", w.get("name", waste_key), w_act, w_amt))
        except Exception:
            pass

    # Add Direct Emissions with automatic unit conversion
    direct_emissions_list: list[tuple[str, str, float]] = []
    for em in emissions:
        flow_code = em.get("flow", em.get("key", em.get("name", ""))).lower().strip()
        raw_em_amt = float(em.get("amount", 0.0))
        em_unit = em.get("unit")
        try:
            b_flow = lca_bio.get(flow_code)
            expected_em_unit = b_flow.get("unit", "kilogram")
            converted_em_amt = db.convert_unit_db(raw_em_amt, em_unit or expected_em_unit, expected_em_unit)
            em_amt = converted_em_amt * alloc_factor
            act.new_exchange(input=b_flow.key, amount=em_amt, type="biosphere").save()
            direct_emissions_list.append((em.get("name", flow_code), flow_code, em_amt))
        except Exception:
            pass

    act.save()

    # 4. Multi-Method Impact Calculation across all configured methods
    configured_methods = db.get_all_methods_db()
    summary: dict[str, float] = {}
    hotspots: list[dict[str, Any]] = []

    try:
        # Solve each LCIA method
        for m in configured_methods:
            mt = tuple(m["method_tuple"])
            if mt in bd.methods:
                lca = bc.LCA({act: 1.0}, method=mt)
                lca.lci()
                lca.lcia()
                summary[m["key"]] = float(lca.score)

        # Build detailed hotspot rankings for GWP100
        gwp_info = next((m for m in configured_methods if m["key"] == "gwp100"), configured_methods[0])
        gwp_tuple = tuple(gwp_info["method_tuple"])
        gwp_cfs = gwp_info.get("cfs") or {}
        total_gwp = summary.get(gwp_info["key"], 1.0)

        for c_type, c_name, c_act, c_amt in component_activities:
            try:
                sub_lca = bc.LCA({c_act: c_amt}, method=gwp_tuple)
                sub_lca.lci()
                sub_lca.lcia()
                sub_score = float(sub_lca.score)
                pct = (sub_score / total_gwp * 100.0) if total_gwp > 0 else 0.0
                hotspots.append({
                    "name": c_name,
                    "type": "technosphere",
                    "score": round(sub_score, 6),
                    "percentage": round(pct, 2),
                    "unit": gwp_info["unit"],
                })
            except Exception:
                pass

        # Add direct emissions to hotspots
        for d_name, d_code, d_amt in direct_emissions_list:
            cf = gwp_cfs.get(d_code, 1.0 if d_code == "co2" else 0.0)
            d_score = d_amt * cf
            pct = (d_score / total_gwp * 100.0) if total_gwp > 0 else 0.0
            hotspots.append({
                "name": f"{d_name} (direct emission)",
                "type": "biosphere",
                "score": round(d_score, 6),
                "percentage": round(pct, 2),
                "unit": gwp_info["unit"],
            })

        hotspots.sort(key=lambda x: x["score"], reverse=True)

    finally:
        # Clean up temporary foreground activity from scratch database
        try:
            act.delete()
        except Exception:
            pass

    # 5. Record Run into PostgreSQL lca_run table
    meta = payload.get("metadata") or {}
    run_rec = db.record_run_db(
        summary=summary,
        metadata_info=meta,
        request_data=payload,
        product_name=product_name,
        run_id=run_id,
    )

    return {
        "status": "success",
        "run_id": run_id,
        "product_name": product_name,
        "summary": summary,
        "allocation": {
            "method": alloc_method,
            "allocation_factor": round(alloc_factor, 6),
            "allocation_percentage": round(alloc_factor * 100, 2),
            "target_product_amount": main_amount,
            "total_system_mass": total_mass,
            "main_product_energy_mj": round(main_energy, 4) if main_energy is not None else None,
            "total_system_energy_mj": round(total_energy, 4) if total_energy is not None else None,
            "co_products": [
                {
                    "name": cp.get("name"),
                    "amount": float(cp.get("amount", 0.0)),
                    "share_pct": round((float(cp.get("amount", 0.0)) / total_mass) * 100, 2) if total_mass > 0 else 0,
                    **(
                        {
                            "lhv_mj_per_unit": get_output_lhv(cp),
                            "energy_mj": round(float(cp.get("amount", 0.0)) * get_output_lhv(cp), 4),
                            "energy_share_pct": round(((float(cp.get("amount", 0.0)) * get_output_lhv(cp)) / total_energy) * 100, 2) if total_energy and total_energy > 0 else 0,
                        }
                        if total_energy is not None
                        else {}
                    ),
                }
                for cp in co_prods
            ],
        },
        "metadata": meta,
        "hotspots": hotspots[:payload.get("top_n", 12)],
        "created_at": run_rec["created_at"],
    }
