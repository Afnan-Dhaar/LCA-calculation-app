import io
import json
import re
import altair as alt
import pandas as pd
import streamlit as st

from brightway_engine import (
    DEFAULT_LCIA_METHOD,
    LCAResult,
    calculate_product_lca,
    get_available_methods,
)
from excel_importer import import_products_from_excel
from product_model import (
    Exchange,
    Process,
    Product,
    Transportation,
    dict_to_product,
    load_products_from_json,
    product_to_dict,
    save_products_to_json,
    validate_product,
)

# --------------------------------------------------
# 1. Page Configuration & Styling
# --------------------------------------------------

st.set_page_config(
    page_title="Product LCA Studio",
    page_icon="🌱",
    layout="wide",
)

st.title("🌱 Product LCA Studio")
st.caption(
    "Fast, simplified Life Cycle Assessment powered by Brightway. "
    "Define a product with all its inputs, direct emissions, and transportation in one simple screen, "
    "then compute its environmental footprint and contribution hotspots."
)

# --------------------------------------------------
# 2. Default Sample Data Helpers
# --------------------------------------------------

DEFAULT_STAGES = [
    "Raw Materials",
    "Manufacturing",
    "Packaging",
    "Distribution & Transport",
    "Use Phase",
    "End of Life",
]

DEFAULT_MODES = ["truck", "train", "ship", "air"]


def get_default_inputs_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Stage": "Raw Materials",
                "Input Flow Name": "Plastic granules",
                "Amount": 0.30,
                "Unit": "kg",
            },
            {
                "Stage": "Raw Materials",
                "Input Flow Name": "Broom bristles",
                "Amount": 0.10,
                "Unit": "kg",
            },
            {
                "Stage": "Manufacturing",
                "Input Flow Name": "Electricity, grid average",
                "Amount": 0.20,
                "Unit": "kWh",
            },
        ]
    )


def get_default_emissions_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Stage": "Manufacturing",
                "Emission Flow Name": "Carbon dioxide, fossil",
                "Amount": 0.05,
                "Unit": "kg",
            }
        ]
    )


def get_default_transport_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Stage / Route": "Manufacturing",
                "Transport Mode": "truck",
                "Distance (km)": 100.0,
                "Cargo Mass (kg)": 0.40,
            }
        ]
    )


def build_product_from_tables(
    product_id: str,
    product_name: str,
    fu_amount: float,
    fu_unit: str,
    inputs_df: pd.DataFrame,
    emissions_df: pd.DataFrame,
    transport_df: pd.DataFrame,
) -> Product:
    """Compile simple flat tables into a structured multi-process Product model."""
    product_id = product_id.strip()
    product_name = product_name.strip()

    # Discover all distinct stages referenced
    all_stages: list[str] = []
    if "Stage" in inputs_df.columns:
        for s in inputs_df["Stage"].dropna():
            if str(s).strip() and str(s).strip() not in all_stages:
                all_stages.append(str(s).strip())

    if "Stage" in emissions_df.columns:
        for s in emissions_df["Stage"].dropna():
            if str(s).strip() and str(s).strip() not in all_stages:
                all_stages.append(str(s).strip())

    transport_stage_col = "Stage / Route" if "Stage / Route" in transport_df.columns else "Stage"
    if transport_stage_col in transport_df.columns:
        for s in transport_df[transport_stage_col].dropna():
            s_clean = str(s).strip()
            if s_clean and s_clean not in all_stages:
                all_stages.append(s_clean)

    if not all_stages:
        all_stages = ["Manufacturing"]

    processes: list[Process] = []

    for stage_name in all_stages:
        clean_stage_id = re.sub(r"[^a-zA-Z0-9_]", "_", stage_name.lower())
        proc_id = f"{product_id}_{clean_stage_id}"
        proc_name = f"{product_name} [{stage_name}]"

        exchanges: list[Exchange] = []

        # 1. Inputs for this stage
        if not inputs_df.empty and "Stage" in inputs_df.columns:
            stage_inputs = inputs_df[inputs_df["Stage"].astype(str).str.strip() == stage_name]
            for _, row in stage_inputs.iterrows():
                flow = str(row.get("Input Flow Name", "")).strip()
                amt = float(row.get("Amount", 0.0) or 0.0)
                unit = str(row.get("Unit", "kg")).strip() or "kg"
                if flow and amt > 0:
                    exchanges.append(
                        Exchange(
                            flow_name=flow,
                            exchange_type="input",
                            amount=amt,
                            unit=unit,
                        )
                    )

        # 2. Direct emissions for this stage
        if not emissions_df.empty and "Stage" in emissions_df.columns:
            stage_emissions = emissions_df[emissions_df["Stage"].astype(str).str.strip() == stage_name]
            for _, row in stage_emissions.iterrows():
                flow = str(row.get("Emission Flow Name", "")).strip()
                amt = float(row.get("Amount", 0.0) or 0.0)
                unit = str(row.get("Unit", "kg")).strip() or "kg"
                if flow and amt > 0:
                    exchanges.append(
                        Exchange(
                            flow_name=flow,
                            exchange_type="output",
                            amount=amt,
                            unit=unit,
                        )
                    )

        # 3. Transportation for this stage
        transportation: list[Transportation] = []
        if not transport_df.empty and transport_stage_col in transport_df.columns:
            stage_trans = transport_df[transport_df[transport_stage_col].astype(str).str.strip() == stage_name]
            for _, row in stage_trans.iterrows():
                mode = str(row.get("Transport Mode", "truck")).strip().lower() or "truck"
                dist = float(row.get("Distance (km)", 0.0) or 0.0)
                mass = float(row.get("Cargo Mass (kg)", 1.0) or 1.0)
                if dist > 0:
                    transportation.append(
                        Transportation(
                            transport_mode=mode,
                            distance=dist,
                            distance_unit="km",
                            transported_mass=mass,
                            mass_unit="kg",
                        )
                    )

        processes.append(
            Process(
                process_id=proc_id,
                process_name=proc_name,
                stage=stage_name,
                exchanges=exchanges,
                transportation=transportation,
            )
        )

    return Product(
        product_id=product_id,
        product_name=product_name,
        functional_unit_amount=fu_amount,
        functional_unit=fu_unit,
        processes=processes,
    )


