export interface Goal {
  id: string;
  title: string;
  description: string | null;
  category: string | null;
  target_date: string | null;
  status: "active" | "completed" | "abandoned";
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  goal_id: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  priority: "low" | "medium" | "high";
  status: "pending" | "completed" | "skipped";
  is_daily_mission: boolean;
  created_at: string;
  updated_at: string;
}

export interface Habit {
  id: string;
  title: string;
  frequency: "daily" | "weekly";
  repeat_days: number[] | null;
  target_count_per_period: number;
  active: boolean;
  created_at: string;
  updated_at: string;
  current_streak: number;
  completed_today: boolean;
}

export interface Countdown {
  id: string;
  title: string;
  target_datetime: string;
  category: string | null;
  notes: string | null;
  priority: "low" | "medium" | "high";
  repeat_rule: "none" | "daily" | "weekly" | "monthly" | "yearly";
  notification_offsets_minutes: number[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TodayView {
  mission: Task | null;
  habits_due_today: Habit[];
  active_goals_count: number;
  active_countdown: Countdown | null;
}

export interface Conversation {
  id: string;
  title: string | null;
  mode: "friend" | "teacher" | "commander" | "coach" | "financial_guide" | "health_coach" | "adaptive";
  last_message_at: string | null;
  created_at: string;
}

export interface DietLog {
  id: string;
  meal_type: "breakfast" | "lunch" | "dinner" | "snack";
  description: string;
  calories: number | null;
  protein_grams: number | null;
  logged_at: string;
  notes: string | null;
}

export interface WaterLog {
  id: string;
  amount_ml: number;
  logged_at: string;
}

export interface SleepLog {
  id: string;
  sleep_date: string;
  bedtime: string | null;
  wake_time: string | null;
  duration_minutes: number | null;
  quality: number | null;
  notes: string | null;
}

export interface WorkoutLog {
  id: string;
  activity_type: string;
  duration_minutes: number;
  intensity: "low" | "medium" | "high";
  logged_at: string;
  notes: string | null;
}

export interface MoodLog {
  id: string;
  mood: "very_low" | "low" | "neutral" | "good" | "great";
  stress_level: number | null;
  journal_entry: string | null;
  logged_at: string;
}

export interface HealthTodaySummary {
  water_ml_total: number;
  meals_logged: DietLog[];
  calories_total: number | null;
  last_night_sleep: SleepLog | null;
  workouts_today: WorkoutLog[];
  latest_mood_today: MoodLog | null;
}

export interface Income {
  id: string;
  source: string;
  amount: number;
  frequency: "one_time" | "weekly" | "biweekly" | "monthly" | "yearly";
  received_at: string;
  notes: string | null;
}

export interface Expense {
  id: string;
  category: string;
  description: string;
  amount: number;
  frequency: "one_time" | "weekly" | "biweekly" | "monthly" | "yearly";
  spent_at: string;
  notes: string | null;
}

export interface Budget {
  id: string;
  category: string;
  monthly_limit: number;
}

export interface BudgetStatus {
  category: string;
  monthly_limit: number;
  spent_this_month: number;
  remaining: number;
}

export interface FinancialGoal {
  id: string;
  title: string;
  goal_type: "savings" | "debt_payoff";
  target_amount: number;
  current_amount: number;
  target_date: string | null;
  status: "active" | "completed" | "abandoned";
  notes: string | null;
}

export interface FinanceSummary {
  estimated_monthly_income: number;
  estimated_recurring_monthly_expenses: number;
  income_logged_this_month: number;
  expenses_logged_this_month: number;
  budgets: BudgetStatus[];
  active_goals: FinancialGoal[];
}

export interface AffordabilityResult {
  requested_amount: number;
  estimated_monthly_income: number;
  estimated_recurring_monthly_expenses: number;
  expenses_logged_this_month: number;
  estimated_available_this_month: number | null;
  likely_affordable: boolean | null;
  assumptions: string[];
  caveats: string[];
}

export interface Prediction {
  id: string;
  prediction_type: "smoking_risk" | "habit_adherence";
  predicted_probability: number | null;
  confidence: "no_data" | "baseline_low_data" | "model_limited_data" | "model";
  explanation: string;
  created_at: string;
}

export interface PredictionFeedback {
  id: string;
  prediction_id: string;
  actual_outcome: boolean;
  recorded_at: string;
}

export interface ModelVersion {
  id: string;
  prediction_type: string;
  version: number;
  algorithm: string;
  training_sample_count: number;
  training_accuracy: number | null;
  trained_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  is_fallback: boolean;
  created_at: string;
}

export interface MessageExchange {
  user_message: Message;
  assistant_message: Message;
}

export interface SmokingEvent {
  id: string;
  trigger: string;
  craving_intensity: number;
  stress_level: number | null;
  context: string | null;
  outcome: "resisted" | "alternative_used" | "smoked";
  alternative_action: string | null;
  reflection_note: string | null;
  notes: string | null;
  occurred_at: string;
}

export interface DetectedPattern {
  pattern_type: "trigger" | "time_of_day" | "trigger_and_time_of_day";
  description: string;
  occurrences: number;
  window_days: number;
}

export interface SmokingSummary {
  window_days: number;
  total_events: number;
  smoked_count: number;
  resisted_count: number;
  alternative_used_count: number;
  smoke_free_streak_days: number | null;
  last_event: SmokingEvent | null;
  detected_patterns: DetectedPattern[];
}

export type NotificationType = "scheduled" | "contextual" | "behavioral" | "deadline" | "habit_intervention";

export interface NotificationItem {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  source_type: string | null;
  source_id: string | null;
  trigger_at: string;
  status: "pending" | "delivered" | "dismissed" | "actioned";
  created_at: string;
  delivered_at: string | null;
  actioned_at: string | null;
}

export interface NotificationPreferences {
  quiet_hours_start_hour: number | null;
  quiet_hours_end_hour: number | null;
  max_per_day: number;
  enabled_types: Record<NotificationType, boolean>;
}

export interface VoiceCall {
  id: string;
  conversation_id: string;
  language: "en" | "te" | "mixed";
  status: "in_progress" | "completed";
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  recording_enabled: boolean;
  recording_local_reference: string | null;
  recording_duration_seconds: number | null;
}

