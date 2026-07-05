export type BillingPlan = 'monthly' | 'annual';

export type CheckoutRequest = {
  plan: BillingPlan;
};

export type CheckoutResponse = {
  checkout_url: string;
};

export type BillingStatusResponse = {
  has_active_access: boolean;
  subscription_status: string | null;
  plan_type: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
};

export type CustomerPortalResponse = {
  portal_url: string;
};
