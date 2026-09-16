import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../store/AuthContext";
import { ApiError } from "../../services/apiClient";

export function LoginScreen() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t("auth.invalidCredentials"));
      } else {
        setError(t("common.somethingWentWrong"));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-screen">
      <h1 className="auth-screen__title">{t("auth.loginTitle")}</h1>

      <form onSubmit={handleSubmit} className="auth-screen__form" noValidate>
        <label className="field">
          <span className="field__label">{t("auth.emailLabel")}</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label className="field">
          <span className="field__label">{t("auth.passwordLabel")}</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        {error && (
          <p role="alert" className="field-error">
            {error}
          </p>
        )}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? t("common.loading") : t("auth.loginAction")}
        </button>
      </form>

      <Link to="/register" className="auth-screen__switch">
        {t("auth.switchToRegister")}
      </Link>
    </main>
  );
}
