"""
Automated Integration Tests for Brightway FastAPI REST Service (api.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

import api
from api import app, STORAGE_FILE
from product_model import Product, load_products_from_json, save_products_to_json

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Brightway Product LCA API"
    assert data["status"] == "online"
    assert data["docs_url"] == "/docs"


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "brightway_project" in data
    assert "installed_databases" in data
    assert data["installed_methods_count"] > 0


def test_list_methods():
    response = client.get("/api/methods?search=climate&limit=5")
    assert response.status_code == 200
    methods = response.json()
    assert isinstance(methods, list)
    assert len(methods) > 0
    assert "method_tuple" in methods[0]
    assert "display_name" in methods[0]
    # Check that climate was in the query result
    assert any("climate" in m["display_name"].lower() for m in methods)


def test_product_crud_and_calculation():
    test_pid = "api_test_widget_99"

    # Sample product payload
    sample_payload = {
        "product_id": test_pid,
        "product_name": "API Test Eco Widget",
        "functional_unit_amount": 1.0,
        "functional_unit": "unit",
        "processes": [
            {
                "process_id": "widget_molding",
                "process_name": "Widget Injection Molding",
                "stage": "Manufacturing",
                "exchanges": [
                    {
                        "flow_name": "Plastic granules",
                        "exchange_type": "input",
                        "amount": 0.25,
                        "unit": "kg"
                    },
                    {
                        "flow_name": "Electricity, grid average",
                        "exchange_type": "input",
                        "amount": 0.5,
                        "unit": "kWh"
                    },
                    {
                        "flow_name": "Carbon dioxide, fossil",
                        "exchange_type": "output",
                        "amount": 0.05,
                        "unit": "kg"
                    }
                ],
                "transportation": [
                    {
                        "transport_mode": "truck",
                        "distance": 80.0,
                        "distance_unit": "km",
                        "transported_mass": 0.25,
                        "mass_unit": "kg"
                    }
                ]
            }
        ]
    }

    # 1. Create product via POST /api/products
    post_res = client.post("/api/products", json=sample_payload)
    assert post_res.status_code == 201, post_res.text
    post_data = post_res.json()
    assert post_data["status"] == "success"
    assert post_data["product_id"] == test_pid

    # 2. Get product via GET /api/products/{id}
    get_res = client.get(f"/api/products/{test_pid}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["product_id"] == test_pid
    assert retrieved["product_name"] == "API Test Eco Widget"
    assert len(retrieved["processes"]) == 1

    # 3. Calculate LCA on the saved product via POST /api/lca/calculate-saved/{id}
    calc_saved_res = client.post(f"/api/lca/calculate-saved/{test_pid}")
    assert calc_saved_res.status_code == 200, calc_saved_res.text
    saved_result = calc_saved_res.json()
    assert saved_result["product_id"] == test_pid
    assert saved_result["total_score"] > 0.0
    assert len(saved_result["process_contributions"]) >= 1
    assert any("Widget Injection Molding" in p["process_name"] for p in saved_result["process_contributions"])
    assert len(saved_result["stage_contributions"]) >= 1
    assert any("Manufacturing" in s["stage"] for s in saved_result["stage_contributions"])
    assert saved_result["transport_score"] > 0.0

    # 4. Calculate LCA directly from payload via POST /api/lca/calculate
    calc_res = client.post("/api/lca/calculate", json={"product": sample_payload})
    assert calc_res.status_code == 200, calc_res.text
    calc_result = calc_res.json()
    assert calc_result["product_id"] == test_pid
    assert abs(calc_result["total_score"] - saved_result["total_score"]) < 1e-6

    # 5. Delete product via DELETE /api/products/{id}
    del_res = client.delete(f"/api/products/{test_pid}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # 6. Verify 404 on deleted product
    get_deleted = client.get(f"/api/products/{test_pid}")
    assert get_deleted.status_code == 404


def test_invalid_product_validation():
    # Empty process_id should fail
    bad_payload = {
        "product_id": "bad_prod",
        "product_name": "Bad Product",
        "functional_unit_amount": 1.0,
        "processes": [
            {
                "process_id": "",  # invalid
                "process_name": "No ID Process",
                "stage": "Manufacturing",
                "exchanges": [],
                "transportation": []
            }
        ]
    }
    res = client.post("/api/products", json=bad_payload)
    assert res.status_code == 422


def test_senior_flat_refinery_payload():
    """Test that senior's flat refinery payload with mass allocation calculates seamlessly."""
    senior_payload = {
        "product": {
            "name": "Diesel, refinery gate",
            "functional_unit": "1 kg of diesel"
        },
        "allocation": {
            "method": "mass"
        },
        "inputs": [
            {
                "name": "Crude oil",
                "key": "crude_oil",
                "stage": "raw_material",
                "amount": 1.15,
                "unit": "kg"
            },
            {
                "name": "Process electricity",
                "key": "electricity_grid_sa",
                "stage": "manufacturing",
                "amount": 0.12,
                "unit": "kWh"
            },
            {
                "name": "Process heat",
                "key": "natural_gas_heat",
                "stage": "manufacturing",
                "amount": 0.8,
                "unit": "kWh"
            },
            {
                "name": "Hydrogen (hydrotreating)",
                "key": "hydrogen_smr",
                "stage": "manufacturing",
                "amount": 0.02,
                "unit": "kg"
            },
            {
                "name": "Crude oil transport",
                "key": "truck_16t",
                "stage": "transport",
                "mass": 1.15,
                "mass_unit": "kg",
                "distance_km": 300
            }
        ],
        "outputs": [
            {
                "type": "product",
                "name": "Diesel",
                "amount": 1.0,
                "unit": "kg",
                "price": 1.0
            },
            {
                "type": "co_product",
                "name": "Gasoline",
                "amount": 0.35,
                "unit": "kg",
                "price": 1.1
            },
            {
                "type": "co_product",
                "name": "LPG",
                "amount": 0.12,
                "unit": "kg",
                "price": 0.9
            },
            {
                "type": "emission",
                "name": "Flue gas CO2",
                "flow": "co2",
                "amount": 0.22,
                "unit": "kg"
            },
            {
                "type": "emission",
                "name": "Flue gas SO2",
                "flow": "so2",
                "amount": 0.0004,
                "unit": "kg"
            },
            {
                "type": "emission",
                "name": "Flue gas NOx",
                "flow": "nox",
                "amount": 0.0007,
                "unit": "kg"
            },
            {
                "type": "emission",
                "name": "Fugitive methane",
                "flow": "ch4",
                "amount": 0.0009,
                "unit": "kg"
            },
            {
                "type": "waste",
                "name": "Process wastewater",
                "key": "wastewater_treatment",
                "amount": 0.003,
                "unit": "m3"
            },
            {
                "type": "waste",
                "name": "Spent catalyst",
                "key": "hazardous_waste_incineration",
                "amount": 0.0008,
                "unit": "kg"
            }
        ],
        "metadata": {
            "product_code": "DSL-001",
            "plant": "Refinery A",
            "period": "2026-Q3",
            "request_ref": "REQ-12345"
        }
    }

    # 1. Calculate directly via /api/lca/calculate
    calc_res = client.post("/api/lca/calculate", json={"product": senior_payload})
    assert calc_res.status_code == 200, calc_res.text
    result = calc_res.json()
    assert result["product_id"] == "DSL-001"
    assert result["product_name"] == "Diesel, refinery gate"
    assert result["total_score"] > 0.0
    assert result["allocation_summary"] is not None
    assert result["allocation_summary"]["method"] == "mass"
    assert result["allocation_summary"]["allocation_percentage"] == 68.03
    assert len(result["process_contributions"]) > 0

    # 2. Save via /api/products
    save_res = client.post("/api/products", json=senior_payload)
    assert save_res.status_code == 201, save_res.text

    # 3. Calculate saved product
    calc_saved_res = client.post("/api/lca/calculate-saved/DSL-001")
    assert calc_saved_res.status_code == 200, calc_saved_res.text

    # 4. Clean up
    del_res = client.delete("/api/products/DSL-001")
    assert del_res.status_code == 200


