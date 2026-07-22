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
    cash_position: number | null;
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

export type Supplier = {
  id: string;
  code: string;
  name: string;
  supplier_type: "MANUFACTURER" | "IMPORTER" | "TRADER" | "DISTRIBUTOR";
  contact_person: string;
  phone: string;
  email: string;
  address: string;
  credit_days: number;
  preferred_payment_method: string;
  balance_cache: string;
  is_active: boolean;
};

export type SupplierLedgerEntry = {
  id: string;
  entry_type: string;
  amount_delta: string;
  due_date: string | null;
  source_type: string;
  source_number: string;
  business_date: string;
  running_balance: string;
};

export type SupplierLedgerResponse = {
  balance: string;
  count: number;
  results: SupplierLedgerEntry[];
};

export type FinancialAccount = {
  id: string;
  code: string;
  name: string;
  account_type: "CASH" | "BANK" | "MFS";
  branch: string | null;
  branch_name: string;
  provider: string;
  account_number: string;
  balance_cache: string;
  is_active: boolean;
};

export type PurchaseItem = {
  id: string;
  line_no: number;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch: string | null;
  batch_number: string;
  manufacturing_date: string | null;
  expiry_date: string | null;
  conversion_factor: string;
  qty_entered: string;
  qty_base: string;
  bonus_qty_entered: string;
  bonus_qty_base: string;
  unit_cost: string;
  line_discount: string;
  vat_rate: string;
  vat_amount: string;
  line_net: string;
  base_unit_cost: string;
  effective_unit_cost: string;
  returned_qty_base: string;
};

export type Purchase = {
  id: string;
  number: string | null;
  branch: string;
  branch_name: string;
  supplier: string;
  supplier_name: string;
  supplier_invoice_number: string;
  supplier_invoice_date: string;
  business_date: string;
  lifecycle: "DRAFT" | "CONFIRMED" | "CANCELLED";
  payment_status: "UNPAID" | "PARTIALLY_PAID" | "PAID";
  return_status: "NONE" | "PARTIALLY_RETURNED" | "FULLY_RETURNED";
  subtotal: string;
  discount_total: string;
  vat_total: string;
  freight_total: string;
  round_off: string;
  grand_total: string;
  paid_total: string;
  returned_total: string;
  outstanding: string;
  notes: string;
  confirmed_at: string | null;
  cancel_reason: string;
  created_at: string;
  items: PurchaseItem[];
};

export type SupplierPaymentAllocation = {
  id: string;
  purchase: string;
  purchase_number: string | null;
  amount: string;
};

export type SupplierPayment = {
  id: string;
  number: string;
  branch: string;
  branch_name: string;
  supplier: string;
  supplier_name: string;
  business_date: string;
  amount: string;
  method: string;
  account: string;
  account_name: string;
  reference: string;
  status: "ACTIVE" | "REVERSED";
  allocations: SupplierPaymentAllocation[];
  created_at: string;
};

export type PayableAgingRow = {
  supplier: string;
  supplier_name: string;
  supplier_code: string;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_90_plus: string;
  total: string;
};

export type Customer = {
  id: string;
  code: string;
  name: string;
  customer_type: "PHARMACY" | "RETAIL" | "HOSPITAL" | "CLINIC";
  contact_person: string;
  phone: string;
  email: string;
  address: string;
  area: string;
  price_tier: "RETAIL" | "WHOLESALE" | "CUSTOM";
  default_discount_pct: string;
  credit_limit: string;
  credit_days: number;
  credit_hold: boolean;
  credit_hold_reason: string;
  balance_cache: string;
  is_active: boolean;
};

export type CustomerLedgerEntry = {
  id: string;
  entry_type: string;
  amount_delta: string;
  due_date: string | null;
  source_type: string;
  source_number: string;
  business_date: string;
  running_balance: string;
};

export type CustomerLedgerResponse = {
  balance: string;
  count: number;
  results: CustomerLedgerEntry[];
};

export type SalesInvoiceItem = {
  id: string;
  line_no: number;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch: string | null;
  batch_number: string;
  qty: string;
  unit_price: string;
  line_discount: string;
  vat_rate: string;
  vat_amount: string;
  line_net: string;
  line_total: string;
  unit_cost: string;
  is_free_goods: boolean;
  returned_qty: string;
};

export type SalesInvoice = {
  id: string;
  number: string | null;
  branch: string;
  branch_name: string;
  branch_address: string;
  branch_phone: string;
  customer: string;
  customer_name: string;
  customer_code: string;
  customer_phone: string;
  customer_address: string;
  business_date: string;
  lifecycle: "DRAFT" | "CONFIRMED" | "CANCELLED";
  payment_status: "UNPAID" | "PARTIALLY_PAID" | "PAID";
  return_status: "NONE" | "PARTIALLY_RETURNED" | "FULLY_RETURNED";
  fulfillment_status: "PENDING" | "DELIVERED";
  subtotal: string;
  discount_total: string;
  vat_total: string;
  round_off: string;
  grand_total: string;
  paid_total: string;
  outstanding: string;
  due_date: string | null;
  notes: string;
  confirmed_at: string | null;
  cancel_reason: string;
  credit_override: boolean;
  credit_override_reason: string;
  created_at: string;
  items: SalesInvoiceItem[];
};