# --------------------------------------------------
# 3. Session State & Disk Persistence Initialization
# --------------------------------------------------

SAVED_PRODUCTS_FILE = "saved_products.json"

if "structured_products" not in st.session_state:
    loaded_disk_prods = load_products_from_json(SAVED_PRODUCTS_FILE)
    if loaded_disk_prods:
        st.session_state.structured_products = loaded_disk_prods
    else:
        sample_prod = build_product_from_tables(
            product_id="broom_001",
            product_name="Plastic Broom",
            fu_amount=1.0,
            fu_unit="unit",
            inputs_df=get_default_inputs_df(),
            emissions_df=get_default_emissions_df(),
            transport_df=get_default_transport_df(),
        )
        st.session_state.structured_products = [sample_prod]
        save_products_to_json([sample_prod], SAVED_PRODUCTS_FILE)

if "lca_results" not in st.session_state:
    st.session_state.lca_results = {}

if "selected_lca_prod_id" not in st.session_state:
    st.session_state.selected_lca_prod_id = (
        st.session_state.structured_products[0].product_id
        if st.session_state.structured_products
        else "broom_001"
    )

# Builder Form State
if "form_product_id" not in st.session_state:
    st.session_state.form_product_id = "broom_001"

if "form_product_name" not in st.session_state:
    st.session_state.form_product_name = "Plastic Broom"

if "form_fu_amount" not in st.session_state:
    st.session_state.form_fu_amount = 1.0

if "form_fu_unit" not in st.session_state:
    st.session_state.form_fu_unit = "unit"

if "form_inputs_df" not in st.session_state:
    st.session_state.form_inputs_df = get_default_inputs_df()

if "form_emissions_df" not in st.session_state:
    st.session_state.form_emissions_df = get_default_emissions_df()

if "form_transport_df" not in st.session_state:
    st.session_state.form_transport_df = get_default_transport_df()

if "imported_tables" not in st.session_state:
    st.session_state.imported_tables = {}

if "imported_file_name" not in st.session_state:
    st.session_state.imported_file_name = None

# --------------------------------------------------
# 4. Excel Template Generator
# --------------------------------------------------

TEMPLATE_COLUMNS = {
    "Products": ["product_id", "product_name", "functional_unit_amount", "functional_unit"],
    "Processes": ["process_id", "product_id", "process_name", "stage"],
    "Exchanges": ["process_id", "flow_name", "exchange_type", "amount", "unit"],
    "Transportation": ["process_id", "transport_mode", "distance", "distance_unit", "transported_mass", "mass_unit"],
}