def test_v1_reference_data():
    """Test /v1/units, /v1/flows, /v1/methods, /v1/activities."""
    # 1. Units
    units_res = client.get("/v1/units")
    assert units_res.status_code == 200
    units = units_res.json()
    assert isinstance(units, list)
    assert len(units) >= 10
    assert any(u["from_unit"] == "kg" for u in units)

    # 2. Flows
    flows_res = client.get("/v1/flows")
    assert flows_res.status_code == 200
    flows = flows_res.json()
    assert isinstance(flows, list)
    assert len(flows) >= 6
    assert any(f["code"] == "co2" for f in flows)

    # 3. Methods
    methods_res = client.get("/v1/methods")
    assert methods_res.status_code == 200
    methods = methods_res.json()
    assert isinstance(methods, list)
    assert len(methods) >= 2
    assert any(m["key"] == "gwp100" for m in methods)
    assert any(m["key"] == "acidification" for m in methods)

    # 4. Activities
    activities_res = client.get("/v1/activities")
    assert activities_res.status_code == 200
    activities = activities_res.json()
    assert isinstance(activities, list)
    assert len(activities) >= 13
    assert any(a["code"] == "crude_oil" for a in activities)


def test_v1_unit_and_activity_crud():
    """Test creating and deleting units and activities via /v1."""
    # Create custom unit
    new_unit = {
        "code": "test_ton_to_kg",
        "from_unit": "test_ton",
        "to_unit": "kg",
        "factor": 1000.0,
        "dimension": "mass",
    }
    c_unit_res = client.post("/v1/units", json=new_unit)
    assert c_unit_res.status_code == 200
    assert c_unit_res.json()["status"] == "success"

    # Delete custom unit
    d_unit_res = client.delete("/v1/units/test_ton_to_kg")
    assert d_unit_res.status_code == 200
    assert d_unit_res.json()["status"] == "success"

    # Create custom activity
    new_act = {
        "code": "test_biomass",
        "name": "Biomass pellets test",
        "unit": "kilogram",
        "location": "GLO",
        "emissions": {"co2": 0.02},
        "technosphere": {"crude_oil": 0.05},
    }
    c_act_res = client.post("/v1/activities", json=new_act)
    assert c_act_res.status_code == 200
    assert c_act_res.json()["status"] == "success"

    # Delete custom activity
    d_act_res = client.delete("/v1/activities/test_biomass")
    assert d_act_res.status_code == 200
    assert d_act_res.json()["status"] == "success"


