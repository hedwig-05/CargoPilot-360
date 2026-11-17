
import { useState, type FormEvent } from 'react'
import {
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Moon,
  Sun,
} from 'lucide-react'

interface LoginPageProps {
  onLogin: (email: string, password: string) => Promise<void>
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

function LoginPage({
  onLogin,
  theme,
  onToggleTheme,
}: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await onLogin(email.trim(), password)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to sign in. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-topbar">
        <div className="login-brand">
          <div className="login-brand-mark">
            <span>CP</span>
          </div>
          <div className="login-brand-copy">
            <strong>CargoPilot <span>360</span></strong>
            <small>LOGISTICS INTELLIGENCE</small>
          </div>
        </div>

        <button
          type="button"
          className="login-theme-button"
          onClick={onToggleTheme}
          aria-label="Toggle colour theme"
        >
          {theme === 'light' ? <Moon size={19} /> : <Sun size={19} />}
        </button>
      </div>

      <section className="login-content">
        <div className="login-card">
          <div className="login-heading">
            <span className="login-eyebrow">CARGOPILOT 360 WORKSPACE</span>
            <h1>Welcome back</h1>
            <p>Sign in to access your logistics operations workspace.</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field">
              <label htmlFor="login-email">Email address</label>
              <div className="login-input-wrapper">
                <Mail size={18} />
                <input
                  id="login-email"
                  type="email"
                  placeholder="Enter your email address"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="username"
                  required
                />
              </div>
            </div>

            <div className="login-field">
              <div className="login-password-label">
                <label htmlFor="login-password">Password</label>
              </div>

              <div className="login-input-wrapper">
                <LockKeyhole size={18} />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="login-error" role="alert">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="login-submit"
              disabled={loading}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <div className="login-security-note">
            <LockKeyhole size={15} />
            <span>Secure access to your operations workspace</span>
          </div>
        </div>
      </section>

      <footer className="login-footer">
        <span>CargoPilot 360</span>
        <span>Logistics intelligence. Connected operations.</span>
      </footer>
    </main>
  )
}

export default LoginPage