def create_excel_template():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        examples = {
            "Products": [
                {
                    "product_id": "broom_001",
                    "product_name": "Plastic broom",
                    "functional_unit_amount": 1.0,
                    "functional_unit": "unit",
                }
            ],
            "Processes": [
                {
                    "process_id": "material_production",
                    "product_id": "broom_001",
                    "process_name": "Material compounding",
                    "stage": "Raw Materials",
                },
                {
                    "process_id": "broom_manufacturing",
                    "product_id": "broom_001",
                    "process_name": "Broom manufacturing",
                    "stage": "Manufacturing",
                },
            ],
            "Exchanges": [
                {
                    "process_id": "material_production",
                    "flow_name": "Plastic granules",
                    "exchange_type": "input",
                    "amount": 0.30,
                    "unit": "kg",
                },
                {
                    "process_id": "material_production",
                    "flow_name": "Broom bristles",
                    "exchange_type": "input",
                    "amount": 0.10,
                    "unit": "kg",
                },
                {
                    "process_id": "broom_manufacturing",
                    "flow_name": "Material compounding",
                    "exchange_type": "input",
                    "amount": 1.0,
                    "unit": "unit",
                },
                {
                    "process_id": "broom_manufacturing",
                    "flow_name": "Manufacturing electricity",
                    "exchange_type": "input",
                    "amount": 0.20,
                    "unit": "kWh",
                },
                {
                    "process_id": "broom_manufacturing",
                    "flow_name": "Carbon dioxide, fossil",
                    "exchange_type": "output",
                    "amount": 0.05,
                    "unit": "kg",
                },
            ],
            "Transportation": [
                {
                    "process_id": "broom_manufacturing",
                    "transport_mode": "truck",
                    "distance": 100,
                    "distance_unit": "km",
                    "transported_mass": 0.40,
                    "mass_unit": "kg",
                }
            ],
        }
        for sheet_name, cols in TEMPLATE_COLUMNS.items():
            pd.DataFrame(examples[sheet_name], columns=cols).to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()


# --------------------------------------------------
# 5. App Layout & Tabs
# --------------------------------------------------

builder_tab, lca_tab, excel_tab = st.tabs(
    [
        "📦 1. Product Builder (Create & Edit)",
        "🔬 2. LCA Calculation & Assessment",
        "📊 3. Excel Import & Export",
    ]
)

# ==================================================
# TAB 1: Simplified All-In-One Product Builder
# ==================================================

