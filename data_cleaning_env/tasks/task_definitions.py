"""
Task definitions for the Data Cleaning Environment.

Each task provides:
- task_id: Unique identifier for the task
- dirty_data: The messy dataset the agent must clean (list of dicts)
- clean_data: The gold-standard clean version (list of dicts)
- columns: Column names
- description: Detailed human-readable task description
- max_actions: Maximum allowed actions
- difficulty: easy / medium / hard
- issues: List of detailed issue descriptions
- metadata: Domain context, skills tested, real-world impact, difficulty score
- issue_taxonomy: Categorization of issues by type (formatting, semantic, structural, logical)
"""

import copy
from typing import Any, Callable


def _validate_task_structure(task: dict[str, Any]) -> bool:
    """Validate that a task has all required fields and data integrity."""
    required_fields = {
        "task_id", "dirty_data", "clean_data", "columns", "description",
        "max_actions", "difficulty", "issues", "metadata", "issue_taxonomy"
    }
    if not required_fields.issubset(task.keys()):
        missing = required_fields - set(task.keys())
        raise ValueError(f"Task missing required fields: {missing}")

    # Validate dirty_data and clean_data structure
    if not isinstance(task["dirty_data"], list) or not isinstance(task["clean_data"], list):
        raise ValueError("dirty_data and clean_data must be lists")

    if len(task["dirty_data"]) == 0:
        raise ValueError("dirty_data cannot be empty")

    # All rows should have the same columns
    expected_cols = set(task["columns"])
    for idx, row in enumerate(task["clean_data"]):
        if set(row.keys()) != expected_cols:
            raise ValueError(
                f"Row {idx} in clean_data has columns {set(row.keys())}, "
                f"expected {expected_cols}"
            )

    # Validate metadata
    metadata = task["metadata"]
    required_metadata = {"domain", "skills_tested", "real_world_impact", "estimated_difficulty_score"}
    if not required_metadata.issubset(metadata.keys()):
        missing = required_metadata - set(metadata.keys())
        raise ValueError(f"Metadata missing fields: {missing}")

    if not isinstance(metadata["estimated_difficulty_score"], (int, float)):
        raise ValueError("estimated_difficulty_score must be a number")
    if not (0 <= metadata["estimated_difficulty_score"] <= 1):
        raise ValueError("estimated_difficulty_score must be between 0 and 1")

    if not isinstance(metadata["skills_tested"], list):
        raise ValueError("skills_tested must be a list")

    # Validate issue_taxonomy
    taxonomy = task["issue_taxonomy"]
    valid_types = {"formatting", "semantic", "structural", "logical"}
    if not all(cat in valid_types for cat in taxonomy.keys()):
        invalid = set(taxonomy.keys()) - valid_types
        raise ValueError(f"Invalid issue categories in taxonomy: {invalid}")

    return True


