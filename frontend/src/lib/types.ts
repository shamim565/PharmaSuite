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

export type RolePermissionEntry = {
  code: string;
  module: string;
  label: string;
  effect: "ALLOW" | "DENY";
};

export type PermissionItem = {
  id: string;
  code: string;
  module: string;
  action: string;
  label: string;
  is_sensitive: boolean;
};

export type PermissionCatalog = Record<string, PermissionItem[]>;

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
  totp_enabled: boolean;
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
  totp_enabled: boolean;
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
  retail_price: string | null;
  wholesale_price: string | null;
  custom_price: string | null;
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

export type StockTransferItem = {
  id: string;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch: string;
  batch_number: string;
  qty: string;
  pool: "SALEABLE" | "PROMO" | "QUARANTINE";
  unit_cost: string;
};

export type StockTransfer = {
  id: string;
  number: string | null;
  from_branch: string;
  from_branch_name: string;
  to_branch: string;
  to_branch_name: string;
  business_date: string;
  status: "DRAFT" | "CONFIRMED";
  notes: string;
  requested_by_name: string;
  confirmed_by_name: string;
  confirmed_at: string | null;
  created_at: string;
  items: StockTransferItem[];
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
  location: string;
  status: BatchStatus;
  notes: string;
  days_to_expiry: number | null;
  created_at: string;
};

