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
    ]

    passed = 0
    for name, func in tests:
        try:
            print(f"Testing {name}...", end=" ")
            func()
            print("PASSED [OK]")
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