with builder_tab:
    st.header("Product Builder — All Inputs on One Screen")
    st.write(
        "Enter product details, materials & energy inputs, direct emissions, and transportation. "
        "Everything is defined right here in simple editable tables, then saved with one click."
    )

    # Preset / Action Buttons
    action_col1, action_col2, action_col3 = st.columns([2, 1, 1])
    with action_col2:
        if st.button("✨ Load Example (Plastic Broom)"):
            st.session_state.form_product_id = "broom_001"
            st.session_state.form_product_name = "Plastic Broom"
            st.session_state.form_fu_amount = 1.0
            st.session_state.form_fu_unit = "unit"
            st.session_state.form_inputs_df = get_default_inputs_df()
            st.session_state.form_emissions_df = get_default_emissions_df()
            st.session_state.form_transport_df = get_default_transport_df()
            st.rerun()

    with action_col3:
        if st.button("🧹 Clear / Blank Form"):
            st.session_state.form_product_id = "new_product_01"
            st.session_state.form_product_name = ""
            st.session_state.form_fu_amount = 1.0
            st.session_state.form_fu_unit = "unit"
            st.session_state.form_inputs_df = pd.DataFrame(
                columns=["Stage", "Input Flow Name", "Amount", "Unit"]
            )
            st.session_state.form_emissions_df = pd.DataFrame(
                columns=["Stage", "Emission Flow Name", "Amount", "Unit"]
            )
            st.session_state.form_transport_df = pd.DataFrame(
                columns=["Stage / Route", "Transport Mode", "Distance (km)", "Cargo Mass (kg)"]
            )
            st.rerun()

    st.markdown("---")

    # Step 1: Product Basics
    st.subheader("Step 1: Product Basics")
    b_col1, b_col2, b_col3, b_col4 = st.columns([2, 2, 1, 1])
    with b_col1:
        in_name = st.text_input(
            "Product Name",
            value=st.session_state.form_product_name,
            placeholder="e.g. Plastic Chair, Cotton T-Shirt",
        )
    with b_col2:
        in_id = st.text_input(
            "Product ID (unique code)",
            value=st.session_state.form_product_id,
            placeholder="e.g. chair_001",
        )
    with b_col3:
        in_fu_amt = st.number_input(
            "Functional Unit Amount",
            min_value=0.001,
            value=float(st.session_state.form_fu_amount),
            step=1.0,
        )
    with b_col4:
        units_list = ["unit", "kg", "piece", "litre", "m2", "kWh"]
        cur_unit = st.session_state.form_fu_unit if st.session_state.form_fu_unit in units_list else "unit"
        in_fu_unit = st.selectbox(
            "Unit",
            units_list,
            index=units_list.index(cur_unit),
        )

    st.markdown("---")

    # Step 2: Materials & Energy Inputs
    st.subheader("Step 2: Materials, Energy & Consumables (Inputs)")
    st.caption(
        "Add rows for every raw material, electricity, or fuel consumed. "
        "Tip: Common keywords like 'Electricity, grid average', 'Plastic granules', 'Diesel fuel', 'Steel', 'Aluminum', 'Glass', 'Cardboard', 'Water' automatically link to standard Brightway emission factors."
    )

    edited_inputs = st.data_editor(
        st.session_state.form_inputs_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Stage": st.column_config.SelectboxColumn(
                "Stage",
                options=DEFAULT_STAGES,
                required=True,
                default="Raw Materials",
            ),
            "Input Flow Name": st.column_config.TextColumn(
                "Input Flow / Material / Energy",
                required=True,
            ),
            "Amount": st.column_config.NumberColumn(
                "Amount",
                min_value=0.0,
                step=0.1,
                required=True,
                default=1.0,
            ),
            "Unit": st.column_config.TextColumn(
                "Unit",
                default="kg",
                required=True,
            ),
        },
        key="editor_inputs",
    )

    st.markdown("---")

    # Step 3: Direct Environmental Emissions (Outputs)
    st.subheader("Step 3: Direct Stack & Process Emissions (Outputs, Optional)")
    st.caption(
        "If this product or factory releases emissions directly into the air (e.g. burning natural gas or chemical reactions), add them here. Common flows: 'Carbon dioxide, fossil', 'Methane, fossil', 'Nitrous oxide'."
    )

    edited_emissions = st.data_editor(
        st.session_state.form_emissions_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Stage": st.column_config.SelectboxColumn(
                "Stage",
                options=DEFAULT_STAGES,
                required=True,
                default="Manufacturing",
            ),
            "Emission Flow Name": st.column_config.TextColumn(
                "Emission Flow Name",
                required=True,
                default="Carbon dioxide, fossil",
            ),
            "Amount": st.column_config.NumberColumn(
                "Amount",
                min_value=0.0,
                step=0.01,
                required=True,
                default=0.0,
            ),
            "Unit": st.column_config.TextColumn(
                "Unit",
                default="kg",
                required=True,
            ),
        },
        key="editor_emissions",
    )

    st.markdown("---")

    # Step 4: Transportation Logistics
    st.subheader("Step 4: Transportation Logistics (Optional)")
    st.caption(
        "Freight movement of raw materials or finished products. Specify mode (truck, train, ship, air), distance, and cargo weight."
    )

    edited_transport = st.data_editor(
        st.session_state.form_transport_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Stage / Route": st.column_config.SelectboxColumn(
                "Stage / Route",
                options=DEFAULT_STAGES,
                required=True,
                default="Manufacturing",
            ),
            "Transport Mode": st.column_config.SelectboxColumn(
                "Transport Mode",
                options=DEFAULT_MODES,
                required=True,
                default="truck",
            ),
            "Distance (km)": st.column_config.NumberColumn(
                "Distance (km)",
                min_value=0.0,
                step=10.0,
                required=True,
                default=100.0,
            ),
            "Cargo Mass (kg)": st.column_config.NumberColumn(
                "Cargo Mass (kg)",
                min_value=0.0,
                step=0.1,
                required=True,
                default=1.0,
            ),
        },
        key="editor_transport",
    )

    st.markdown("---")

    # Step 5: Save Product Button
    save_col1, save_col2 = st.columns([1, 3])
    with save_col1:
        save_clicked = st.button("💾 Save Product & Life Cycle", type="primary", use_container_width=True)

    if save_clicked:
        if not in_name.strip() or not in_id.strip():
            st.error("Please provide both a Product Name and Product ID.")
        else:
            compiled_prod = build_product_from_tables(
                product_id=in_id,
                product_name=in_name,
                fu_amount=in_fu_amt,
                fu_unit=in_fu_unit,
                inputs_df=edited_inputs,
                emissions_df=edited_emissions,
                transport_df=edited_transport,
            )

            # Check if updating or adding new
            existing_idx = next(
                (i for i, p in enumerate(st.session_state.structured_products) if p.product_id == compiled_prod.product_id),
                None,
            )

            if existing_idx is not None:
                st.session_state.structured_products[existing_idx] = compiled_prod
                action_word = "Updated"
            else:
                st.session_state.structured_products.append(compiled_prod)
                action_word = "Saved"

            # Set as target for calculation tab
            st.session_state.selected_lca_prod_id = compiled_prod.product_id

            # Update builder form memory
            st.session_state.form_product_id = compiled_prod.product_id
            st.session_state.form_product_name = compiled_prod.product_name
            st.session_state.form_fu_amount = compiled_prod.functional_unit_amount
            st.session_state.form_fu_unit = compiled_prod.functional_unit
            st.session_state.form_inputs_df = edited_inputs
            st.session_state.form_emissions_df = edited_emissions
            st.session_state.form_transport_df = edited_transport

            # Persist to disk permanently!
            save_products_to_json(st.session_state.structured_products, SAVED_PRODUCTS_FILE)

            total_inputs = sum(len([e for e in p.exchanges if e.exchange_type == 'input']) for p in compiled_prod.processes)
            total_trans = sum(len(p.transportation) for p in compiled_prod.processes)

            st.success(
                f"🎉 {action_word} '{compiled_prod.product_name}' successfully! "
                f"({len(compiled_prod.processes)} stages, {total_inputs} inputs, {total_trans} transport legs). "
                f"Saved to disk permanently. Now switch to the '🔬 2. LCA Calculation & Assessment' tab to compute its carbon footprint!"
            )

    # Saved Products Directory
    st.divider()
    st.subheader("Saved Products in Workspace (Persisted on Disk)")
    saved_prods = st.session_state.structured_products

    if not saved_prods:
        st.info("No saved products yet.")
    else:
        for p_idx, prod in enumerate(saved_prods):
            p_inputs = sum(len([e for e in proc.exchanges if e.exchange_type == 'input']) for proc in prod.processes)
            p_trans = sum(len(proc.transportation) for proc in prod.processes)

            with st.expander(
                f"📦 **{prod.product_name}** (`{prod.product_id}`) — Functional Unit: {prod.functional_unit_amount} {prod.functional_unit} | Stages: {len(prod.processes)}"
            ):
                sc1, sc2, sc3 = st.columns([2, 1, 1])
                with sc1:
                    st.write(f"• **Stages:** {', '.join(p.stage for p in prod.processes)}")
                    st.write(f"• **Inputs:** {p_inputs} flows | **Transport legs:** {p_trans}")
                with sc2:
                    if st.button("✏️ Load into Editor", key=f"load_{prod.product_id}_{p_idx}"):
                        inp_rows = []
                        emi_rows = []
                        tra_rows = []

                        for proc in prod.processes:
                            for exc in proc.exchanges:
                                if exc.exchange_type == "input":
                                    inp_rows.append({
                                        "Stage": proc.stage,
                                        "Input Flow Name": exc.flow_name,
                                        "Amount": exc.amount,
                                        "Unit": exc.unit,
                                    })
                                else:
                                    emi_rows.append({
                                        "Stage": proc.stage,
                                        "Emission Flow Name": exc.flow_name,
                                        "Amount": exc.amount,
                                        "Unit": exc.unit,
                                    })
                            for tr in proc.transportation:
                                tra_rows.append({
                                    "Stage / Route": proc.stage,
                                    "Transport Mode": tr.transport_mode,
                                    "Distance (km)": tr.distance,
                                    "Cargo Mass (kg)": tr.transported_mass or 1.0,
                                })

                        st.session_state.form_product_id = prod.product_id
                        st.session_state.form_product_name = prod.product_name
                        st.session_state.form_fu_amount = prod.functional_unit_amount
                        st.session_state.form_fu_unit = prod.functional_unit
                        st.session_state.form_inputs_df = pd.DataFrame(inp_rows) if inp_rows else pd.DataFrame(columns=["Stage", "Input Flow Name", "Amount", "Unit"])
                        st.session_state.form_emissions_df = pd.DataFrame(emi_rows) if emi_rows else pd.DataFrame(columns=["Stage", "Emission Flow Name", "Amount", "Unit"])
                        st.session_state.form_transport_df = pd.DataFrame(tra_rows) if tra_rows else pd.DataFrame(columns=["Stage / Route", "Transport Mode", "Distance (km)", "Cargo Mass (kg)"])
                        st.rerun()

                with sc3:
                    if st.button("🗑️ Delete Product", key=f"del_{prod.product_id}_{p_idx}"):
                        st.session_state.structured_products.pop(p_idx)
                        st.session_state.lca_results.pop(prod.product_id, None)
                        save_products_to_json(st.session_state.structured_products, SAVED_PRODUCTS_FILE)
                        st.rerun()

    # --------------------------------------------------
    # Expected Payload Inspector & JSON Exporter / Importer
    # --------------------------------------------------
    st.divider()
    with st.expander("📋 Inspect Expected JSON Payload & Schema (API / Developer View)"):
        st.markdown(
            "Here is the **exact JSON payload structure** that represents a full product life cycle model. "
            "You can copy this payload, use it in APIs, or save it as a backup."
        )

        if saved_prods:
            active_p = next(
                (p for p in saved_prods if p.product_id == st.session_state.form_product_id),
                saved_prods[0],
            )
            prod_payload = product_to_dict(active_p)
            st.markdown(f"**Current Payload for `{active_p.product_name}`:**")
            st.json(prod_payload)

            st.download_button(
                label=f"⬇️ Download {active_p.product_name} Payload (JSON)",
                data=json.dumps(prod_payload, indent=2),
                file_name=f"{active_p.product_id}_payload.json",
                mime="application/json",
                key="dl_payload_json",
            )

        st.markdown("#### Schema Definition & Required Keys")
        st.code(
            """{
  "product_id": "unique_product_code",
  "product_name": "Human-readable product name",
  "functional_unit_amount": 1.0,
  "functional_unit": "unit | kg | piece | litre | m2 | kWh",
  "processes": [
    {
      "process_id": "unique_process_code",
      "process_name": "Process title (e.g. Injection Molding)",
      "stage": "Raw Materials | Manufacturing | Packaging | Distribution & Transport | Use Phase | End of Life",
      "exchanges": [
        {
          "flow_name": "Plastic granules | Electricity, grid average | Carbon dioxide, fossil",
          "exchange_type": "input | output",
          "amount": 0.50,
          "unit": "kg | kWh | m3 | unit"
        }
      ],
      "transportation": [
        {
          "transport_mode": "truck | train | ship | air",
          "distance": 100.0,
          "distance_unit": "km",
          "transported_mass": 0.40,
          "mass_unit": "kg"
        }
      ]
    }
  ]
}""",
            language="json",
        )

        st.markdown("#### 📥 Paste & Load JSON Payload Directly")
        pasted_json = st.text_area(
            "Paste JSON payload here to import into workspace:",
            placeholder="{\n  \"product_id\": \"sample_01\",\n  \"product_name\": \"...\",\n  \"processes\": [...]\n}",
            height=120,
            key="pasted_payload_input",
        )
        if st.button("Load Pasted JSON into Workspace", type="secondary"):
            if not pasted_json.strip():
                st.warning("Please paste a JSON payload first.")
            else:
                try:
                    parsed_dict = json.loads(pasted_json)
                    imported_p = dict_to_product(parsed_dict)

                    existing_idx = next(
                        (i for i, p in enumerate(st.session_state.structured_products) if p.product_id == imported_p.product_id),
                        None,
                    )
                    if existing_idx is not None:
                        st.session_state.structured_products[existing_idx] = imported_p
                    else:
                        st.session_state.structured_products.append(imported_p)

                    save_products_to_json(st.session_state.structured_products, SAVED_PRODUCTS_FILE)
                    st.success(f"Successfully loaded '{imported_p.product_name}' from JSON payload!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse JSON payload: {e}")


