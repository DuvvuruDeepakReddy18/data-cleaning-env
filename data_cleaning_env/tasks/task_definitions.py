"""
Task definitions for the Data Cleaning Environment.

Each task provides:
- dirty_data: The messy dataset the agent must clean (list of dicts)
- clean_data: The gold-standard clean version (list of dicts)
- columns: Column names
- description: Human-readable task description
- max_actions: Maximum allowed actions
- difficulty: easy / medium / hard
- issues: List of issue descriptions for reference
"""

import copy
from typing import Any


def _task_easy() -> dict[str, Any]:
    """Task 1 (Easy): Fix Customer Contact List.

    Issues: whitespace, capitalization, date formatting, typos in emails.
    10 rows, ~12 issues.
    """
    dirty_data = [
        {"name": "  john doe  ", "email": "john@example.com", "phone": "555-1234", "signup_date": "01/15/2024", "city": "new york"},
        {"name": "JANE SMITH", "email": "jane@example", "phone": "555-5678", "signup_date": "2024-02-20", "city": "Los Angeles"},
        {"name": "Bob Johnson", "email": "bob@example.com", "phone": "5551234567", "signup_date": "March 3, 2024", "city": "chicago"},
        {"name": "alice   williams", "email": "alice@example.com", "phone": "555-9012", "signup_date": "2024-04-10", "city": "Houston"},
        {"name": "Charlie Brown", "email": "charlie@example.com", "phone": "555-3456", "signup_date": "05/22/2024", "city": "PHOENIX"},
        {"name": " david lee", "email": "david@example.com", "phone": "555 7890", "signup_date": "2024-06-15", "city": "Philadelphia"},
        {"name": "Eva Martinez", "email": "eva@@example.com", "phone": "555-2345", "signup_date": "2024-07-01", "city": "san antonio"},
        {"name": "frank WILSON", "email": "frank@example.com", "phone": "555-6789", "signup_date": "Aug 18, 2024", "city": "San Diego"},
        {"name": "Grace Taylor", "email": "grace@example.com", "phone": "555-0123", "signup_date": "2024-09-30", "city": "dallas"},
        {"name": "  henry thomas ", "email": "henry@example.com", "phone": "555-4567", "signup_date": "10/05/2024", "city": "San Jose"},
    ]

    clean_data = [
        {"name": "John Doe", "email": "john@example.com", "phone": "555-1234", "signup_date": "2024-01-15", "city": "New York"},
        {"name": "Jane Smith", "email": "jane@example.com", "phone": "555-5678", "signup_date": "2024-02-20", "city": "Los Angeles"},
        {"name": "Bob Johnson", "email": "bob@example.com", "phone": "555-1234567", "signup_date": "2024-03-03", "city": "Chicago"},
        {"name": "Alice Williams", "email": "alice@example.com", "phone": "555-9012", "signup_date": "2024-04-10", "city": "Houston"},
        {"name": "Charlie Brown", "email": "charlie@example.com", "phone": "555-3456", "signup_date": "2024-05-22", "city": "Phoenix"},
        {"name": "David Lee", "email": "david@example.com", "phone": "555-7890", "signup_date": "2024-06-15", "city": "Philadelphia"},
        {"name": "Eva Martinez", "email": "eva@example.com", "phone": "555-2345", "signup_date": "2024-07-01", "city": "San Antonio"},
        {"name": "Frank Wilson", "email": "frank@example.com", "phone": "555-6789", "signup_date": "2024-08-18", "city": "San Diego"},
        {"name": "Grace Taylor", "email": "grace@example.com", "phone": "555-0123", "signup_date": "2024-09-30", "city": "Dallas"},
        {"name": "Henry Thomas", "email": "henry@example.com", "phone": "555-4567", "signup_date": "2024-10-05", "city": "San Jose"},
    ]

    issues = [
        "Row 0: name has leading/trailing whitespace and wrong case",
        "Row 0: signup_date uses MM/DD/YYYY instead of YYYY-MM-DD",
        "Row 0: city has wrong capitalization",
        "Row 1: name is ALL CAPS",
        "Row 1: email is missing TLD (.com)",
        "Row 2: phone missing dashes (raw digits)",
        "Row 2: signup_date uses 'Month D, YYYY' format",
        "Row 2: city has wrong capitalization",
        "Row 3: name has inconsistent spacing",
        "Row 4: signup_date uses MM/DD/YYYY format",
        "Row 4: city is ALL CAPS",
        "Row 5: name has leading whitespace",
        "Row 5: phone uses spaces instead of dashes",
        "Row 6: email has double @@ symbol",
        "Row 6: city has wrong capitalization",
        "Row 7: name has mixed case (frank WILSON)",
        "Row 7: signup_date uses 'Mon DD, YYYY' format",
        "Row 8: city has wrong capitalization",
        "Row 9: name has leading/trailing whitespace",
        "Row 9: signup_date uses MM/DD/YYYY format",
    ]

    return {
        "task_id": "easy_customer_contacts",
        "description": (
            "Clean a customer contact list with 10 entries. Fix issues including: "
            "inconsistent name capitalization, extra whitespace, non-standard date formats "
            "(standardize to YYYY-MM-DD), malformed emails, inconsistent phone formatting, "
            "and city name capitalization. Each field should be properly formatted."
        ),
        "dirty_data": dirty_data,
        "clean_data": clean_data,
        "columns": ["name", "email", "phone", "signup_date", "city"],
        "max_actions": 40,
        "difficulty": "easy",
        "issues": issues,
    }


