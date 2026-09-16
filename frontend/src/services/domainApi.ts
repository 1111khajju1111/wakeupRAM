import { apiClient } from "./apiClient";
import type {
  AffordabilityResult,
  Budget,
  Conversation,
  Countdown,
  DietLog,
  Expense,
  FinancialGoal,
  FinanceSummary,
  Goal,
  Habit,
  HealthTodaySummary,
  Income,
  Message,
  MessageExchange,
  MoodLog,
  ModelVersion,
  NotificationItem,
  NotificationPreferences,
  Prediction,
  PredictionFeedback,
  SleepLog,
  SmokingEvent,
  SmokingSummary,
  Task,
  TodayView,
  VoiceCall,
  WaterLog,
  WorkoutLog,
} from "../types/domain";

export const goalsApi = {
  list: (status?: Goal["status"]) =>
    apiClient.get<Goal[]>(`/api/v1/goals${status ? `?status=${status}` : ""}`),
  create: (data: { title: string; description?: string; category?: string; target_date?: string }) =>
    apiClient.post<Goal>("/api/v1/goals", data),
  update: (id: string, data: Partial<Pick<Goal, "title" | "description" | "category" | "status">>) =>
    apiClient.patch<Goal>(`/api/v1/goals/${id}`, data),
  remove: (id: string) => apiClient.delete<void>(`/api/v1/goals/${id}`),
};

export const tasksApi = {
  list: (params?: { due_date?: string; status?: Task["status"] }) => {
    const query = new URLSearchParams();
    if (params?.due_date) query.set("due_date", params.due_date);
    if (params?.status) query.set("status", params.status);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<Task[]>(`/api/v1/tasks${suffix}`);
  },
  create: (data: {
    title: string;
    description?: string;
    goal_id?: string;
    due_date?: string;
    priority?: Task["priority"];
    is_daily_mission?: boolean;
  }) => apiClient.post<Task>("/api/v1/tasks", data),
  update: (id: string, data: Partial<Task>) =>
  apiClient.patch<Task>(`/api/v1/tasks/${id}`, data),
  logAction: (id: string, action: "completed" | "skipped" | "rescheduled", notes?: string) =>
    apiClient.post<Task>(`/api/v1/tasks/${id}/logs`, { action, notes }),
};

export const habitsApi = {
  list: (activeOnly = false) => apiClient.get<Habit[]>(`/api/v1/habits?active_only=${activeOnly}`),
  create: (data: { title: string; frequency?: Habit["frequency"]; repeat_days?: number[] }) =>
    apiClient.post<Habit>("/api/v1/habits", data),
  logCompletion: (id: string, notes?: string) =>
    apiClient.post(`/api/v1/habits/${id}/logs`, { notes }),
};

export const todayApi = {
  get: () => apiClient.get<TodayView>("/api/v1/today"),
};

export const healthApi = {
  today: () => apiClient.get<HealthTodaySummary>("/api/v1/health/today"),

  logDiet: (data: {
    meal_type: DietLog["meal_type"];
    description: string;
    calories?: number;
    protein_grams?: number;
    notes?: string;
  }) => apiClient.post<DietLog>("/api/v1/health/diet", data),
  listDiet: () => apiClient.get<DietLog[]>("/api/v1/health/diet"),

  logWater: (amount_ml: number) => apiClient.post<WaterLog>("/api/v1/health/water", { amount_ml }),

  // Upsert keyed on sleep_date — calling this again for the same night
  // updates that night's entry rather than creating a second one.
  logSleep: (data: {
    sleep_date: string;
    bedtime?: string;
    wake_time?: string;
    duration_minutes?: number;
    quality?: number;
    notes?: string;
  }) => apiClient.post<SleepLog>("/api/v1/health/sleep", data),

  logWorkout: (data: {
    activity_type: string;
    duration_minutes: number;
    intensity?: WorkoutLog["intensity"];
    notes?: string;
  }) => apiClient.post<WorkoutLog>("/api/v1/health/workouts", data),

  logMood: (data: { mood: MoodLog["mood"]; stress_level?: number; journal_entry?: string }) =>
    apiClient.post<MoodLog>("/api/v1/health/mood", data),
};

export const financeApi = {
  summary: () => apiClient.get<FinanceSummary>("/api/v1/finance/summary"),

  checkAffordability: (amount: number, description?: string) =>
    apiClient.post<AffordabilityResult>("/api/v1/finance/affordability", { amount, description }),

  logIncome: (data: {
    source: string;
    amount: number;
    frequency?: Income["frequency"];
    received_at: string;
    notes?: string;
  }) => apiClient.post<Income>("/api/v1/finance/income", data),
  listIncome: () => apiClient.get<Income[]>("/api/v1/finance/income"),

  logExpense: (data: {
    category: string;
    description: string;
    amount: number;
    frequency?: Expense["frequency"];
    spent_at: string;
    notes?: string;
  }) => apiClient.post<Expense>("/api/v1/finance/expenses", data),
  listExpenses: () => apiClient.get<Expense[]>("/api/v1/finance/expenses"),

  // Upsert keyed on category — calling this again for a category already
  // budgeted updates the limit rather than creating a second budget.
  setBudget: (category: string, monthly_limit: number) =>
    apiClient.post<Budget>("/api/v1/finance/budgets", { category, monthly_limit }),
  listBudgets: () => apiClient.get<Budget[]>("/api/v1/finance/budgets"),

  createGoal: (data: {
    title: string;
    goal_type?: FinancialGoal["goal_type"];
    target_amount: number;
    current_amount?: number;
    target_date?: string;
    notes?: string;
  }) => apiClient.post<FinancialGoal>("/api/v1/finance/goals", data),
  listGoals: () => apiClient.get<FinancialGoal[]>("/api/v1/finance/goals"),
  updateGoal: (id: string, data: Partial<Pick<FinancialGoal, "current_amount" | "status">>) =>
    apiClient.patch<FinancialGoal>(`/api/v1/finance/goals/${id}`, data),
};

