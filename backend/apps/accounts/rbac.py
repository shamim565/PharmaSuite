"""Permission catalog and system role definitions (the RBAC source of truth)."""

from apps.accounts.models import BranchScope

# (code, module, action, label, is_sensitive)
PERMISSION_CATALOG: list[tuple[str, str, str, str, bool]] = [
    # Identity & access
    ("USER_VIEW", "identity", "view", "View users", False),
    ("USER_MANAGE", "identity", "manage", "Create and edit users", True),
    ("ROLE_VIEW", "identity", "view", "View roles", False),
    ("ROLE_MANAGE", "identity", "manage", "Create and edit roles and permissions", True),
    # Branches
    ("BRANCH_VIEW", "branch", "view", "View branches", False),
    ("BRANCH_MANAGE", "branch", "manage", "Create and edit branches", True),
    # Catalog
    ("MEDICINE_VIEW", "catalog", "view", "View medicine catalog", False),
    ("MEDICINE_MANAGE", "catalog", "manage", "Create and edit medicines, generics, units", True),
    # Inventory
    ("STOCK_VIEW", "inventory", "view", "View stock and batch balances", False),
    ("STOCK_VIEW_COST", "inventory", "view", "View stock cost and valuation", True),
    ("STOCK_ADJUST", "inventory", "adjust", "Create stock adjustments and write-offs", True),
    ("INV_OVERRIDE_FEFO", "inventory", "override", "Override FEFO batch selection", True),
    ("STOCK_TRANSFER", "inventory", "transfer", "Transfer stock between branches", True),
    # Payments / cheques
    ("CHEQUE_VIEW", "payments", "view", "View cheques", False),
    ("CHEQUE_MANAGE", "payments", "manage", "Create cheques and run lifecycle actions", True),
    # Purchases
    ("SUPPLIER_VIEW", "purchase", "view", "View suppliers and ledgers", False),
    ("SUPPLIER_MANAGE", "purchase", "manage", "Create and edit suppliers", True),
    ("PURCHASE_VIEW", "purchase", "view", "View purchases", False),
    ("PURCHASE_MANAGE", "purchase", "manage", "Create and edit purchase drafts", False),
    ("PURCHASE_CONFIRM", "purchase", "confirm", "Confirm purchases and receive stock", True),
    ("PURCHASE_PAY", "purchase", "pay", "Pay suppliers and allocate payments", True),
    # Sales
    ("CUSTOMER_VIEW", "sale", "view", "View customers and ledgers", False),
    ("CUSTOMER_MANAGE", "sale", "manage", "Create and edit customers and credit terms", True),
    ("SALE_VIEW", "sale", "view", "View invoices", False),
    ("SALE_CREATE", "sale", "create", "Create sale drafts", False),
    ("SALE_CONFIRM", "sale", "confirm", "Confirm sales invoices", True),
    ("SALE_CANCEL", "sale", "cancel", "Cancel invoices", True),
    ("SALE_PRICE_OVERRIDE", "sale", "override", "Override tier prices", True),
    ("SALE_OVERRIDE_CREDIT", "sale", "override", "Override credit limit / overdue blocks", True),
    ("SALE_BELOW_COST", "sale", "override", "Sell below cost or margin floor", True),
    ("SALE_FREE_GOODS", "sale", "override", "Issue free goods on invoices", True),
    ("SALE_ZERO_VALUE", "sale", "override", "Issue zero-value invoices", True),
    # Payments
    ("PAYMENT_VIEW", "payment", "view", "View payments and receipts", False),
    ("PAYMENT_COLLECT", "payment", "collect", "Collect customer payments", True),
    ("PAYMENT_REVERSE", "payment", "reverse", "Reverse payments", True),
    # Returns
    ("SRET_VIEW", "returns", "view", "View sales returns", False),
    ("SRET_CONFIRM", "returns", "confirm", "Confirm sales returns", True),
    ("SRET_NO_INVOICE", "returns", "override", "Accept returns without original invoice", True),
    ("RETURN_REFUND", "returns", "refund", "Refund returns in cash or bank", True),
    ("PRET_VIEW", "returns", "view", "View purchase returns", False),
    ("PRET_CONFIRM", "returns", "confirm", "Confirm purchase returns", True),
    # CRM
    ("DOCTOR_VIEW", "crm", "view", "View doctors and mappings", False),
    ("DOCTOR_MANAGE", "crm", "manage", "Create and edit doctors and mappings", False),
    ("VISIT_VIEW", "crm", "view", "View doctor visits", False),
    ("VISIT_MANAGE", "crm", "manage", "Plan and log doctor visits and samples", False),
    ("REP_VIEW", "crm", "view", "View representatives", False),
    ("REP_MANAGE", "crm", "manage", "Create and edit representatives and assignments", True),
    ("TERRITORY_MANAGE", "crm", "manage", "Manage territories", True),
    # Finance
    ("ACCOUNT_VIEW", "finance", "view", "View financial accounts", False),
    ("ACCOUNT_MANAGE", "finance", "manage", "Manage financial accounts and transfers", True),
    ("EXPENSE_VIEW", "finance", "view", "View expenses", False),
    ("EXPENSE_POST", "finance", "post", "Record expenses", True),
    ("EXPENSE_APPROVE", "finance", "approve", "Approve expenses above threshold", True),
    ("INCOME_VIEW", "finance", "view", "View other income", False),
    ("INCOME_POST", "finance", "post", "Record other income", True),
    ("PERIOD_LOCK", "finance", "lock", "Lock fiscal periods", True),
    ("PERIOD_OVERRIDE", "finance", "override", "Post into locked periods", True),
    # Reports
    ("DASHBOARD_VIEW", "dashboard", "view", "View dashboard", False),
    ("REPORT_VIEW", "report", "view", "View reports", False),
    ("REPORT_VIEW_COST", "report", "view", "View cost and profit figures", True),
    ("REPORT_EXCEPTION", "report", "view", "View exception/override report", True),
    # Audit
    ("AUDIT_VIEW", "audit", "view", "View audit logs", True),
    ("AUDIT_EXPORT", "audit", "export", "Export audit logs", True),
    # Settings
    ("SETTINGS_VIEW", "settings", "view", "View settings", False),
    ("SETTINGS_MANAGE", "settings", "manage", "Manage settings", True),
]