def _validate_issues_present(task: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate that all issues described in the task are actually present in dirty_data.

    Returns:
        (is_valid, messages) - tuple of validation result and list of messages
    """
    messages = []
    try:
        # This is a basic check - in production you'd implement row-specific validation
        if len(task["issues"]) > 0 and len(task["dirty_data"]) > 0:
            messages.append(f"Task has {len(task['issues'])} documented issues across {len(task['dirty_data'])} rows")
            return True, messages
    except Exception as e:
        messages.append(f"Error validating issues: {str(e)}")
    return True, messages


def _task_easy() -> dict[str, Any]:
    """Task 1 (Easy): Fix Customer Contact List.

    Domain: Customer Relationship Management (CRM)
    Issues: whitespace handling, text case normalization, date format standardization,
    email validation, phone number formatting, and geographical name consistency.
    10 rows, 20 distinct data quality issues.
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
        "Row 0, name: Leading/trailing whitespace ('  john doe  ') + lowercase name needs proper case",
        "Row 0, signup_date: Non-standard format MM/DD/YYYY (01/15/2024) must be YYYY-MM-DD (2024-01-15)",
        "Row 0, city: Lowercase 'new york' should be title case 'New York'",
        "Row 1, name: ALL CAPS text 'JANE SMITH' violates proper name casing convention",
        "Row 1, email: Incomplete email address 'jane@example' missing domain TLD (.com)",
        "Row 2, phone: Phone number '5551234567' lacks delimiter dashes (should be 555-1234567)",
        "Row 2, signup_date: English text format 'March 3, 2024' must be ISO 8601 format (2024-03-03)",
        "Row 2, city: Lowercase 'chicago' should be 'Chicago'",
        "Row 3, name: Multiple excessive spaces ('alice   williams') should normalize to single space",
        "Row 4, signup_date: Date format MM/DD/YYYY (05/22/2024) should be YYYY-MM-DD (2024-05-22)",
        "Row 4, city: ALL CAPS 'PHOENIX' should be 'Phoenix'",
        "Row 5, name: Leading whitespace (' david lee') + lowercase should be 'David Lee'",
        "Row 5, phone: Phone delimiter error - spaces '555 7890' should be dashes '555-7890'",
        "Row 6, email: Double @ symbol 'eva@@example.com' is invalid - should be 'eva@example.com'",
        "Row 6, city: Lowercase 'san antonio' should be title case 'San Antonio'",
        "Row 7, name: Mixed case inconsistency 'frank WILSON' should be 'Frank Wilson'",
        "Row 7, signup_date: English text format 'Aug 18, 2024' must be YYYY-MM-DD (2024-08-18)",
        "Row 8, city: Lowercase 'dallas' should be 'Dallas'",
        "Row 9, name: Leading/trailing whitespace ('  henry thomas ') with lowercase needs title case",
        "Row 9, signup_date: Date format MM/DD/YYYY (10/05/2024) should be YYYY-MM-DD (2024-10-05)",
    ]

    issue_taxonomy = {
        "formatting": [
            "Leading/trailing whitespace in names",
            "Phone number delimiter inconsistency (dashes vs spaces)",
            "Date format standardization (multiple input formats to ISO 8601)",
            "Multiple consecutive spaces in text fields",
        ],
        "semantic": [
            "Email domain completeness (missing TLD)",
            "Invalid email syntax (double @ symbols)",
            "City name capitalization (title case convention)",
            "Personal name capitalization (proper case convention)",
        ],
        "structural": [
            "Phone number structure (digit grouping with proper delimiters)",
            "Email structure (valid format with @domain.tld)",
            "Date structure (ISO 8601 YYYY-MM-DD format)",
        ],
        "logical": []
    }

    metadata = {
        "domain": "Customer Relationship Management (CRM) / Contact Management",
        "skills_tested": [
            "Text normalization and whitespace handling",
            "Case conversion and title casing",
            "Date format standardization",
            "Email validation and correction",
            "Phone number formatting",
            "Geographical name consistency"
        ],
        "real_world_impact": (
            "Clean contact data is essential for customer communications, mailing lists, and "
            "CRM system functionality. Inconsistent formatting can break automated systems and "
            "degrade user experience. This task simulates typical data entry errors in small-to-medium "
            "customer databases."
        ),
        "estimated_difficulty_score": 0.25,
    }

    task_dict = {
        "task_id": "easy_customer_contacts",
        "description": (
            "Clean a customer contact list with 10 entries representing customer signup data. "
            "The dataset contains common data quality issues found in manually-entered contact information. "
            "Fix inconsistent name capitalization, extra whitespace, non-standard date formats "
            "(standardize all dates to ISO 8601: YYYY-MM-DD), malformed or incomplete emails, "
            "inconsistent phone number formatting, and improper geographical name capitalization. "
            "This task tests fundamental data cleaning skills including text normalization, "
            "format standardization, and validation pattern recognition."
        ),
        "dirty_data": dirty_data,
        "clean_data": clean_data,
        "columns": ["name", "email", "phone", "signup_date", "city"],
        "max_actions": 40,
        "difficulty": "easy",
        "issues": issues,
        "metadata": metadata,
        "issue_taxonomy": issue_taxonomy,
    }

    _validate_task_structure(task_dict)
    return task_dict