# ==================================================
# TAB 2: LCA Calculation & Assessment
# ==================================================

with lca_tab:
    st.header("🔬 Brightway LCA Calculation & Assessment")
    st.write(
        "Select any saved product to run real-time matrix Life Cycle Assessment in Brightway. "
        "View cradle-to-grave carbon footprints, stage breakdowns, and process hotspots."
    )

    products = st.session_state.structured_products

    if not products:
        st.info("No products available. Please create or save a product in Tab 1 first.")
    else:
        prod_ids = [p.product_id for p in products]
        default_index = prod_ids.index(st.session_state.selected_lca_prod_id) if st.session_state.selected_lca_prod_id in prod_ids else 0

        c_col1, c_col2 = st.columns([2, 1])

        with c_col1:
            chosen_pid = st.selectbox(
                "Choose Product to Assess",
                prod_ids,
                index=default_index,
                format_func=lambda pid: next(p.product_name for p in products if p.product_id == pid) + f" [{pid}]",
            )
            target_product = next(p for p in products if p.product_id == chosen_pid)

        with c_col2:
            method_choice = st.selectbox(
                "Impact Method",
                [
                    "CML v4.8 GWP100 (Climate Change / Global Warming Potential)",
                    "Ecological Scarcity 2021 (Climate Change)",
                    "EF v3.0 (Climate Change)",
                    "Search All Brightway Methods...",
                ],
            )

        # Map choice to method tuple
        selected_method = DEFAULT_LCIA_METHOD
        if "Ecological Scarcity" in method_choice:
            selected_method = (
                "Ecological Scarcity 2021 no LT",
                "climate change no LT",
                "global warming potential (GWP100) no LT",
            )
        elif "EF v3.0" in method_choice:
            selected_method = (
                "EF v3.0 no LT",
                "climate change no LT",
                "global warming potential (GWP100) no LT",
            )
        elif "Search All" in method_choice:
            query = st.text_input("Filter methods (e.g. water, acidification, climate):", value="climate")
            matches = get_available_methods(query, limit=20)
            if matches:
                picked_idx = st.selectbox("Pick Method", range(len(matches)), format_func=lambda i: matches[i][1])
                selected_method = matches[picked_idx][0]
            else:
                st.warning("No methods matched query, defaulting to CML GWP100.")

        st.caption(f"Active Method: `{selected_method}`")

        # Demand setting
        calc_amt = st.number_input(
            f"Functional Unit Demand ({target_product.functional_unit})",
            min_value=0.001,
            value=float(target_product.functional_unit_amount),
            step=1.0,
        )

        if st.button("⚡ Run Life Cycle Assessment", type="primary"):
            target_product.functional_unit_amount = calc_amt

            with st.spinner("Compiling supply chain graph and solving LCA matrices in Brightway..."):
                try:
                    result: LCAResult = calculate_product_lca(
                        product=target_product,
                        method=selected_method,
                    )
                    st.session_state.lca_results[chosen_pid] = result
                    st.success("LCA calculation completed successfully!")
                except Exception as e:
                    st.error(f"LCA calculation failed: {e}")

        # Display Results
        current_result: LCAResult | None = st.session_state.lca_results.get(chosen_pid)

        if current_result:
            st.divider()
            st.subheader(f"Assessment Results: {current_result.product_name}")
            st.caption(
                f"Assessed on {current_result.functional_unit_amount} {current_result.functional_unit} | "
                f"Method: {current_result.method_name}"
            )

            # Top KPI metrics
            top_process = current_result.process_contributions[0] if current_result.process_contributions else None

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric(
                "Total Carbon Footprint",
                f"{current_result.total_score:.4f} {current_result.method_unit}",
            )
            kpi2.metric(
                "Transport Footprint",
                f"{current_result.transport_score:.4f} {current_result.method_unit}",
                f"{current_result.transport_percentage:.1f}% of total",
            )
            kpi3.metric(
                "Primary Hotspot",
                f"{top_process.process_name if top_process else 'N/A'}",
                f"{top_process.percentage:.1f}%" if top_process else "",
            )
            kpi4.metric(
                "Stages Analyzed",
                f"{len(current_result.stage_contributions)} Stages",
            )

            # 1. Stage Breakdown
            st.divider()
            st.subheader("1. Life Cycle Stage Breakdown (Cradle-to-Grave)")

            if current_result.stage_contributions:
                stage_df = pd.DataFrame(
                    [
                        {
                            "Stage": s.stage,
                            "Impact (kg CO2-eq)": round(s.score, 4),
                            "Share (%)": round(s.percentage, 1),
                        }
                        for s in current_result.stage_contributions
                    ]
                )

                col_chart, col_tbl = st.columns([3, 2])

                with col_chart:
                    chart = (
                        alt.Chart(stage_df)
                        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                        .encode(
                            x=alt.X("Impact (kg CO2-eq):Q", title="Impact (kg CO2-eq)"),
                            y=alt.Y("Stage:N", sort="-x", title=None),
                            color=alt.Color("Stage:N", legend=None),
                            tooltip=["Stage", "Impact (kg CO2-eq)", "Share (%)"],
                        )
                        .properties(height=240)
                    )
                    st.altair_chart(chart, use_container_width=True)

                with col_tbl:
                    st.dataframe(stage_df, use_container_width=True, hide_index=True)

            # 2. Process Hotspot Analysis
            st.divider()
            st.subheader("2. Process Hotspots & Supply Chain Contributors")

            if current_result.process_contributions:
                proc_df = pd.DataFrame(
                    [
                        {
                            "Process / Flow": p.process_name,
                            "Stage": p.stage,
                            "Impact (kg CO2-eq)": round(p.score, 4),
                            "Contribution (%)": round(p.percentage, 1),
                        }
                        for p in current_result.process_contributions
                    ]
                )
                st.dataframe(
                    proc_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Contribution (%)": st.column_config.ProgressColumn(
                            "Contribution (%)",
                            min_value=0,
                            max_value=100,
                            format="%.1f%%",
                        ),
                    },
                )

            # 3. Direct Elementary Emissions
            if current_result.flow_contributions:
                st.divider()
                st.subheader("3. Environmental Elementary Flows (Direct & Upstream)")
                flow_df = pd.DataFrame(
                    [
                        {
                            "Emission Flow": f.flow_name,
                            "Compartment": f.category,
                            "Inventory Amount": f"{f.amount:.4f} {f.unit}",
                            "Characterized Score": round(f.score, 4),
                            "Share (%)": round(f.percentage, 1),
                        }
                        for f in current_result.flow_contributions
                    ]
                )
                st.dataframe(flow_df, use_container_width=True, hide_index=True)

            # 4. Transportation Footprint
            if current_result.transport_contributions:
                st.divider()
                st.subheader("4. Logistics & Transportation Footprint")
                t_df = pd.DataFrame(
                    [
                        {
                            "Connected Process": t.process_name,
                            "Mode": t.mode.title(),
                            "Distance (km)": t.distance_km,
                            "Mass (kg)": t.mass_kg,
                            "Tonne-km (tkm)": round(t.tkm, 4),
                            "Transport Impact": round(t.score, 4),
                            "Share (%)": round(t.percentage, 1),
                        }
                        for t in current_result.transport_contributions
                    ]
                )
                st.dataframe(t_df, use_container_width=True, hide_index=True)

            if current_result.warnings:
                with st.expander("⚠️ Modeling Diagnostics & Notes"):
                    for w in current_result.warnings:
                        st.caption(f"• {w}")