def _task_medium() -> dict[str, Any]:
    """Task 2 (Medium): Clean Product Inventory.

    Issues: missing values, type mismatches, inconsistent categories,
    invalid values, unit inconsistencies.
    15 rows, ~22 issues.
    """
    dirty_data = [
        {"product_name": "Wireless Mouse", "category": "Electronics", "price": "29.99", "stock": "150", "weight_kg": "0.1", "rating": "4.5"},
        {"product_name": "USB Cable", "category": "electronics", "price": "9.99", "stock": "500", "weight_kg": "0.05", "rating": "4.0"},
        {"product_name": "Laptop Stand", "category": "Electr.", "price": "forty-five", "stock": "75", "weight_kg": "1.2", "rating": "4.8"},
        {"product_name": "Notebook", "category": "Stationery", "price": "3.50", "stock": "-10", "weight_kg": "0.2", "rating": "3.5"},
        {"product_name": "Desk Lamp", "category": "Home & Office", "price": "24.99", "stock": "", "weight_kg": "0.8", "rating": "4.2"},
        {"product_name": "", "category": "Electronics", "price": "199.99", "stock": "30", "weight_kg": "0.3", "rating": "4.7"},
        {"product_name": "Mechanical Keyboard", "category": "ELECTRONICS", "price": "89.99", "stock": "200", "weight_kg": "0.9", "rating": "11.0"},
        {"product_name": "Monitor Arm", "category": "Home & Office", "price": "35.00", "stock": "60", "weight_kg": "2500g", "rating": "4.1"},
        {"product_name": "Webcam HD", "category": "Electronicss", "price": "49.99", "stock": "100", "weight_kg": "0.15", "rating": ""},
        {"product_name": "Sticky Notes", "category": "stationery", "price": "2.99", "stock": "1000", "weight_kg": "0.1", "rating": "4.0"},
        {"product_name": "Ergonomic Chair", "category": "Home & Office", "price": "$299.00", "stock": "25", "weight_kg": "15.0", "rating": "4.9"},
        {"product_name": "USB Hub", "category": "Electronics", "price": "19.99", "stock": "N/A", "weight_kg": "0.12", "rating": "3.8"},
        {"product_name": "Whiteboard", "category": "Home & office", "price": "45.00", "stock": "40", "weight_kg": "3.5", "rating": "4.3"},
        {"product_name": "Pen Set", "category": "Stationery", "price": "12.99", "stock": "300", "weight_kg": "0.15", "rating": "-1.0"},
        {"product_name": "Power Strip", "category": "Electrnics", "price": "15.99", "stock": "180", "weight_kg": "0.4", "rating": "4.0"},
    ]

    clean_data = [
        {"product_name": "Wireless Mouse", "category": "Electronics", "price": "29.99", "stock": "150", "weight_kg": "0.1", "rating": "4.5"},
        {"product_name": "USB Cable", "category": "Electronics", "price": "9.99", "stock": "500", "weight_kg": "0.05", "rating": "4.0"},
        {"product_name": "Laptop Stand", "category": "Electronics", "price": "45.00", "stock": "75", "weight_kg": "1.2", "rating": "4.8"},
        {"product_name": "Notebook", "category": "Stationery", "price": "3.50", "stock": "0", "weight_kg": "0.2", "rating": "3.5"},
        {"product_name": "Desk Lamp", "category": "Home & Office", "price": "24.99", "stock": "0", "weight_kg": "0.8", "rating": "4.2"},
        {"product_name": "Unknown Product", "category": "Electronics", "price": "199.99", "stock": "30", "weight_kg": "0.3", "rating": "4.7"},
        {"product_name": "Mechanical Keyboard", "category": "Electronics", "price": "89.99", "stock": "200", "weight_kg": "0.9", "rating": "5.0"},
        {"product_name": "Monitor Arm", "category": "Home & Office", "price": "35.00", "stock": "60", "weight_kg": "2.5", "rating": "4.1"},
        {"product_name": "Webcam HD", "category": "Electronics", "price": "49.99", "stock": "100", "weight_kg": "0.15", "rating": "0.0"},
        {"product_name": "Sticky Notes", "category": "Stationery", "price": "2.99", "stock": "1000", "weight_kg": "0.1", "rating": "4.0"},
        {"product_name": "Ergonomic Chair", "category": "Home & Office", "price": "299.00", "stock": "25", "weight_kg": "15.0", "rating": "4.9"},
        {"product_name": "USB Hub", "category": "Electronics", "price": "19.99", "stock": "0", "weight_kg": "0.12", "rating": "3.8"},
        {"product_name": "Whiteboard", "category": "Home & Office", "price": "45.00", "stock": "40", "weight_kg": "3.5", "rating": "4.3"},
        {"product_name": "Pen Set", "category": "Stationery", "price": "12.99", "stock": "300", "weight_kg": "0.15", "rating": "0.0"},
        {"product_name": "Power Strip", "category": "Electronics", "price": "15.99", "stock": "180", "weight_kg": "0.4", "rating": "4.0"},
    ]

    issues = [
        "Row 1: category 'electronics' should be 'Electronics'",
        "Row 2: category 'Electr.' is abbreviated, should be 'Electronics'",
        "Row 2: price 'forty-five' is text, should be '45.00'",
        "Row 3: stock '-10' is negative, should be '0'",
        "Row 4: stock is empty/missing, should be '0'",
        "Row 5: product_name is empty, should be 'Unknown Product'",
        "Row 6: category 'ELECTRONICS' wrong case, should be 'Electronics'",
        "Row 6: rating '11.0' exceeds max 5.0, should be capped at '5.0'",
        "Row 7: weight_kg '2500g' has unit suffix and wrong value, should be '2.5'",
        "Row 8: category 'Electronicss' is misspelled, should be 'Electronics'",
        "Row 8: rating is empty/missing, should be '0.0'",
        "Row 9: category 'stationery' wrong case, should be 'Stationery'",
        "Row 10: price '$299.00' has currency symbol, should be '299.00'",
        "Row 11: stock 'N/A' is non-numeric, should be '0'",
        "Row 12: category 'Home & office' wrong case, should be 'Home & Office'",
        "Row 13: rating '-1.0' is negative, should be '0.0'",
        "Row 14: category 'Electrnics' is misspelled, should be 'Electronics'",
    ]

    return {
        "task_id": "medium_product_inventory",
        "description": (
            "Clean a product inventory dataset with 15 entries. Fix issues including: "
            "inconsistent category names (standardize to 'Electronics', 'Stationery', "
            "'Home & Office'), prices with text or currency symbols (should be plain numbers), "
            "negative or missing stock values (set to 0), weight with unit suffixes "
            "(should be plain numbers in kg), ratings outside 0-5 range, missing product names "
            "(set to 'Unknown Product'), and empty/non-numeric fields."
        ),
        "dirty_data": dirty_data,
        "clean_data": clean_data,
        "columns": ["product_name", "category", "price", "stock", "weight_kg", "rating"],
        "max_actions": 60,
        "difficulty": "medium",
        "issues": issues,
    }