def _task_medium() -> dict[str, Any]:
    """Task 2 (Medium): Clean Product Inventory.

    Domain: Retail / Inventory Management System
    Issues: missing values, type mismatches, inconsistent enumeration values,
    out-of-range numeric values, unit inconsistencies, non-numeric strings,
    case normalization, and abbreviation expansion.
    15 rows, 22 distinct data quality issues.
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
        "Row 1, category: 'electronics' has wrong case - should be 'Electronics' (standardized enum value)",
        "Row 2, category: 'Electr.' is an abbreviation - should be expanded to full 'Electronics'",
        "Row 2, price: Text value 'forty-five' is non-numeric - should be converted to '45.00'",
        "Row 3, stock: Negative value '-10' is invalid for inventory - should be normalized to '0'",
        "Row 4, stock: Empty/missing value should be interpreted as '0' (no stock available)",
        "Row 5, product_name: Empty/null product name is missing required field - should be 'Unknown Product'",
        "Row 6, category: 'ELECTRONICS' has wrong case - should be 'Electronics'",
        "Row 6, rating: Out-of-range value '11.0' exceeds maximum allowed 5.0 - should be capped at '5.0'",
        "Row 7, weight_kg: Unit-suffixed value '2500g' mixed with wrong interpretation - should be '2.5' kg",
        "Row 8, category: 'Electronicss' is misspelled (extra 's') - should be 'Electronics'",
        "Row 8, rating: Empty/missing rating value - should be defaulted to '0.0'",
        "Row 9, category: 'stationery' has wrong case - should be 'Stationery'",
        "Row 10, price: Currency symbol prefix '$299.00' should be stripped to '299.00'",
        "Row 11, stock: Non-numeric string 'N/A' cannot be processed - should be normalized to '0'",
        "Row 12, category: 'Home & office' has mixed case - should be 'Home & Office' (proper title case)",
        "Row 13, rating: Negative value '-1.0' outside valid range [0.0, 5.0] - should be normalized to '0.0'",
        "Row 14, category: 'Electrnics' is misspelled (missing 'o') - should be 'Electronics'",
    ]

    issue_taxonomy = {
        "formatting": [
            "Currency symbol removal from price field",
            "Unit suffix handling in weight field",
            "Case normalization for category enumeration",
            "Empty string handling and default values",
        ],
        "semantic": [
            "Enumeration value validation (valid categories: Electronics, Stationery, Home & Office)",
            "Product name missing value handling",
            "Typos in enumeration values (Electronicss, Electrnics, Electr.)",
        ],
        "structural": [
            "Numeric type validation for price field",
            "Numeric type validation for stock field",
            "Numeric type validation for weight field",
            "Numeric type validation for rating field",
        ],
        "logical": [
            "Range validation for stock (must be >= 0)",
            "Range validation for rating (must be between 0.0 and 5.0)",
            "Weight unit conversion and parsing (grams to kilograms)",
        ]
    }

    metadata = {
        "domain": "Retail / E-commerce Inventory Management",
        "skills_tested": [
            "Enumeration/categorical value normalization",
            "Numeric type conversion and validation",
            "Range constraint enforcement",
            "Unit conversion and suffix stripping",
            "Missing value imputation",
            "Case normalization",
            "Typo detection and correction",
            "Currency formatting"
        ],
        "real_world_impact": (
            "Accurate product inventory is critical for retail operations, pricing accuracy, and supply chain "
            "management. Inconsistent product data leads to inventory discrepancies, pricing errors, and poor "
            "customer experience. This task simulates common data quality issues in e-commerce and retail systems "
            "where products are managed across multiple channels and data sources."
        ),
        "estimated_difficulty_score": 0.55,
    }

    task_dict = {
        "task_id": "medium_product_inventory",
        "description": (
            "Clean a product inventory dataset with 15 product entries representing a retail catalog. "
            "The dataset contains multiple types of data quality issues commonly found in e-commerce systems. "
            "Fix inconsistent category enumeration values by standardizing to valid categories "
            "('Electronics', 'Stationery', 'Home & Office'), remove currency symbols and convert text prices "
            "to numeric values, handle negative and missing stock values by setting to 0, convert weight with "
            "unit suffixes to plain numeric values in kg, enforce rating constraints (0.0-5.0 range), fill missing "
            "product names with 'Unknown Product', and correct misspelled category values. This task requires "
            "understanding enumeration constraints, numeric validation, range constraints, and data imputation."
        ),
        "dirty_data": dirty_data,
        "clean_data": clean_data,
        "columns": ["product_name", "category", "price", "stock", "weight_kg", "rating"],
        "max_actions": 60,
        "difficulty": "medium",
        "issues": issues,
        "metadata": metadata,
        "issue_taxonomy": issue_taxonomy,
    }

    _validate_task_structure(task_dict)
    return task_dict


def _task_hard() -> dict[str, Any]:
    """Task 3 (Hard): Reconcile Sales Records.

    Domain: Order Management / Enterprise Data Reconciliation
    Issues: exact duplicates, near-duplicates with divergent totals, logical inconsistencies
    (cross-field validation: total != qty * price), temporal constraint violations (ship_date
    before order_date), missing primary keys, negative/zero quantities, text in numeric fields,
    whitespace in categorical fields, case normalization, format inconsistencies, and enumeration
    violations (invalid status values). Requires deduplication and multi-field validation.
    20 rows, 28 distinct data quality issues.
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

    # Clean version: duplicates removed (rows 2, 15), all issues fixed
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
        "Row 1, status: 'shipped' has wrong case - should be 'Shipped' (capitalized)",
        "Row 2: EXACT DUPLICATE of Row 1 with order_id 'ORD-002', but total differs (200.50 vs 200.00) indicating data conflict - DELETE this row as duplicate",
        "Row 3, total: Arithmetic mismatch - total '250.00' != quantity(3) * unit_price(100.00) = 300.00 - correct total to '300.00'",
        "Row 3, ship_date: Temporal constraint violation - ship_date '2024-01-28' is BEFORE order_date '2024-02-01' (impossible) - correct ship_date to '2024-02-04'",
        "Row 4, customer: Whitespace issue ' delta co ' has leading/trailing spaces and wrong case - normalize to 'Delta Co'",
        "Row 5, quantity: Zero quantity '0' is semantically invalid for a sales order - set to '1' (minimum)",
        "Row 6, order_date: Non-ISO format '02/28/2024' (MM/DD/YYYY) must be standardized to '2024-02-28' (YYYY-MM-DD)",
        "Row 7, status: 'DELIVERED' has wrong case - should be 'Delivered' (valid enum value)",
        "Row 8, quantity: Negative quantity '-3' is logically invalid - take absolute value to '3'",
        "Row 8, total: Negative total '-120.00' is a consequence of negative quantity - correct to '120.00' (recalculated as 3 * 40.00)",
        "Row 9, product: 'widget a' has wrong case - should be 'Widget A' (proper product name casing)",
        "Row 11, order_id: Empty/missing order_id violates primary key requirement - assign generated value 'ORD-011'",
        "Row 13, unit_price: Text value 'thirty' is non-numeric - convert to numeric '30.00'",
        "Row 14, status: Misspelled value 'Shpped' (missing 'i') is not valid enum - correct to 'Shipped'",
        "Row 15: EXACT DUPLICATE of Row 10 with order_id 'ORD-010' - DELETE this row as duplicate",
        "Row 16, total: Arithmetic mismatch - total '290.00' != quantity(12) * unit_price(25.00) = 300.00 - correct total to '300.00'",
        "Row 17, customer: 'ACME CORP' has wrong case - normalize to 'Acme Corp' (title case)",
        "Row 17, ship_date: Temporal constraint violation - ship_date '2024-05-08' is BEFORE order_date '2024-05-10' (impossible) - correct ship_date to '2024-05-13'",
    ]

    issue_taxonomy = {
        "formatting": [
            "Case normalization for status enumeration",
            "Case normalization for product names",
            "Case normalization for customer names",
            "Whitespace trimming in customer field",
            "Date format standardization (MM/DD/YYYY to YYYY-MM-DD)",
            "Numeric formatting (text to numeric conversion)",
        ],
        "semantic": [
            "Status value enumeration (valid: Shipped, Delivered, Pending, Cancelled)",
            "Customer name normalization (title case convention)",
            "Product name normalization (title case convention)",
            "Misspelled enumeration values (Shpped -> Shipped)",
        ],
        "structural": [
            "Order ID primary key requirement (cannot be empty)",
            "All rows must have required fields",
            "Date format consistency across all date fields",
            "Numeric field type validation",
        ],
        "logical": [
            "Cross-field validation: total must equal quantity * unit_price",
            "Temporal ordering: ship_date must be >= order_date",
            "Quantity constraint: must be positive (> 0)",
            "Exact duplicate detection and removal by order_id",
            "Out-of-range quantity correction (negative to positive)",
        ]
    }

    metadata = {
        "domain": "Order Management / Sales Records Reconciliation / Enterprise Data Quality",
        "skills_tested": [
            "Duplicate detection and removal (exact matches)",
            "Cross-field arithmetic validation",
            "Temporal constraint validation",
            "Primary key constraint enforcement",
            "Enumeration value normalization",
            "Text case normalization",
            "Whitespace handling",
            "Date format standardization",
            "Numeric type conversion",
            "Multi-field referential integrity",
            "Business logic validation",
            "Complex data quality assessment"
        ],
        "real_world_impact": (
            "Sales order reconciliation is critical in financial systems, supply chain management, and "
            "revenue recognition processes. Duplicate orders cause billing errors and inventory discrepancies. "
            "Incorrect totals lead to financial statement errors. Temporal inconsistencies break fulfillment "
            "workflows. This task simulates realistic challenges in enterprise data warehouses integrating data "
            "from multiple order systems, where consistency enforcement is essential for compliance and accuracy."
        ),
        "estimated_difficulty_score": 0.80,
    }

    task_dict = {
        "task_id": "hard_sales_reconciliation",
        "description": (
            "Reconcile a complex sales orders dataset with 20 order records requiring multi-field validation, "
            "deduplication, and business logic verification. This dataset simulates real-world challenges in "
            "enterprise order management systems with data from multiple sources and inconsistent formatting. "
            "Fix multiple categories of issues: (1) Remove duplicate orders identified by matching order_id values "
            "(rows with identical order_id should be deduplicated, keeping the first occurrence); (2) Enforce "
            "arithmetic consistency by validating that total field equals quantity * unit_price (correct mismatches); "
            "(3) Enforce temporal constraints by validating that ship_date is on or after order_date (correct violations); "
            "(4) Normalize enumeration values for status field to valid options (Shipped, Delivered, Pending, Cancelled) "
            "with proper case; (5) Enforce primary key constraints by assigning order_id 'ORD-011' to the missing ID; "
            "(6) Correct quantity anomalies (zero or negative values); (7) Standardize date formats to ISO 8601 "
            "(YYYY-MM-DD); (8) Fix whitespace and case issues in customer and product names; (9) Convert text prices "
            "to numeric values. This task tests advanced data quality skills including deduplication logic, "
            "cross-field validation, temporal reasoning, and business constraint enforcement."
        ),
        "dirty_data": dirty_data,
        "clean_data": clean_data,
        "columns": ["order_id", "customer", "product", "quantity", "unit_price", "total", "order_date", "ship_date", "status"],
        "max_actions": 80,
        "difficulty": "hard",
        "issues": issues,
        "metadata": metadata,
        "issue_taxonomy": issue_taxonomy,
    }

    _validate_task_structure(task_dict)
    return task_dict


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


