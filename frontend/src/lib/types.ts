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

export type Medicine = {
  id: string;
  code: string;
  name: string;
  generic_name: string;
  manufacturer: string;
  category: string;
  strength: string;
  dosage_form: string;
  unit: string;
  purchase_price: string;
  selling_price: string;
  mrp: string;
  vat_rate: string;
  reorder_level: string;
  is_active: boolean;
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