# ==================================================
# TAB 3: Excel Import & Export
# ==================================================

with excel_tab:
    st.header("Bulk Import / Export via Excel")
    st.write(
        "Upload a multi-sheet `.xlsx` workbook containing full life-cycle data "
        "(`Products`, `Processes`, `Exchanges`, `Transportation`)."
    )

    st.download_button(
        label="⬇️ Download Excel Template (.xlsx)",
        data=create_excel_template(),
        file_name="product_lca_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    uploaded_file = st.file_uploader(
        "Choose an Excel workbook (.xlsx)",
        type=["xlsx"],
        help="Upload workbook with Products, Processes, Exchanges, and Transportation sheets.",
    )

    if uploaded_file is not None:
        try:
            workbook = pd.ExcelFile(uploaded_file)
            required_sheets = {"Products", "Processes", "Exchanges", "Transportation"}
            missing_sheets = required_sheets - set(workbook.sheet_names)

            if missing_sheets:
                st.error("Missing required sheets: " + ", ".join(sorted(missing_sheets)))
            else:
                tables = {name: pd.read_excel(workbook, sheet_name=name) for name in required_sheets}
                st.subheader("Workbook Preview")
                preview_sheet = st.selectbox("Choose sheet to preview", list(required_sheets))
                st.dataframe(tables[preview_sheet], use_container_width=True, hide_index=True)

                if st.button("🚀 Import All Products & Life Cycles", type="primary"):
                    uploaded_file.seek(0)
                    imported_prods = import_products_from_excel(uploaded_file)

                    existing_ids = {p.product_id for p in st.session_state.structured_products}
                    for imp_p in imported_prods:
                        if imp_p.product_id in existing_ids:
                            st.session_state.structured_products = [
                                p if p.product_id != imp_p.product_id else imp_p
                                for p in st.session_state.structured_products
                            ]
                        else:
                            st.session_state.structured_products.append(imp_p)

                    save_products_to_json(st.session_state.structured_products, SAVED_PRODUCTS_FILE)

                    st.session_state.imported_tables = tables
                    st.session_state.imported_file_name = uploaded_file.name

                    st.success(f"Successfully imported {len(imported_prods)} product(s) (persisted to disk)!")
                    st.info("Head over to '🔬 2. LCA Calculation & Assessment' to run Brightway on the imported data.")

        except Exception as error:
            st.error(f"Failed to read workbook: {error}")


# --------------------------------------------------
# 6. Footer
# --------------------------------------------------

st.divider()
st.caption(
    "Product LCA Studio | Dynamic Brightway Engine active. "
    "All calculations run live matrix inversions on your supply chain models."
)