export const conversationsApi = {
  list: () => apiClient.get<Conversation[]>("/api/v1/conversations"),
  create: (mode?: Conversation["mode"]) =>
    apiClient.post<Conversation>("/api/v1/conversations", mode ? { mode } : {}),
  listMessages: (conversationId: string) =>
    apiClient.get<Message[]>(`/api/v1/conversations/${conversationId}/messages`),
  sendMessage: (conversationId: string, content: string) =>
    apiClient.post<MessageExchange>(`/api/v1/conversations/${conversationId}/messages`, { content }),
};

export const smokingApi = {
  summary: () => apiClient.get<SmokingSummary>("/api/v1/smoking/summary"),

  logEvent: (data: {
    trigger: string;
    craving_intensity: number;
    stress_level?: number;
    context?: string;
    outcome: SmokingEvent["outcome"];
    alternative_action?: string;
    notes?: string;
  }) => apiClient.post<SmokingEvent>("/api/v1/smoking/events", data),
  listEvents: () => apiClient.get<SmokingEvent[]>("/api/v1/smoking/events"),

  // Adding a reflection afterward — the no-shame, understand-and-learn step
  // — never rewrites what was originally logged.
  addReflection: (id: string, reflection_note: string) =>
    apiClient.patch<SmokingEvent>(`/api/v1/smoking/events/${id}`, { reflection_note }),
};

export const predictionsApi = {
  predictSmokingRisk: (data: { trigger: string; craving_intensity: number; stress_level?: number }) =>
    apiClient.post<Prediction>("/api/v1/predictions/smoking-risk", data),

  predictHabitAdherence: (habitId: string) =>
    apiClient.post<Prediction>(`/api/v1/predictions/habit-adherence/${habitId}`, {}),

  list: (predictionType?: Prediction["prediction_type"]) =>
    apiClient.get<Prediction[]>(
      predictionType ? `/api/v1/predictions?prediction_type=${predictionType}` : "/api/v1/predictions"
    ),

  listModelVersions: () => apiClient.get<ModelVersion[]>("/api/v1/predictions/model-versions"),

  giveFeedback: (predictionId: string, actual_outcome: boolean) =>
    apiClient.post<PredictionFeedback>(`/api/v1/predictions/${predictionId}/feedback`, { actual_outcome }),
};

export const countdownsApi = {
  list: (activeOnly = false) => apiClient.get<Countdown[]>(`/api/v1/countdowns?active_only=${activeOnly}`),
  create: (data: {
    title: string;
    target_datetime: string;
    category?: string;
    notes?: string;
    priority?: Countdown["priority"];
    repeat_rule?: Countdown["repeat_rule"];
    notification_offsets_minutes?: number[];
  }) => apiClient.post<Countdown>("/api/v1/countdowns", data),
  update: (
    id: string,
    data: Partial<
      Pick<
        Countdown,
        "title" | "target_datetime" | "category" | "notes" | "priority" | "repeat_rule" | "is_active"
      >
    >,
  ) => apiClient.patch<Countdown>(`/api/v1/countdowns/${id}`, data),
  remove: (id: string) => apiClient.delete<void>(`/api/v1/countdowns/${id}`),
};

export const notificationsApi = {
  list: (status?: NotificationItem["status"]) =>
    apiClient.get<NotificationItem[]>(`/api/v1/notifications${status ? `?status=${status}` : ""}`),
  refresh: () => apiClient.post<NotificationItem[]>("/api/v1/notifications/refresh", {}),
  updateStatus: (id: string, status: "delivered" | "dismissed" | "actioned") =>
    apiClient.patch<NotificationItem>(`/api/v1/notifications/${id}`, { status }),
  getPreferences: () => apiClient.get<NotificationPreferences>("/api/v1/notifications/preferences"),
  updatePreferences: (data: Partial<NotificationPreferences>) =>
    apiClient.patch<NotificationPreferences>("/api/v1/notifications/preferences", data),
};

export const voiceApi = {
  tts: (text: string, language: "en" | "te" | "mixed") =>
    apiClient.blob("/api/v1/voice/tts", {
      method: "POST",
      body: JSON.stringify({ text, language }),
      headers: { "Content-Type": "application/json" },
    }),
};

export const callsApi = {
  start: (data: { language?: VoiceCall["language"]; recording_enabled?: boolean; title?: string }) =>
    apiClient.post<VoiceCall>("/api/v1/calls", data),
  end: (id: string, data: { recording_local_reference?: string; recording_duration_seconds?: number }) =>
    apiClient.post<VoiceCall>(`/api/v1/calls/${id}/end`, data),
  list: () => apiClient.get<VoiceCall[]>("/api/v1/calls"),
  get: (id: string) => apiClient.get<VoiceCall>(`/api/v1/calls/${id}`),
};
