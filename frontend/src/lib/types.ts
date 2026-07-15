export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type Role = {
  id: string;
  code: string;
  name: string;
  description?: string;
  is_system?: boolean;
  branch_scope?: "ALL" | "ASSIGNED";
  permissions?: { code: string; module: string; label: string; effect: string }[];
};

export type Branch = {
  id: string;
  code: string;
  name: string;
  type: "HEAD_OFFICE" | "BRANCH";
  address?: string;
  phone?: string;
  email?: string;
  status: "ACTIVE" | "INACTIVE";
  manager_name?: string;
};

export type BranchMembership = {
  id: string;
  code: string;
  name: string;
  is_default: boolean;
};

export type CurrentUser = {
  id: string;
  full_name: string;
  mobile: string;
  email: string | null;
  is_superuser: boolean;
  must_change_password: boolean;
  default_branch_id: string | null;
  roles: { id: string; code: string; name: string }[];
  branches: BranchMembership[];
  permissions: string[];
};

export type UserRecord = {
  id: string;
  full_name: string;
  mobile: string;
  email: string | null;
  status: "PENDING_ACTIVATION" | "ACTIVE" | "DEACTIVATED";
  is_superuser: boolean;
  roles: { id: string; code: string; name: string }[];
  branches: BranchMembership[];
  last_login_at: string | null;
  created_at: string;
};

export type Generic = {
  id: string;
  name: string;
  therapeutic_class: string;
  description?: string;
  is_active: boolean;
};

export type Manufacturer = {
  id: string;
  name: string;
  country: string;
  license_no: string;
  is_active: boolean;
};

export type MedicineCategory = {
  id: string;
  name: string;
  parent: string | null;
  parent_name: string;
  sort_order: number;
  is_active: boolean;
};

export type Unit = {
  id: string;
  name: string;
  symbol: string;
  unit_type: "COUNT" | "WEIGHT" | "VOLUME";
  allows_fraction: boolean;
  is_active: boolean;
};

export type MedicineUnitConversion = {
  id: string;
  medicine: string;
  unit: string;
  unit_name: string;
  unit_symbol: string;
  factor_to_base: string;
  is_purchase_default: boolean;
  is_sale_default: boolean;
};

export type Medicine = {
  id: string;
  code: string;
  name: string;
  generic: string | null;
  generic_name: string;
  manufacturer: string | null;
  manufacturer_name: string;
  category: string | null;
  category_name: string;
  base_unit: string | null;
  base_unit_name: string;
  strength: string;
  dosage_form: string;
  pack_size: string;
  purchase_price: string;
  selling_price: string;
  mrp: string;
  vat_rate: string;
  reorder_level: string;
  shelf_life_months: number | null;
  near_expiry_days: number | null;
  no_batch: boolean;
  rx_required: boolean;
  cold_chain: boolean;
  is_active: boolean;
  barcode: string;
  conversions: MedicineUnitConversion[];
};

export type BatchStatus = "ACTIVE" | "DEPLETED" | "EXPIRED" | "QUARANTINE" | "DAMAGED" | "RECALLED";

export type MedicineBatch = {
  id: string;
  branch: string;
  branch_name: string;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch_number: string;
  manufacturing_date: string | null;
  expiry_date: string | null;
  qty_received_total: string;
  qty_on_hand: string;
  unit_cost: string;
  status: BatchStatus;
  notes: string;
  days_to_expiry: number | null;
  created_at: string;
};

export type DashboardSummary = {
  generated_at: string;
  branch_scope: "ALL" | "ASSIGNED";
  users: { total: number; active: number };
  branches: { total: number; active: number };
  roles: { total: number };
  medicines: { total: number; active: number };
  operations: {
    sales_today: number | null;
    collections_today: number | null;
    customer_due: number | null;
    supplier_payable: number | null;
    stock_value: number | null;
    low_stock_count: number | null;
    near_expiry_count: number | null;
  };
};

export type InventoryEntryType =
  | "OPENING"
  | "PURCHASE"
  | "BONUS"
  | "SALE"
  | "SALES_RETURN"
  | "PURCHASE_RETURN"
  | "ADJUSTMENT"
  | "BONUS_ISSUE"
  | "DAMAGE"
  | "EXPIRY"
  | "TRANSFER"
  | "REVERSAL";

export type InventoryTransaction = {
  id: string;
  branch: string;
  branch_name: string;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch: string;
  batch_number: string;
  entry_type: InventoryEntryType;
  pool: "SALEABLE" | "PROMO" | "QUARANTINE";
  qty_delta: string;
  unit_cost: string;
  value_delta: string;
  source_type: string;
  source_number: string;
  transaction_group_id: string;
  business_date: string;
  actor_name: string;
  created_at: string;
};

export type StockSummaryRow = {
  branch: string;
  branch_name: string;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  qty_on_hand: string;
  qty_promo: string;
  qty_quarantine: string;
  reorder_level: string;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
};

export type ExpiryReportRow = {
  branch_name: string;
  medicine_name: string;
  medicine_code: string;
  batch_number: string;
  expiry_date: string;
  days_to_expiry: number;
  qty_on_hand: string;
  qty_quarantine: string;
  value_on_hand: string;
  status: BatchStatus;
};