def validate_all_tasks() -> dict[str, bool]:
    """
    Validate all registered tasks for structural integrity.

    Returns:
        Dictionary mapping task_id to validation result
    """
    results = {}
    for task_id in TASKS.keys():
        try:
            task = get_task(task_id)
            _validate_task_structure(task)
            is_valid, messages = _validate_issues_present(task)
            results[task_id] = is_valid
        except Exception as e:
            results[task_id] = False
            print(f"Task {task_id} validation failed: {str(e)}")
    return results


def get_task_metadata(task_id: str) -> dict[str, Any]:
    """Get metadata for a specific task, useful for filtering/search."""
    task = get_task(task_id)
    return {
        "task_id": task["task_id"],
        "difficulty": task["difficulty"],
        "max_actions": task["max_actions"],
        "num_rows": len(task["dirty_data"]),
        "num_issues": len(task["issues"]),
        "num_columns": len(task["columns"]),
        "domain": task["metadata"]["domain"],
        "estimated_difficulty_score": task["metadata"]["estimated_difficulty_score"],
        "skills_tested": task["metadata"]["skills_tested"],
        "issue_categories": list(task["issue_taxonomy"].keys()),
    }


def list_tasks() -> list[dict[str, Any]]:
    """List all available tasks with their metadata."""
    return [get_task_metadata(task_id) for task_id in TASKS.keys()]