def _task_hard() -> dict[str, Any]:
    """Task 3 (Hard): Reconcile Sales Records.

    Issues: duplicates, logical inconsistencies (total != qty * price),
    date ordering violations, referential integrity, format issues,
    cross-field validation.
    20 rows, ~28 issues including rows to delete.
    """
    dirty_data = [
        {"order_id": "ORD-001", "customer": "Acme Corp", "product": "Widget A", "quantity": "10", "unit_price": "25.00", "total": "250.00", "order_date": "2024-01-15", "ship_date": "2024-01-18", "status": "Shipped"},
        {"order_id": "ORD-002", "customer": "Beta LLC", "product": "Widget B", "quantity": "5", "unit_price": "40.00", "total": "200.00", "order_date": "2024-01-20", "ship_date": "2024-01-22", "status": "shipped"},
        {"order_id": "ORD-002", "customer": "Beta LLC", "product": "Widget B", "quantity": "5", "unit_price": "40.00", "total": "200.50", "order_date": "2024-01-20", "ship_date": "2024-01-22", "status": "Shipped"},
        {"order_id": "ORD-003", "customer": "Gamma Inc", "product": "Gadget X", "quantity": "3", "unit_price": "100.00", "total": "250.00", "order_date": "2024-02-01", "ship_date": "2024-01-28", "status": "Shipped"},
        {"order_id": "ORD-004", "customer": "  delta co  ", "product": "Widget A", "quantity": "20", "unit_price": "25.00", "total": "500.00", "order_date": "2024-02-10", "ship_date": "2024-02-14", "status": "Delivered"},
        {"order_id": "ORD-005", "customer": "Acme Corp", "product": "Gadget Y", "quantity": "0", "unit_price": "75.00", "total": "75.00", "order_date": "2024-02-15", "ship_date": "", "status": "Pending"},
        {"order_id": "ORD-006", "customer": "Epsilon Ltd", "product": "Widget C", "quantity": "8", "unit_price": "30.00", "total": "240.00", "order_date": "02/28/2024", "ship_date": "2024-03-02", "status": "Shipped"},
        {"order_id": "ORD-007", "customer": "Beta LLC", "product": "Gadget X", "quantity": "2", "unit_price": "100.00", "total": "200.00", "order_date": "2024-03-05", "ship_date": "2024-03-08", "status": "DELIVERED"},
        {"order_id": "ORD-008", "customer": "Zeta Group", "product": "Widget B", "quantity": "-3", "unit_price": "40.00", "total": "-120.00", "order_date": "2024-03-10", "ship_date": "2024-03-12", "status": "Cancelled"},
        {"order_id": "ORD-009", "customer": "Acme Corp", "product": "widget a", "quantity": "15", "unit_price": "25.00", "total": "375.00", "order_date": "2024-03-15", "ship_date": "2024-03-18", "status": "Shipped"},
        {"order_id": "ORD-010", "customer": "Gamma Inc", "product": "Gadget Z", "quantity": "6", "unit_price": "50.00", "total": "300.00", "order_date": "2024-03-20", "ship_date": "2024-03-25", "status": "Shipped"},
        {"order_id": "", "customer": "Theta Corp", "product": "Widget A", "quantity": "4", "unit_price": "25.00", "total": "100.00", "order_date": "2024-03-22", "ship_date": "2024-03-26", "status": "Pending"},
        {"order_id": "ORD-012", "customer": "Acme Corp", "product": "Gadget X", "quantity": "7", "unit_price": "100.00", "total": "700.00", "order_date": "2024-04-01", "ship_date": "2024-04-05", "status": "Shipped"},
        {"order_id": "ORD-013", "customer": "Beta LLC", "product": "Widget C", "quantity": "10", "unit_price": "thirty", "total": "300.00", "order_date": "2024-04-10", "ship_date": "2024-04-12", "status": "Delivered"},
        {"order_id": "ORD-014", "customer": "Gamma Inc", "product": "Gadget Y", "quantity": "1", "unit_price": "75.00", "total": "75.00", "order_date": "2024-04-15", "ship_date": "2024-04-18", "status": "Shpped"},
        {"order_id": "ORD-010", "customer": "Gamma Inc", "product": "Gadget Z", "quantity": "6", "unit_price": "50.00", "total": "300.00", "order_date": "2024-03-20", "ship_date": "2024-03-25", "status": "Shipped"},
        {"order_id": "ORD-015", "customer": "Epsilon Ltd", "product": "Widget A", "quantity": "12", "unit_price": "25.00", "total": "290.00", "order_date": "2024-05-01", "ship_date": "2024-05-04", "status": "Delivered"},
        {"order_id": "ORD-016", "customer": "ACME CORP", "product": "Gadget X", "quantity": "3", "unit_price": "100.00", "total": "300.00", "order_date": "2024-05-10", "ship_date": "2024-05-08", "status": "Shipped"},
        {"order_id": "ORD-017", "customer": "Delta Co", "product": "Widget B", "quantity": "9", "unit_price": "40.00", "total": "360.00", "order_date": "2024-05-15", "ship_date": "2024-05-19", "status": "Delivered"},
        {"order_id": "ORD-018", "customer": "Beta LLC", "product": "Gadget Y", "quantity": "2", "unit_price": "75.00", "total": "150.00", "order_date": "2024-05-20", "ship_date": "2024-05-23", "status": "Pending"},
    ]

    # Clean version: duplicates removed (rows 2, 15), issues fixed
    clean_data = [
        {"order_id": "ORD-001", "customer": "Acme Corp", "product": "Widget A", "quantity": "10", "unit_price": "25.00", "total": "250.00", "order_date": "2024-01-15", "ship_date": "2024-01-18", "status": "Shipped"},
        {"order_id": "ORD-002", "customer": "Beta LLC", "product": "Widget B", "quantity": "5", "unit_price": "40.00", "total": "200.00", "order_date": "2024-01-20", "ship_date": "2024-01-22", "status": "Shipped"},
        {"order_id": "ORD-003", "customer": "Gamma Inc", "product": "Gadget X", "quantity": "3", "unit_price": "100.00", "total": "300.00", "order_date": "2024-02-01", "ship_date": "2024-02-04", "status": "Shipped"},
        {"order_id": "ORD-004", "customer": "Delta Co", "product": "Widget A", "quantity": "20", "unit_price": "25.00", "total": "500.00", "order_date": "2024-02-10", "ship_date": "2024-02-14", "status": "Delivered"},
        {"order_id": "ORD-005", "customer": "Acme Corp", "product": "Gadget Y", "quantity": "1", "unit_price": "75.00", "total": "75.00", "order_date": "2024-02-15", "ship_date": "", "status": "Pending"},
        {"order_id": "ORD-006", "customer": "Epsilon Ltd", "product": "Widget C", "quantity": "8", "unit_price": "30.00", "total": "240.00", "order_date": "2024-02-28", "ship_date": "2024-03-02", "status": "Shipped"},
        {"order_id": "ORD-007", "customer": "Beta LLC", "product": "Gadget X", "quantity": "2", "unit_price": "100.00", "total": "200.00", "order_date": "2024-03-05", "ship_date": "2024-03-08", "status": "Delivered"},
        {"order_id": "ORD-008", "customer": "Zeta Group", "product": "Widget B", "quantity": "3", "unit_price": "40.00", "total": "120.00", "order_date": "2024-03-10", "ship_date": "2024-03-12", "status": "Cancelled"},
        {"order_id": "ORD-009", "customer": "Acme Corp", "product": "Widget A", "quantity": "15", "unit_price": "25.00", "total": "375.00", "order_date": "2024-03-15", "ship_date": "2024-03-18", "status": "Shipped"},
        {"order_id": "ORD-010", "customer": "Gamma Inc", "product": "Gadget Z", "quantity": "6", "unit_price": "50.00", "total": "300.00", "order_date": "2024-03-20", "ship_date": "2024-03-25", "status": "Shipped"},
        {"order_id": "ORD-011", "customer": "Theta Corp", "product": "Widget A", "quantity": "4", "unit_price": "25.00", "total": "100.00", "order_date": "2024-03-22", "ship_date": "2024-03-26", "status": "Pending"},
        {"order_id": "ORD-012", "customer": "Acme Corp", "product": "Gadget X", "quantity": "7", "unit_price": "100.00", "total": "700.00", "order_date": "2024-04-01", "ship_date": "2024-04-05", "status": "Shipped"},
        {"order_id": "ORD-013", "customer": "Beta LLC", "product": "Widget C", "quantity": "10", "unit_price": "30.00", "total": "300.00", "order_date": "2024-04-10", "ship_date": "2024-04-12", "status": "Delivered"},
        {"order_id": "ORD-014", "customer": "Gamma Inc", "product": "Gadget Y", "quantity": "1", "unit_price": "75.00", "total": "75.00", "order_date": "2024-04-15", "ship_date": "2024-04-18", "status": "Shipped"},
        {"order_id": "ORD-015", "customer": "Epsilon Ltd", "product": "Widget A", "quantity": "12", "unit_price": "25.00", "total": "300.00", "order_date": "2024-05-01", "ship_date": "2024-05-04", "status": "Delivered"},
        {"order_id": "ORD-016", "customer": "Acme Corp", "product": "Gadget X", "quantity": "3", "unit_price": "100.00", "total": "300.00", "order_date": "2024-05-10", "ship_date": "2024-05-13", "status": "Shipped"},
        {"order_id": "ORD-017", "customer": "Delta Co", "product": "Widget B", "quantity": "9", "unit_price": "40.00", "total": "360.00", "order_date": "2024-05-15", "ship_date": "2024-05-19", "status": "Delivered"},
        {"order_id": "ORD-018", "customer": "Beta LLC", "product": "Gadget Y", "quantity": "2", "unit_price": "75.00", "total": "150.00", "order_date": "2024-05-20", "ship_date": "2024-05-23", "status": "Pending"},
    ]

    issues = [
        "Row 1: status 'shipped' wrong case -> 'Shipped'",
        "Row 2: DUPLICATE of Row 1 (ORD-002), total differs (200.50 vs 200.00) -> delete row",
        "Row 3: total 250.00 != 3 * 100.00 = 300.00 -> fix total to '300.00'",
        "Row 3: ship_date 2024-01-28 is BEFORE order_date 2024-02-01 -> fix ship_date to '2024-02-04'",
        "Row 4: customer '  delta co  ' has whitespace and wrong case -> 'Delta Co'",
        "Row 5: quantity '0' is invalid for an order -> set to '1'",
        "Row 6: order_date '02/28/2024' wrong format -> '2024-02-28'",
        "Row 7: status 'DELIVERED' wrong case -> 'Delivered'",
        "Row 8: quantity '-3' is negative -> '3'; total '-120.00' -> '120.00'",
        "Row 9: product 'widget a' wrong case -> 'Widget A'",
        "Row 11: order_id is empty -> assign 'ORD-011'",
        "Row 13: unit_price 'thirty' is text -> '30.00'",
        "Row 14: status 'Shpped' is misspelled -> 'Shipped'",
        "Row 15: DUPLICATE of Row 10 (ORD-010) -> delete row",
        "Row 16: total 290.00 != 12 * 25.00 = 300.00 -> fix total to '300.00'",
        "Row 17: customer 'ACME CORP' wrong case -> 'Acme Corp'",
        "Row 17: ship_date 2024-05-08 is BEFORE order_date 2024-05-10 -> fix ship_date to '2024-05-13'",
    ]

    return {
        "task_id": "hard_sales_reconciliation",
        "description": (
            "Reconcile a sales records dataset with 20 entries. Fix complex issues including: "
            "duplicate orders (same order_id, delete the duplicate row), logical inconsistencies "
            "(total should equal quantity * unit_price), date ordering violations (ship_date must "
            "be on or after order_date), inconsistent customer/product names, missing order IDs, "
            "negative quantities (take absolute value), non-numeric prices, misspelled status values "
            "(valid: Shipped, Delivered, Pending, Cancelled), and date format standardization "
            "(use YYYY-MM-DD). Use 'delete_row' for duplicates and 'fix_cell' for corrections."
        ),
        "dirty_data": dirty_data,
        "clean_data": clean_data,
        "columns": ["order_id", "customer", "product", "quantity", "unit_price", "total", "order_date", "ship_date", "status"],
        "max_actions": 80,
        "difficulty": "hard",
        "issues": issues,
    }


TASKS = {
    "easy_customer_contacts": _task_easy,
    "medium_product_inventory": _task_medium,
    "hard_sales_reconciliation": _task_hard,
}


def get_task(task_id: str) -> dict[str, Any]:
    """Get a task by its ID. Returns a deep copy so tasks are independent."""
    if task_id not in TASKS:
        available = ", ".join(TASKS.keys())
        raise ValueError(f"Unknown task_id '{task_id}'. Available: {available}")
    return copy.deepcopy(TASKS[task_id]())