export type FefoBatch = {
  batch: string;
  batch_number: string;
  expiry_date: string | null;
  qty_on_hand: string;
  unit_cost: string;
  days_to_expiry: number | null;
};

export type ReceivableAgingRow = {
  customer: string;
  customer_name: string;
  customer_code: string;
  phone: string;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_90_plus: string;
  total: string;
};

export type DueListRow = {
  invoice: string;
  number: string;
  business_date: string;
  due_date: string;
  days_overdue: number;
  bucket: "current" | "days_1_30" | "days_31_60" | "days_61_90" | "days_90_plus";
  customer: string;
  customer_name: string;
  customer_code: string;
  phone: string;
  branch: string;
  branch_name: string;
  grand_total: string;
  paid_total: string;
  outstanding: string;
  payment_status: "UNPAID" | "PARTIALLY_PAID" | "PAID";
};

export type DueListResponse = {
  count: number;
  totals: { outstanding: string; overdue: string };
  results: DueListRow[];
};

export type AdvanceRow = {
  customer: string;
  customer_name: string;
  customer_code: string;
  phone: string;
  advance: string;
};

export type CustomerPaymentAllocation = {
  id: string;
  invoice: string;
  invoice_number: string;
  amount: string;
};

export type CustomerPayment = {
  id: string;
  number: string;
  branch: string;
  branch_name: string;
  customer: string;
  customer_name: string;
  business_date: string;
  amount: string;
  method: string;
  account: string;
  account_name: string;
  reference: string;
  collector_name: string;
  status: "ACTIVE" | "REVERSED";
  allocations: CustomerPaymentAllocation[];
  created_at: string;
};

export type DailyCollectionReport = {
  date: string;
  payment_count: number;
  total: string;
  by_method: { method: string; total: string; count: number }[];
  by_collector: { collector: string | null; collector_name: string; total: string; count: number }[];
};

export type SalesReturnItem = {
  id: string;
  invoice_item: string;
  line_no: number;
  medicine_name: string;
  medicine_code: string;
  batch: string;
  batch_number: string;
  qty: string;
  condition: "RESELLABLE" | "DAMAGED" | "EXPIRED";
  unit_price: string;
  discount_reversal: string;
  vat_reversal: string;
  unit_cost: string;
  restocked: boolean;
};

export type SalesReturn = {
  id: string;
  number: string | null;
  invoice: string;
  invoice_number: string;
  customer: string;
  customer_name: string;
  branch: string;
  business_date: string;
  reason_code: string;
  status: "DRAFT" | "CONFIRMED" | "REVERSED";
  refund_method: string;
  refund_account: string | null;
  subtotal: string;
  discount_reversal: string;
  vat_reversal: string;
  round_off: string;
  grand_total: string;
  notes: string;
  confirmed_at: string | null;
  created_at: string;
  items: SalesReturnItem[];
};

export type StockAdjustmentItem = {
  id: string;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch: string;
  batch_number: string;
  qty: string;
  pool: "SALEABLE" | "PROMO" | "QUARANTINE";
  target_pool: "SALEABLE" | "PROMO" | "QUARANTINE" | null;
  unit_cost: string;
};

export type StockAdjustment = {
  id: string;
  number: string | null;
  branch: string;
  branch_name: string;
  business_date: string;
  adjustment_type: "INCREASE" | "DECREASE";
  reason_code: string;
  status: "PENDING_APPROVAL" | "POSTED" | "REJECTED" | "REVERSED";
  total_value: string;
  requested_by_name: string;
  approved_by_name: string;
  approved_at: string | null;
  posted_at: string | null;
  rejection_reason: string;
  reversal_of: string | null;
  notes: string;
  created_at: string;
  items: StockAdjustmentItem[];
};

export type ExpenseCategory = {
  id: string;
  name: string;
  is_system: boolean;
  is_active: boolean;
};

export type Expense = {
  id: string;
  number: string | null;
  branch: string;
  branch_name: string;
  business_date: string;
  category: string;
  category_name: string;
  amount: string;
  account: string;
  account_name: string;
  payee: string;
  reference: string;
  note: string;
  status: "PENDING_APPROVAL" | "POSTED" | "REJECTED" | "REVERSED";
  requested_by_name: string;
  approved_by_name: string;
  approved_at: string | null;
  posted_at: string | null;
  rejection_reason: string;
  created_at: string;
};

export type IncomeCategory = {
  id: string;
  name: string;
  is_system: boolean;
  is_active: boolean;
};

export type Income = {
  id: string;
  number: string | null;
  branch: string;
  branch_name: string;
  business_date: string;
  category: string;
  category_name: string;
  amount: string;
  account: string;
  account_name: string;
  source: string;
  reference: string;
  note: string;
  status: "POSTED" | "REVERSED";
  posted_by_name: string;
  posted_at: string | null;
  created_at: string;
};

export type AccountLedgerEntry = {
  id: string;
  entry_type: string;
  amount_delta: string;
  reference: string;
  source_type: string;
  source_number: string;
  business_date: string;
  running_balance: string;
};

export type AccountLedgerResponse = {
  balance: string;
  count: number;
  results: AccountLedgerEntry[];
};