export type WarehouseLocation = {
  id: string;
  branch: string;
  branch_name: string;
  zone: string;
  rack: string;
  bin: string;
  label: string;
  is_active: boolean;
  notes: string;
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
  confirmed_by_name: string;
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

export type PurchaseOrderItem = {
  id: string;
  line_no: number;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  qty_ordered: string;
  qty_received: string;
  qty_pending: string;
  is_fully_received: boolean;
  unit_cost: string;
  line_discount: string;
  vat_rate: string;
  vat_amount: string;
  line_net: string;
  notes: string;
};

export type PurchaseOrder = {
  id: string;
  number: string | null;
  branch: string;
  branch_name: string;
  supplier: string;
  supplier_name: string;
  business_date: string;
  expected_delivery_date: string | null;
  status:
    | "DRAFT"
    | "SUBMITTED"
    | "APPROVED"
    | "PARTIALLY_RECEIVED"
    | "FULLY_RECEIVED"
    | "CANCELLED";
  subtotal: string;
  discount_total: string;
  vat_total: string;
  grand_total: string;
  notes: string;
  submitted_at: string | null;
  submitted_by_name: string;
  approved_at: string | null;
  approved_by_name: string;
  cancel_reason: string;
  cancelled_by_name: string;
  fulfilled_by: string | null;
  fulfilled_by_number: string;
  created_at: string;
  items: PurchaseOrderItem[];
};

export type DeliveryChallanItem = {
  id: string;
  line_no: number;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch: string | null;
  batch_number: string;
  qty: string;
  notes: string;
};

export type DeliveryChallan = {
  id: string;
  number: string | null;
  branch: string;
  branch_name: string;
  customer: string;
  customer_name: string;
  customer_code: string;
  invoice: string | null;
  invoice_number: string;
  business_date: string;
  status: "PREPARED" | "DISPATCHED" | "DELIVERED" | "UNDELIVERED" | "CANCELLED";
  delivery_person: string;
  delivery_phone: string;
  vehicle_no: string;
  dispatched_at: string | null;
  dispatched_by_name: string;
  delivered_at: string | null;
  delivered_by_name: string;
  recipient_name: string;
  recipient_phone: string;
  notes: string;
  cancel_reason: string;
  created_at: string;
  items: DeliveryChallanItem[];
};

export type SalesTarget = {
  id: string;
  representative: string;
  representative_name: string;
  representative_code: string;
  branch: string | null;
  branch_name: string;
  fiscal_year: number;
  period_month: number;
  target_amount: string;
  target_collection: string;
  target_visits: number;
  achieved_sales: string;
  achieved_percent: number | null;
  notes: string;
  created_at: string;
};

export type InventoryDsiRow = {
  medicine: string;
  name: string;
  code: string;
  qty_on_hand: string;
  reorder_level: string;
  avg_daily_sales: string;
  total_sold_in_period: string;
  dsi: number | null;
  last_sale_date: string | null;
  days_since_sale: number | null;
  is_dead_stock: boolean;
  is_slow_mover: boolean;
};

export type InventoryDsiReport = {
  period_days: number;
  dead_days_threshold: number;
  slow_dsi_threshold: number;
  count: number;
  dead_stock_count: number;
  slow_mover_count: number;
  results: InventoryDsiRow[];
};

export type MarginAnalysisRow = {
  id: string;
  name: string;
  qty: string;
  gross: string;
  discount: string;
  net_revenue: string;
  cogs?: string;
  gross_profit?: string;
  gross_profit_pct?: number;
};

export type MarginAnalysisReport = {
  period: { date_from: string; date_to: string };
  group_by: string;
  has_cost_access: boolean;
  total_net_revenue: string;
  total_gross_profit: string | null;
  count: number;
  results: MarginAnalysisRow[];
};

export type RepPerformanceRow = {
  representative: string;
  name: string;
  code: string;
  rep_type: "SALES" | "MEDICAL";
  branch: string | null;
  branch_name: string;
  target_amount: string;
  actual_sales: string;
  achievement_pct: number | null;
  gap: string;
};

export type RepPerformanceReport = {
  fiscal_year: number;
  period_month: number;
  count: number;
  total_target: string;
  total_actual: string;
  results: RepPerformanceRow[];
};

export type CollectionEfficiencyRow = {
  customer: string;
  name: string;
  code: string;
  invoiced: string;
  collected: string;
  outstanding: string;
  efficiency_pct: number;
};

export type CollectionEfficiencyReport = {
  period: { date_from: string; date_to: string };
  kpi: {
    total_invoiced: string;
    total_collected: string;
    total_outstanding: string;
    collection_efficiency_pct: number;
  };
  count: number;
  results: CollectionEfficiencyRow[];
};

export type SupplierConcentrationRow = {
  supplier: string;
  name: string;
  total_spend: string;
  purchase_count: number;
  pct_of_total: number;
  cumulative_pct: number;
  high_dependency: boolean;
};

export type SupplierConcentrationReport = {
  period: { date_from: string; date_to: string };
  total_spend: string;
  supplier_count: number;
  high_dependency_count: number;
  results: SupplierConcentrationRow[];
};

export type ExceptionOverride = {
  type:
    | "CREDIT_OVERRIDE"
    | "FEFO_OVERRIDE"
    | "RX_OVERRIDE"
    | "PRICE_OVERRIDE"
    | "DUPLICATE_INVOICE";
  reason: string;
};

export type ExceptionReportRow = {
  document_type: "SALES_INVOICE" | "PURCHASE";
  document_id: string;
  document_number: string | null;
  business_date: string;
  branch: string;
  branch_name: string;
  customer?: string;
  customer_name?: string;
  supplier?: string;
  supplier_name?: string;
  grand_total: string;
  confirmed_by: string;
  confirmed_at: string;
  overrides: ExceptionOverride[];
};

export type ExceptionReport = {
  period: { date_from: string; date_to: string };
  total_exceptions: number;
  invoice_exceptions: number;
  purchase_exceptions: number;
  results: ExceptionReportRow[];
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
  credit_unlimited: boolean;
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
  medicine_rx_required: boolean;
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
  confirmed_by_name: string;
  cancel_reason: string;
  credit_override: boolean;
  credit_override_reason: string;
  fefo_override: boolean;
  fefo_override_reason: string;
  prescription_number: string;
  rx_override: boolean;
  rx_override_reason: string;
  delivered_at: string | null;
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
  page?: number;
  page_size?: number;
  next?: boolean;
  previous?: boolean;
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
  by_collector: {
    collector: string | null;
    collector_name: string;
    total: string;
    count: number;
  }[];
};

export type SalesReturnItem = {
  id: string;
  invoice_item: string | null;
  line_no: number | null;
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
  invoice: string | null;
  invoice_number: string | null;
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

export type ProfitLossPeriod = {
  period: { date_from: string; date_to: string };
  revenue: { sales_net: string; returns_net: string; net_revenue: string };
  cogs: string;
  gross_profit: string;
  gross_margin_pct: string | null;
  losses: {
    damage: string;
    expiry: string;
    adjustments_net: string;
    adjustment_reversals: string;
    total: string;
  };
  expenses: string;
  other_income: string;
  net_profit: string;
  reconciliation: {
    customer_ledger_delta: string;
    receipts: string;
    note: string;
  };
};

export type ProfitLossReport = {
  current: ProfitLossPeriod;
  previous: ProfitLossPeriod;
  comparison: {
    revenue_delta: string;
    revenue_delta_pct: string | null;
    net_profit_delta: string;
    net_profit_delta_pct: string | null;
  };
};

export type ValuationRow = {
  branch: string;
  branch_name: string;
  saleable_qty: string;
  saleable_value: string;
  quarantine_qty: string;
  quarantine_value: string;
  promo_qty: string;
  promo_value: string;
};

export type InventoryValuationReport = {
  count: number;
  total_value: string;
  results: ValuationRow[];
};

export type FinancialPositionReport = {
  receivables: string;
  payables: string;
  cash_position: string;
  accounts: {
    account: string;
    code: string;
    name: string;
    account_type: string;
    balance: string;
  }[];
  stock_value_saleable: string;
  stock_value_quarantine: string;
  net_working_position: string;
};

export type Territory = {
  id: string;
  name: string;
  parent: string | null;
  parent_name: string;
  territory_type: "REGION" | "AREA" | "TERRITORY";
  is_active: boolean;
};

export type Representative = {
  id: string;
  code: string;
  name: string;
  rep_type: "SALES" | "MEDICAL";
  phone: string;
  email: string;
  branch: string | null;
  branch_name: string;
  user: string | null;
  user_name: string;
  reports_to: string | null;
  reports_to_name: string;
  joined_at: string | null;
  is_active: boolean;
  notes: string;
};

export type RepresentativeAssignment = {
  id: string;
  representative: string;
  representative_name: string;
  entity_type: "CUSTOMER" | "DOCTOR" | "TERRITORY";
  entity_id: string;
  entity_label: string;
  effective_from: string;
  effective_to: string | null;
  is_primary: boolean;
};

export type Doctor = {
  id: string;
  code: string;
  name: string;
  gender: string;
  phones: string[];
  email: string;
  specialty: string;
  degrees: string;
  doctor_type: "CONSULTANT" | "GP" | "OTHER";
  registration_no: string | null;
  category: "A" | "B" | "C";
  potential_rating: string;
  territory: string | null;
  territory_name: string;
  visit_frequency_target: number | null;
  consent_note: string;
  notes: string;
  is_active: boolean;
  open_mapping_count: number;
  created_at: string;
};

export type DoctorMedicine = {
  id: string;
  doctor: string;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  priority: string;
  strength_note: string;
  effective_from: string;
  effective_to: string | null;
};

export type DoctorVisitSample = {
  id: string;
  medicine: string;
  medicine_name: string;
  medicine_code: string;
  batch: string;
  batch_number: string;
  qty: string;
  unit_cost: string;
  reversed: boolean;
  reversed_at: string | null;
};

export type DoctorVisit = {
  id: string;
  doctor: string;
  doctor_name: string;
  doctor_code: string;
  representative: string;
  representative_name: string;
  branch: string;
  branch_name: string;
  status: "PLANNED" | "COMPLETED" | "MISSED" | "CANCELLED";
  planned_date: string | null;
  visited_at: string | null;
  purpose: string;
  products_discussed: string[];
  outcome: string;
  next_visit_date: string | null;
  notes: string;
  missed_reason: string;
  cancel_reason: string;
  created_at: string;
  samples: DoctorVisitSample[];
};

export type VisitCoverageRow = {
  representative: string;
  representative_name: string;
  planned: number;
  completed: number;
  missed: number;
  cancelled: number;
  coverage_pct: number | null;
};

export type AttributionRow = {
  id: string | null;
  name: string;
  net_revenue: string;
  invoice_count: number;
};

export type AttributionReport = {
  period: { date_from: string; date_to: string };
  count: number;
  total_net_revenue: string;
  results: AttributionRow[];
};

export type DashboardWidgets = {
  period: { date_from: string; date_to: string; days: number };
  sales_trend: { date: string; revenue: string; invoices: number }[];
  top_items: { medicine: string; name: string; code: string; qty: string; revenue: string }[];
  top_customers: { customer: string; name: string; revenue: string; invoices: number }[];
  low_stock: {
    medicine: string;
    name: string;
    code: string;
    on_hand: string;
    reorder_level: string;
  }[];
  near_expiry: {
    medicine: string;
    batch_number: string;
    expiry_date: string;
    days_to_expiry: number;
    qty_on_hand: string;
  }[];
  medicine_count: number;
};

export type SalesSummaryReport = {
  period: { date_from: string; date_to: string };
  count: number;
  totals: { invoices: number; net_revenue: string; vat: string; grand_total: string };
  results: {
    date: string;
    invoices: number;
    net_revenue: string;
    vat: string;
    grand_total: string;
  }[];
};

export type PurchasesSummaryReport = {
  period: { date_from: string; date_to: string };
  count: number;
  totals: { purchases: number; net_cost: string; grand_total: string };
  results: {
    date: string;
    purchases: number;
    net_cost: string;
    vat: string;
    grand_total: string;
  }[];
};

export type SalesByItemReport = {
  period: { date_from: string; date_to: string };
  count: number;
  has_cost_access: boolean;
  results: {
    medicine: string;
    name: string;
    code: string;
    qty: string;
    gross: string;
    discount: string;
    net_revenue: string;
    cost?: string;
    gross_profit?: string;
  }[];
};

export type SalesByCustomerReport = {
  period: { date_from: string; date_to: string };
  count: number;
  results: {
    customer: string;
    name: string;
    code: string;
    invoices: number;
    net_revenue: string;
    paid: string;
    outstanding: string;
  }[];
};

export type AuditLogEntry = {
  id: string;
  actor: string | null;
  actor_name: string;
  actor_type: "USER" | "SYSTEM";
  branch: string | null;
  branch_name: string;
  entity_type: string;
  entity_id: string | null;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  request_id: string;
  ip: string | null;
  created_at: string;
};

export type SettingGroups = {
  groups: Record<string, Record<string, string | number | boolean>>;
};

export type FiscalPeriod = {
  id: string;
  fiscal_year: number;
  period_month: number;
  start_date: string;
  end_date: string;
  status: "OPEN" | "LOCKED";
  locked_by_name: string;
  locked_at: string | null;
  lock_reason: string;
  unlock_by_name: string;
  unlock_reason: string;
  checklist?: {
    pending_expenses: number;
    pending_adjustments: number;
    note: string;
  };
};

export type AppNotification = {
  id: string;
  type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  title: string;
  body: string;
  deep_link: string;
  payload: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
};

export type NotificationPreference = {
  category: string;
  label: string;
  enabled: boolean;
  email_enabled: boolean;
  sms_enabled: boolean;
};

export type NotificationPreferenceList = {
  results: NotificationPreference[];
};

export type NotificationList = {
  count: number;
  unread_count: number;
  results: AppNotification[];
};

export type AttachmentRow = {
  id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by_name: string;
  created_at: string;
};

export type Cheque = {
  id: string;
  direction: "RECEIVED" | "ISSUED";
  status: "PENDING_DEPOSIT" | "DEPOSITED" | "CLEARED" | "BOUNCED" | "PENDING" | "PAID" | "STOPPED";
  number: string;
  bank_name: string;
  bank_branch: string;
  amount: string;
  date_issued: string;
  date_deposited: string | null;
  date_cleared: string | null;
  date_bounced: string | null;
  date_paid: string | null;
  date_stopped: string | null;
  customer: string | null;
  customer_name: string;
  supplier: string | null;
  supplier_name: string;
  invoice: string | null;
  invoice_number: string;
  supplier_payment: string | null;
  supplier_payment_number: string;
  notes: string;
  created_at: string;
};

export type SearchResults = {
  results: {
    medicines: Array<{ id: string; code: string; name: string; selling_price: string }>;
    customers: Array<{ id: string; code: string; name: string; phone: string }>;
    suppliers: Array<{ id: string; code: string; name: string; phone: string }>;
    doctors: Array<{ id: string; code: string; name: string; category: string }>;
    invoices: Array<{
      id: string;
      number: string;
      customer__name: string;
      grand_total: string;
      lifecycle: string;
    }>;
    purchases: Array<{
      id: string;
      number: string;
      supplier__name: string;
      grand_total: string;
      lifecycle: string;
    }>;
  };
};

export type DoctorChamber = {
  id: string;
  doctor: string;
  name: string;
  address: string;
  visiting_hours: string;
};