def test_v1_lca_calculate_and_runs():
    """Test POST /v1/lca/calculate directly against pgAdmin target values."""
    senior_refinery_payload = {
        "product": {
            "name": "Diesel, refinery gate",
            "functional_unit": "1 kg of diesel"
        },
        "allocation": {
            "method": "mass"
        },
        "inputs": [
            {
                "name": "Crude oil",
                "key": "crude_oil",
                "stage": "raw_material",
                "amount": 1.15,
                "unit": "kg"
            },
            {
                "name": "Process electricity",
                "key": "electricity_grid_sa",
                "stage": "manufacturing",
                "amount": 0.12,
                "unit": "kWh"
            },
            {
                "name": "Process heat",
                "key": "natural_gas_heat",
                "stage": "manufacturing",
                "amount": 0.8,
                "unit": "kWh"
            },
            {
                "name": "Hydrogen (hydrotreating)",
                "key": "hydrogen_smr",
                "stage": "manufacturing",
                "amount": 0.02,
                "unit": "kg"
            },
            {
                "name": "Crude oil transport",
                "key": "truck_16t",
                "stage": "transport",
                "mass": 1.15,
                "mass_unit": "kg",
                "distance_km": 300
            }
        ],
        "outputs": [
            {
                "type": "product",
                "name": "Diesel",
                "amount": 1.0,
                "unit": "kg",
                "price": 1.0
            },
            {
                "type": "co_product",
                "name": "Gasoline",
                "amount": 0.35,
                "unit": "kg",
                "price": 1.1
            },
            {
                "type": "co_product",
                "name": "LPG",
                "amount": 0.12,
                "unit": "kg",
                "price": 0.9
            },
            {
                "type": "emission",
                "name": "Flue gas CO2",
                "flow": "co2",
                "amount": 0.22,
                "unit": "kg"
            },
            {
                "type": "emission",
                "name": "Flue gas SO2",
                "flow": "so2",
                "amount": 0.0004,
                "unit": "kg"
            },
            {
                "type": "emission",
                "name": "Flue gas NOx",
                "flow": "nox",
                "amount": 0.0007,
                "unit": "kg"
            },
            {
                "type": "emission",
                "name": "Fugitive methane",
                "flow": "ch4",
                "amount": 0.0009,
                "unit": "kg"
            },
            {
                "type": "waste",
                "name": "Process wastewater",
                "key": "wastewater_treatment",
                "amount": 0.003,
                "unit": "m3"
            },
            {
                "type": "waste",
                "name": "Spent catalyst",
                "key": "hazardous_waste_incineration",
                "amount": 0.0008,
                "unit": "kg"
            }
        ],
        "metadata": {
            "product_code": "DSL-001",
            "plant": "Refinery A",
            "period": "2026-Q3",
            "request_ref": "REQ-12345"
        }
    }

    res = client.post("/v1/lca/calculate", json=senior_refinery_payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "run_id" in data
    assert "summary" in data
    assert "gwp100" in data["summary"]
    assert "acidification" in data["summary"]

    # Exactly match pgAdmin values
    # gwp100: ~0.94224649
    # acidification: ~0.00141920
    assert abs(data["summary"]["gwp100"] - 0.94224649) < 1e-4
    assert abs(data["summary"]["acidification"] - 0.00141920) < 1e-5

    run_id = data["run_id"]

    # Verify run audit logging via GET /v1/runs and GET /v1/runs/{run_id}
    runs_res = client.get("/v1/runs")
    assert runs_res.status_code == 200
    runs = runs_res.json()
    assert any(r["run_id"] == run_id for r in runs)

    single_run = client.get(f"/v1/runs/{run_id}")
    assert single_run.status_code == 200
    r_data = single_run.json()
    assert r_data["run_id"] == run_id
    assert r_data["summary"]["gwp100"] == data["summary"]["gwp100"]


def test_v1_unit_conversion_auto_wiring():
    """Verify that inputs passed in different SI units (e.g. grams vs kg) automatically convert."""
    payload_grams = {
        "product": {"name": "Diesel, refinery gate", "functional_unit": "1 kg"},
        "allocation": {"method": "mass"},
        "inputs": [
            {"name": "Crude oil", "key": "crude_oil", "amount": 1150.0, "unit": "g"},  # 1150 grams = 1.15 kg
            {"name": "Process electricity", "key": "electricity_grid_sa", "amount": 120.0, "unit": "Wh"},  # 120 Wh = 0.12 kWh
            {"name": "Process heat", "key": "natural_gas_heat", "amount": 2.88, "unit": "MJ"},  # 2.88 MJ = 0.8 kWh
            {"name": "Hydrogen", "key": "hydrogen_smr", "amount": 20.0, "unit": "g"},  # 20 grams = 0.02 kg
            {"name": "Transport", "key": "truck_16t", "mass": 1150.0, "mass_unit": "g", "distance_km": 300}
        ],
        "outputs": [
            {"type": "product", "name": "Diesel", "amount": 1.0, "unit": "kg"},
            {"type": "co_product", "name": "Gasoline", "amount": 0.35, "unit": "kg"},
            {"type": "co_product", "name": "LPG", "amount": 0.12, "unit": "kg"},
            {"type": "emission", "flow": "co2", "amount": 220.0, "unit": "g"},  # 220 g = 0.22 kg
            {"type": "waste", "key": "wastewater_treatment", "amount": 3.0, "unit": "L"}  # 3 L = 0.003 m3
        ]
    }
    res = client.post("/v1/lca/calculate", json=payload_grams)
    assert res.status_code == 200, res.text
    data = res.json()
    assert abs(data["summary"]["gwp100"] - 0.9422) < 0.05
    assert data["allocation"]["allocation_percentage"] == 68.03


def test_v1_energy_allocation_and_midpoints():
    """Verify ISO 14044 Energy allocation by Net Calorific Value (LHV) and multi-method midpoints."""
    payload_energy = {
        "product": {"name": "Diesel, refinery gate", "functional_unit": "1 kg"},
        "allocation": {"method": "energy"},
        "inputs": [
            {"name": "Crude oil", "key": "crude_oil", "amount": 1.15, "unit": "kg"},
            {"name": "Process electricity", "key": "electricity_grid_sa", "amount": 0.12, "unit": "kWh"}
        ],
        "outputs": [
            {"type": "product", "name": "Diesel", "amount": 1.0, "unit": "kg", "lhv": 43.0},
            {"type": "co_product", "name": "Gasoline", "amount": 0.35, "unit": "kg", "lhv": 44.0},
            {"type": "co_product", "name": "LPG", "amount": 0.12, "unit": "kg", "lhv": 46.1}
        ]
    }
    res = client.post("/v1/lca/calculate", json=payload_energy)
    assert res.status_code == 200, res.text
    data = res.json()

    alloc = data["allocation"]
    assert alloc["method"] == "energy"
    assert abs(alloc["allocation_factor"] - 0.6725896) < 1e-4
    assert alloc["allocation_percentage"] == 67.26
    assert alloc["main_product_energy_mj"] == 43.0
    assert abs(alloc["total_system_energy_mj"] - 63.932) < 0.01

    # Check that all 6 midpoints are calculated
    summary = data["summary"]
    for expected_method in ["gwp100", "acidification", "eutrophication", "photochemical_ozone", "ozone_depletion", "abiotic_depletion_fossil"]:
        assert expected_method in summary, f"Missing method {expected_method} in summary"
        assert isinstance(summary[expected_method], (int, float))


def test_v1_database_version_and_matrix_hash():
    """Verify matrix fingerprint generation and /v1/database/version."""
    res = client.get("/v1/database/version")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "matrix_hash" in data
    assert data["matrix_hash"].startswith("sha256:")
    assert data["total_activities"] > 0
    assert data["total_flows"] > 0
    assert data["total_methods"] > 0
    assert data["total_units"] > 0

    # Verify /api/database/status also has matrix_hash
    legacy_res = client.get("/api/database/status")
    assert legacy_res.status_code == 200
    legacy_data = legacy_res.json()
    assert legacy_data["matrix_hash"] == data["matrix_hash"]


def test_v1_referential_integrity_and_cycles():
    """Verify that bad references and cycles are rejected with HTTP 400."""
    # 1. Non-existent technosphere activity
    bad_act_techno = {
        "code": "test_broken_techno",
        "name": "Broken Technosphere",
        "unit": "kg",
        "technosphere": {"non_existent_upstream_xyz": 1.5},
    }
    res1 = client.post("/v1/activities", json=bad_act_techno)
    assert res1.status_code == 400, res1.text
    assert "Technosphere inputs reference non-existent" in res1.json()["detail"]

    # 2. Non-existent emission flow
    bad_act_flow = {
        "code": "test_broken_flow",
        "name": "Broken Emission Flow",
        "unit": "kg",
        "emissions": {"non_existent_emission_abc": 0.5},
    }
    res2 = client.post("/v1/activities", json=bad_act_flow)
    assert res2.status_code == 400, res2.text
    assert "Direct emissions reference non-existent elementary flows" in res2.json()["detail"]

    # 3. Self-referencing activity
    self_ref_act = {
        "code": "test_self_ref",
        "name": "Self Referencing Act",
        "unit": "kg",
        "technosphere": {"test_self_ref": 1.0},
    }
    res3 = client.post("/v1/activities", json=self_ref_act)
    assert res3.status_code == 400, res3.text
    assert "cannot reference itself" in res3.json()["detail"]


def test_v1_dependency_delete_protection_and_cascade():
    """Verify that deleting an activity or flow required by downstream models is prevented unless cascade=True."""
    # Create upstream parent activity
    parent = {
        "code": "test_upstream_feedstock",
        "name": "Upstream Feedstock",
        "unit": "kg",
    }
    r1 = client.post("/v1/activities", json=parent)
    assert r1.status_code == 200

    # Create downstream child activity
    child = {
        "code": "test_downstream_product",
        "name": "Downstream Product",
        "unit": "kg",
        "technosphere": {"test_upstream_feedstock": 2.0},
    }
    r2 = client.post("/v1/activities", json=child)
    assert r2.status_code == 200

    # Attempting to delete upstream without cascade must fail with 400
    del_blocked = client.delete("/v1/activities/test_upstream_feedstock")
    assert del_blocked.status_code == 400, del_blocked.text
    assert "required by downstream activities" in del_blocked.json()["detail"]

    # Deleting child first succeeds
    del_child = client.delete("/v1/activities/test_downstream_product")
    assert del_child.status_code == 200

    # Now deleting upstream succeeds
    del_parent = client.delete("/v1/activities/test_upstream_feedstock")
    assert del_parent.status_code == 200

    # Flow deletion protection: attempt to delete 'co2' without cascade must fail
    del_co2 = client.delete("/v1/flows/co2")
    assert del_co2.status_code == 400
    assert "referenced by" in del_co2.json()["detail"]


def test_v1_flow_and_method_crud():
    """Verify CRUD endpoints for elementary flows and LCIA methods."""
    # 1. Flow CRUD
    new_flow = {
        "code": "test_cfc11",
        "name": "Trichlorofluoromethane (CFC-11)",
        "unit": "kilogram",
        "categories": "air",
        "flow_type": "emission",
    }
    f_res = client.post("/v1/flows", json=new_flow)
    assert f_res.status_code == 200, f_res.text

    # List flows to check existence
    flows = client.get("/v1/flows").json()
    assert any(f["code"] == "test_cfc11" for f in flows)

    # 2. Method CRUD
    new_method = {
        "key": "test_odp",
        "name": "Ozone Depletion Potential Test",
        "method_tuple": ["TEST", "ODP"],
        "unit": "kg CFC-11-Eq",
        "cfs": {"test_cfc11": 1.0},
    }
    m_res = client.post("/v1/methods", json=new_method)
    assert m_res.status_code == 200, m_res.text

    # List methods to check existence
    methods = client.get("/v1/methods").json()
    assert any(m["key"] == "test_odp" for m in methods)

    # Delete method first
    del_m = client.delete("/v1/methods/test_odp")
    assert del_m.status_code == 200
    assert del_m.json()["status"] == "success"

    # Delete flow
    del_f = client.delete("/v1/flows/test_cfc11")
    assert del_f.status_code == 200
    assert del_f.json()["status"] == "success"


def test_v1_multi_hop_graph_unit_conversion():
    """Verify graph BFS resolver across chained unit conversion definitions."""
    import db
    # Insert a 3-hop chained conversion into unit_conversion table:
    # node_a -> node_b (x 2.5)
    # node_b -> node_c (x 4.0)
    # Expected node_a -> node_c = 10.0
    client.post("/v1/units", json={"code": "hop_a_b", "from_unit": "node_a", "to_unit": "node_b", "factor": 2.5, "dimension": "test"})
    client.post("/v1/units", json={"code": "hop_b_c", "from_unit": "node_b", "to_unit": "node_c", "factor": 4.0, "dimension": "test"})

    try:
        factor_forward = db.resolve_conversion_graph("node_a", "node_c")
        assert factor_forward is not None
        assert abs(factor_forward - 10.0) < 1e-6

        # Inverse graph traversal: node_c -> node_a = 0.1
        factor_reverse = db.resolve_conversion_graph("node_c", "node_a")
        assert factor_reverse is not None
        assert abs(factor_reverse - 0.1) < 1e-6

        # Convert amount via convert_unit_db
        converted = db.convert_unit_db(5.0, "node_a", "node_c")
        assert abs(converted - 50.0) < 1e-6
    finally:
        client.delete("/v1/units/hop_a_b")
        client.delete("/v1/units/hop_b_c")


def test_security_status_and_auth_bypass():
    """Verify auth status endpoint and dev bypass behavior."""
    res = client.get("/v1/auth/status")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "security_enabled" in data
    assert "rate_limit_per_minute" in data
    assert "max_payload_bytes" in data

    # Verify endpoint works without credentials in dev mode
    v_res = client.get("/v1/auth/verify")
    assert v_res.status_code == 200
    assert v_res.json()["client"] == "development_bypass"


def test_security_api_key_enforcement():
    """Verify API key verification when security is enabled."""
    original_state = api.API_SECURITY_ENABLED
    try:
        api.API_SECURITY_ENABLED = True

        # Missing key -> 401
        res_missing = client.get("/v1/auth/verify")
        assert res_missing.status_code == 401, res_missing.text
        assert "Invalid or missing API key" in res_missing.json()["detail"]

        # Wrong key -> 401
        res_wrong = client.get("/v1/auth/verify", headers={"X-API-Key": "wrong-key-123"})
        assert res_wrong.status_code == 401

        # Valid X-API-Key -> 200
        res_valid_header = client.get("/v1/auth/verify", headers={"X-API-Key": api.API_KEY})
        assert res_valid_header.status_code == 200
        assert res_valid_header.json()["status"] == "authenticated"

        # Valid Bearer token -> 200
        res_valid_bearer = client.get("/v1/auth/verify", headers={"Authorization": f"Bearer {api.API_KEY}"})
        assert res_valid_bearer.status_code == 200
        assert res_valid_bearer.json()["status"] == "authenticated"
    finally:
        api.API_SECURITY_ENABLED = original_state


def test_rate_limiter_and_payload_guards():
    """Verify that excessive requests trigger HTTP 429 and oversized payloads trigger HTTP 413."""
    # 1. Test 413 Content Too Large
    oversized_res = client.post(
        "/v1/lca/calculate",
        json={"dummy": "payload"},
        headers={"Content-Length": str(20 * 1024 * 1024)},
    )
    assert oversized_res.status_code == 413, oversized_res.text
    assert "exceeds maximum allowed size" in oversized_res.json()["detail"]

    # 2. Test 429 Too Many Requests
    original_limit = api.rate_limiter.limit
    original_records = api.rate_limiter.records.copy()
    try:
        api.rate_limiter.limit = 2
        api.rate_limiter.records.clear()

        # Simple dummy payload for rate test
        simple_payload = {
            "product": {"name": "Test Rate Limit", "functional_unit": "1 kg"},
            "inputs": [{"key": "crude_oil", "amount": 1.0}],
            "outputs": [{"type": "product", "name": "Test Rate Limit", "amount": 1.0}]
        }

        # Request 1: OK
        r1 = client.post("/v1/lca/calculate", json=simple_payload)
        assert r1.status_code == 200

        # Request 2: OK
        r2 = client.post("/v1/lca/calculate", json=simple_payload)
        assert r2.status_code == 200

        # Request 3: Exceeds rate limit -> 429
        r3 = client.post("/v1/lca/calculate", json=simple_payload)
        assert r3.status_code == 429, r3.text
        assert "Retry-After" in r3.headers
        assert "Too many LCA calculation requests" in r3.json()["detail"]
    finally:
        api.rate_limiter.limit = original_limit
        api.rate_limiter.records = original_records


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING FASTAPI REST API INTEGRATION TESTS")
    print("=" * 60)

    tests = [
        ("Root Endpoint", test_root_endpoint),
        ("Health Check", test_health_check),
        ("List LCIA Methods", test_list_methods),
        ("Product CRUD & LCA Calculation", test_product_crud_and_calculation),
        ("Invalid Payload Validation", test_invalid_product_validation),
        ("Senior Flat Refinery Payload & Allocation", test_senior_flat_refinery_payload),
        ("V1 Reference Data (Units, Flows, Methods, Activities)", test_v1_reference_data),
        ("V1 Unit & Activity CRUD", test_v1_unit_and_activity_crud),
        ("V1 LCA Calculate & Runs Audit Log", test_v1_lca_calculate_and_runs),
        ("V1 Unit Conversion Auto-Wiring", test_v1_unit_conversion_auto_wiring),
        ("V1 ISO 14044 Energy Allocation & Midpoints", test_v1_energy_allocation_and_midpoints),
        ("V1 Database Version & Matrix Hash Fingerprint", test_v1_database_version_and_matrix_hash),
        ("V1 Referential Integrity & Self-Reference Prevention", test_v1_referential_integrity_and_cycles),
        ("V1 Dependency Deletion Protection & Cascade", test_v1_dependency_delete_protection_and_cascade),
        ("V1 Flow & Method CRUD with Incremental Sync", test_v1_flow_and_method_crud),
        ("V1 Multi-Hop Graph Unit Conversion", test_v1_multi_hop_graph_unit_conversion),
        ("Security Status & Auth Dev Bypass", test_security_status_and_auth_bypass),
        ("Security API Key Enforcement & Bearer Token", test_security_api_key_enforcement),
        ("Rate Limiter (429) & Payload Guards (413)", test_rate_limiter_and_payload_guards),
    ]

    passed = 0
    for name, func in tests:
        try:
            print(f"Testing {name}...", end=" ", flush=True)
            func()
            print("PASSED [OK]", flush=True)
            passed += 1
        except Exception as e:
            print(f"FAILED [X]\nError: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 60)
    print(f"TEST RESULTS: {passed}/{len(tests)} PASSED")
    print("=" * 60)
    if passed == len(tests):
        exit(0)
    else:
        exit(1)

