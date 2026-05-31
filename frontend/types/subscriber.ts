export type SubscriberSubscription = {
  status: string;
  plan_type: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
};

export type SubscriberMeResponse = {
  authenticated: boolean;
  has_active_subscription: boolean;
  access_level: string;
  email: string;
  subscription: SubscriberSubscription | null;
};

export type SubscriberAccessResponse = {
  can_access_full_content: boolean;
  reason: string;
};
