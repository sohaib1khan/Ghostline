import { useId } from "react";
import TrackLogo from "../content/TrackLogo.jsx";

export const DEMO_CERTIFICATE = {
  title: "Certificate of Completion",
  subtitle: "This certifies that",
  learner_name: "Alex Rivera",
  body: "has successfully completed the Bash learning path.",
  track_slug: "bash",
  track_name: "Bash",
  track_color: "#8fb9a8",
  earned: true,
  watermarked: false,
  completed: 41,
  total: 41,
  issued_on: "2026-10-01",
  completed_at: "2026-10-01",
  code: "GL-BASH-DEMO4F2A",
  signer_name: "Ghostline",
  signer_title: "Typing-first practice",
  footer: "Keep typing. Keep the muscle memory.",
};

export function formatCertificateDate(iso) {
  if (!iso) {
    return "—";
  }
  const date = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function GhostlineMark({ className = "" }) {
  const gradientId = useId();
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Ghostline"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--cert-accent, #8fb9a8)" stopOpacity="0.95" />
          <stop offset="100%" stopColor="var(--accent-2, #a3b8d4)" stopOpacity="0.9" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill={`url(#${gradientId})`} opacity="0.16" />
      <rect
        x="6"
        y="6"
        width="52"
        height="52"
        rx="13"
        fill="none"
        stroke="var(--cert-accent, #8fb9a8)"
        strokeWidth="1.6"
      />
      <path
        d="M18 40V24h8.2c5.1 0 8.3 2.5 8.3 6.5 0 4.1-3.2 6.6-8.3 6.6H24v2.9H18zm6-8.4h1.8c2.1 0 3.4-1 3.4-2.6s-1.3-2.5-3.4-2.5H24v5.1zM38.2 40l6.8-16h6.1L58 40h-6.1l-1.1-2.9h-5.4L44.3 40h-6.1zm9.1-7.4h3.4l-1.7-4.5-1.7 4.5z"
        fill="var(--cert-accent, #8fb9a8)"
      />
    </svg>
  );
}

function CornerOrnament({ position }) {
  return (
    <svg
      className={`certificate-corner certificate-corner-${position}`}
      viewBox="0 0 48 48"
      aria-hidden="true"
    >
      <path
        d="M8 40V16c0-4.4 3.6-8 8-8h24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M14 40V20c0-3.3 2.7-6 6-6h20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.55"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
    </svg>
  );
}

/** Formal certificate document — used for earned awards, previews, and landing demos. */
export function CertificateDocument({
  cert,
  compact = false,
  forceWatermark = false,
  watermarkLabel = "Preview",
  watermarkHint = "Complete the path to unlock",
}) {
  const issued = formatCertificateDate(cert.issued_on || cert.completed_at);
  const watermarked = forceWatermark || cert.watermarked;
  const earned = !watermarked && cert.earned;
  const statusLabel = earned ? "Official award" : "Sample preview";

  return (
    <article
      className={`certificate-frame ${watermarked ? "is-preview" : "is-earned"}${
        compact ? " certificate-frame-compact" : ""
      }`}
      style={{ "--cert-accent": cert.track_color || "var(--accent)" }}
      aria-label={`${cert.title} for ${cert.learner_name}`}
    >
      <div className="certificate-border" aria-hidden="true" />
      <div className="certificate-border-inner" aria-hidden="true" />
      <CornerOrnament position="tl" />
      <CornerOrnament position="tr" />
      <CornerOrnament position="bl" />
      <CornerOrnament position="br" />

      {watermarked ? (
        <div className="certificate-watermark" aria-hidden="true">
          <span>{watermarkLabel}</span>
          <span>{watermarkHint}</span>
        </div>
      ) : null}

      <header className="certificate-header">
        <GhostlineMark className="certificate-logo" />
        <div className="certificate-header-copy">
          <p className="certificate-brand">Ghostline</p>
          <p className="certificate-brand-tag">Typing-first learning path</p>
        </div>
        <div className="certificate-status-pill">{statusLabel}</div>
      </header>

      <div className="certificate-rule" aria-hidden="true">
        <span />
        <span className="certificate-rule-diamond" />
        <span />
      </div>

      <p className="certificate-presented">Presented by Ghostline</p>
      <h2 className="certificate-title">{cert.title}</h2>
      <p className="certificate-subtitle">{cert.subtitle}</p>
      <p className="certificate-name">{cert.learner_name}</p>
      <p className="certificate-body">{cert.body}</p>

      <div className="certificate-course-chip">
        <TrackLogo
          slug={cert.track_slug}
          color={cert.track_color || "var(--accent)"}
          size="md"
          title={cert.track_name}
        />
        <div>
          <p className="certificate-meta-label">Learning path</p>
          <p className="certificate-meta-value">{cert.track_name}</p>
        </div>
      </div>

      <div className="certificate-meta">
        <div>
          <p className="certificate-meta-label">{earned ? "Date of completion" : "Progress"}</p>
          <p className="certificate-meta-value">
            {earned ? issued : `${cert.completed} of ${cert.total} exercises`}
          </p>
        </div>
        <div>
          <p className="certificate-meta-label">Credential</p>
          <p className="certificate-meta-value">
            {earned ? "Certificate of completion" : "Sample / watermarked"}
          </p>
        </div>
        <div>
          <p className="certificate-meta-label">Certificate ID</p>
          <p className="certificate-meta-value certificate-code">
            {earned || cert.code ? cert.code : "Unlocks on completion"}
          </p>
        </div>
      </div>

      <footer className="certificate-footer-row">
        <div className="certificate-sign-block">
          <p className="certificate-sign-line" aria-hidden="true" />
          <p className="certificate-signer">{cert.signer_name}</p>
          <p className="certificate-signer-title">{cert.signer_title}</p>
        </div>

        <div className={`certificate-seal ${earned ? "is-earned" : ""}`} aria-hidden="true">
          <svg viewBox="0 0 120 120" className="certificate-seal-ring">
            <circle cx="60" cy="60" r="54" fill="none" stroke="currentColor" strokeWidth="2" />
            <circle
              cx="60"
              cy="60"
              r="46"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
              strokeDasharray="2 3"
              opacity="0.7"
            />
            <text
              x="60"
              y="44"
              textAnchor="middle"
              className="certificate-seal-text"
              fill="currentColor"
            >
              GHOSTLINE
            </text>
            <text
              x="60"
              y="68"
              textAnchor="middle"
              className="certificate-seal-mark"
              fill="currentColor"
            >
              {earned ? "AWARDED" : "SAMPLE"}
            </text>
            <text
              x="60"
              y="86"
              textAnchor="middle"
              className="certificate-seal-text"
              fill="currentColor"
            >
              {(cert.track_slug || "path").toUpperCase()}
            </text>
          </svg>
        </div>

        <div className="certificate-sign-block certificate-sign-block-right">
          <p className="certificate-sign-line" aria-hidden="true" />
          <p className="certificate-signer">{earned ? issued : "Pending"}</p>
          <p className="certificate-signer-title">Date issued</p>
        </div>
      </footer>

      <p className="certificate-footer">{cert.footer}</p>
      {earned ? (
        <p className="certificate-verify">
          Verify with certificate ID <span className="certificate-code">{cert.code}</span>
        </p>
      ) : (
        <p className="certificate-verify">
          Sign in, finish a path, and your real name unlocks the official award.
        </p>
      )}
    </article>
  );
}