ALL_CODES = {row[0] for row in PERMISSION_CATALOG}

MODULE_CODES: dict[str, set[str]] = {}
for _code, _module, *_rest in PERMISSION_CATALOG:
    MODULE_CODES.setdefault(_module, set()).add(_code)

# Role definition: scope + module wildcard patterns ("*" = all)
ROLE_DEFINITIONS: dict[str, dict] = {
    "OWNER": {
        "name": "Owner",
        "description": "Business owner with unrestricted access.",
        "scope": BranchScope.ALL,
        "permissions": ["*"],
    },
    "SUPER_ADMIN": {
        "name": "Super Admin",
        "description": "System administrator: users, roles, branches, settings, audit.",
        "scope": BranchScope.ALL,
        "permissions": ["*"],
    },
    "ADMIN": {
        "name": "Admin",
        "description": "Operations administrator across assigned branches.",
        "scope": BranchScope.ALL,
        "permissions": ["*"],
        "exclude": ["PERIOD_OVERRIDE"],
    },
    "BRANCH_MANAGER": {
        "name": "Branch Manager",
        "description": "Runs a branch; approves overrides and monitors performance.",
        "scope": BranchScope.ASSIGNED,
        "permissions": [
            "identity:USER_VIEW",
            "branch:BRANCH_VIEW",
            "catalog:*",
            "inventory:*",
            "purchase:SUPPLIER_VIEW",
            "purchase:PURCHASE_VIEW",
            "purchase:PURCHASE_MANAGE",
            "purchase:PURCHASE_CONFIRM",
            "sale:*",
            "payment:*",
            "returns:*",
            "crm:DOCTOR_VIEW",
            "crm:DOCTOR_MANAGE",
            "crm:VISIT_VIEW",
            "crm:REP_VIEW",
            "crm:REP_MANAGE",
            "crm:TERRITORY_MANAGE",
            "finance:ACCOUNT_VIEW",
            "finance:EXPENSE_VIEW",
            "finance:EXPENSE_POST",
            "finance:EXPENSE_APPROVE",
            "finance:INCOME_VIEW",
            "dashboard:*",
            "report:*",
        ],
        "exclude": ["SALE_ZERO_VALUE", "PERIOD_OVERRIDE", "REPORT_EXCEPTION"],
    },
    "ACCOUNTANT": {
        "name": "Accountant",
        "description": "Money flows, ledgers, expenses, income, reconciliation.",
        "scope": BranchScope.ASSIGNED,
        "permissions": [
            "identity:USER_VIEW",
            "branch:BRANCH_VIEW",
            "catalog:MEDICINE_VIEW",
            "inventory:STOCK_VIEW",
            "inventory:STOCK_VIEW_COST",
            "purchase:SUPPLIER_VIEW",
            "purchase:SUPPLIER_MANAGE",
            "purchase:PURCHASE_VIEW",
            "purchase:PURCHASE_PAY",
            "sale:CUSTOMER_VIEW",
            "sale:CUSTOMER_MANAGE",
            "sale:SALE_VIEW",
            "payment:*",
            "returns:SRET_VIEW",
            "returns:PRET_VIEW",
            "finance:*",
            "dashboard:*",
            "report:*",
            "audit:AUDIT_VIEW",
        ],
        "exclude": ["PERIOD_OVERRIDE", "REPORT_EXCEPTION"],
    },
    "SALES_OPERATOR": {
        "name": "Sales Operator",
        "description": "Counter sales, invoicing and collection.",
        "scope": BranchScope.ASSIGNED,
        "permissions": [
            "catalog:MEDICINE_VIEW",
            "inventory:STOCK_VIEW",
            "sale:CUSTOMER_VIEW",
            "sale:CUSTOMER_MANAGE",
            "sale:SALE_VIEW",
            "sale:SALE_CREATE",
            "sale:SALE_CONFIRM",
            "payment:PAYMENT_VIEW",
            "payment:PAYMENT_COLLECT",
            "returns:SRET_VIEW",
            "dashboard:*",
            "report:REPORT_VIEW",
        ],
        "exclude": [
            "SALE_CANCEL",
            "SALE_PRICE_OVERRIDE",
            "SALE_OVERRIDE_CREDIT",
            "SALE_BELOW_COST",
            "SALE_FREE_GOODS",
            "SALE_ZERO_VALUE",
        ],
    },
    "WAREHOUSE_MANAGER": {
        "name": "Warehouse Manager",
        "description": "Receiving, storage, batch/expiry integrity, adjustments.",
        "scope": BranchScope.ASSIGNED,
        "permissions": [
            "catalog:*",
            "inventory:*",
            "purchase:SUPPLIER_VIEW",
            "purchase:SUPPLIER_MANAGE",
            "purchase:PURCHASE_VIEW",
            "purchase:PURCHASE_MANAGE",
            "purchase:PURCHASE_CONFIRM",
            "returns:SRET_VIEW",
            "returns:PRET_VIEW",
            "returns:PRET_CONFIRM",
            "dashboard:*",
            "report:REPORT_VIEW",
            "report:REPORT_VIEW_COST",
        ],
    },
    "SALES_REP": {
        "name": "Sales Representative",
        "description": "Field sales coverage for assigned customers.",
        "scope": BranchScope.ASSIGNED,
        "permissions": [
            "catalog:MEDICINE_VIEW",
            "sale:CUSTOMER_VIEW",
            "sale:SALE_VIEW",
            "dashboard:*",
            "report:REPORT_VIEW",
        ],
    },
    "MEDICAL_REP": {
        "name": "Medical Representative",
        "description": "Doctor coverage, visits and samples.",
        "scope": BranchScope.ASSIGNED,
        "permissions": [
            "catalog:MEDICINE_VIEW",
            "crm:DOCTOR_VIEW",
            "crm:DOCTOR_MANAGE",
            "crm:VISIT_VIEW",
            "crm:VISIT_MANAGE",
            "crm:REP_VIEW",
            "dashboard:*",
            "report:REPORT_VIEW",
        ],
    },
}


def resolve_permissions(patterns: list[str]) -> set[str]:
    if "*" in patterns:
        return set(ALL_CODES)
    resolved: set[str] = set()
    for pattern in patterns:
        if pattern.endswith(":*"):
            module = pattern[:-2]
            resolved |= MODULE_CODES.get(module, set())
        elif ":" in pattern:
            resolved.add(pattern.split(":", 1)[1])
        else:
            resolved.add(pattern)
    return resolved


def role_permission_codes(definition: dict) -> set[str]:
    codes = resolve_permissions(definition["permissions"])
    for code in definition.get("exclude", []):
        codes.discard(code)
    return codes
