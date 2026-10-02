import { useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import TrackLogo from "../../components/content/TrackLogo.jsx";

function formatDate(iso) {
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

function GhostlineMark({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Ghostline"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="gl-mark-fill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--cert-accent, #8fb9a8)" stopOpacity="0.95" />
          <stop offset="100%" stopColor="var(--accent-2, #a3b8d4)" stopOpacity="0.9" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#gl-mark-fill)" opacity="0.16" />
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

function CertificateCard({ cert }) {
  function printCert() {
    window.print();
  }

  const issued = formatDate(cert.issued_on || cert.completed_at);
  const statusLabel = cert.earned ? "Official award" : "Preview only";

  return (
    <div className="certificate-wrap">
      <article
        className={`certificate-frame ${cert.watermarked ? "is-preview" : "is-earned"}`}
        style={{ "--cert-accent": cert.track_color || "var(--accent)" }}
        aria-label={`${cert.title} for ${cert.learner_name}`}
      >
        <div className="certificate-border" aria-hidden="true" />
        <div className="certificate-border-inner" aria-hidden="true" />
        <CornerOrnament position="tl" />
        <CornerOrnament position="tr" />
        <CornerOrnament position="bl" />
        <CornerOrnament position="br" />

        {cert.watermarked ? (
          <div className="certificate-watermark" aria-hidden="true">
            <span>Preview</span>
            <span>Complete the path to unlock</span>
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
        <h1 className="certificate-title">{cert.title}</h1>
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
            <p className="certificate-meta-label">{cert.earned ? "Date of completion" : "Progress"}</p>
            <p className="certificate-meta-value">
              {cert.earned ? issued : `${cert.completed} of ${cert.total} exercises`}
            </p>
          </div>
          <div>
            <p className="certificate-meta-label">Credential</p>
            <p className="certificate-meta-value">
              {cert.earned ? "Certificate of completion" : "Watermarked preview"}
            </p>
          </div>
          <div>
            <p className="certificate-meta-label">Certificate ID</p>
            <p className="certificate-meta-value certificate-code">
              {cert.code || "Unlocks on completion"}
            </p>
          </div>
        </div>

        <footer className="certificate-footer-row">
          <div className="certificate-sign-block">
            <p className="certificate-sign-line" aria-hidden="true" />
            <p className="certificate-signer">{cert.signer_name}</p>
            <p className="certificate-signer-title">{cert.signer_title}</p>
          </div>

          <div
            className={`certificate-seal ${cert.earned ? "is-earned" : ""}`}
            aria-hidden="true"
          >
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
                {cert.earned ? "AWARDED" : "PREVIEW"}
              </text>
              <text
                x="60"
                y="86"
                textAnchor="middle"
                className="certificate-seal-text"
                fill="currentColor"
              >
                {cert.track_slug.toUpperCase()}
              </text>
            </svg>
          </div>

          <div className="certificate-sign-block certificate-sign-block-right">
            <p className="certificate-sign-line" aria-hidden="true" />
            <p className="certificate-signer">{cert.earned ? issued : "Pending"}</p>
            <p className="certificate-signer-title">Date issued</p>
          </div>
        </footer>

        <p className="certificate-footer">{cert.footer}</p>
        {cert.earned ? (
          <p className="certificate-verify">
            Verify with certificate ID <span className="certificate-code">{cert.code}</span>
          </p>
        ) : (
          <p className="certificate-verify">
            Finish the path to remove the watermark and receive your official ID.
          </p>
        )}
      </article>

      <div className="certificate-actions no-print">
        {cert.earned ? (
          <button type="button" className="btn-primary" onClick={printCert}>
            Print / save PDF
          </button>
        ) : (
          <p className="text-sm text-muted">
            Finish every published exercise on this path to remove the watermark and unlock your
            certificate ID.
          </p>
        )}
        <Link to={`/learn/tracks/${cert.track_slug}`} className="btn-secondary">
          Back to {cert.track_name}
        </Link>
        <Link to="/certificates" className="btn-ghost">
          All certificates
        </Link>
      </div>
    </div>
  );
}

export function CertificateDetailPage() {
  const { slug } = useParams();
  const { user } = useOutletContext();
  const [cert, setCert] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api(`/api/certificates/${slug}`)
      .then((data) => {
        if (!cancelled) {
          setCert(data);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [slug, user?.first_name, user?.last_name]);

  if (error) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <p className="text-sm text-error">{error}</p>
        <Link to="/certificates" className="mt-4 inline-block text-sm text-accent">
          Back to certificates
        </Link>
      </section>
    );
  }
  if (!cert) {
    return <p className="text-sm text-muted">Loading certificate…</p>;
  }
  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)] sm:p-8">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent no-print">
        {cert.earned ? "Official certificate" : "Certificate preview"}
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight no-print">{cert.track_name}</h1>
      <div className="mt-6">
        <CertificateCard cert={cert} />
      </div>
    </section>
  );
}

export default function CertificatesPage() {
  const { user } = useOutletContext();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/certificates")
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user?.first_name, user?.last_name]);

  if (error) {
    return <p className="text-sm text-error">{error}</p>;
  }
  if (!data) {
    return <p className="text-sm text-muted">Loading certificates…</p>;
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)] sm:p-8">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Recognition</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Certificates</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Certificates use your profile name ({data.learner_name}). Preview is watermarked; the
        official award unlocks when every published exercise on a path is done.
      </p>
      {!data.enabled ? (
        <p className="mt-6 text-sm text-muted">Certificates are turned off on this server.</p>
      ) : null}
      {data.enabled && data.certificates.length === 0 ? (
        <p className="mt-6 text-sm text-muted">No tracks yet. Ask your admin for access.</p>
      ) : null}
      {data.enabled && data.certificates.length > 0 ? (
        <ul className="mt-6 grid gap-4">
          {data.certificates.map((item) => (
            <li key={item.track_slug} className="certificate-list-item">
              <div className="certificate-list-mark" aria-hidden="true">
                <GhostlineMark />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-text">{item.track_name}</p>
                <p className="mt-1 text-sm text-muted">
                  {item.earned
                    ? `Official award · ID ${item.code}`
                    : `${item.completed}/${item.total} exercises · watermarked preview`}
                </p>
              </div>
              <Link
                to={`/certificates/${item.track_slug}`}
                className={item.earned ? "btn-primary" : "btn-secondary"}
              >
                {item.earned ? "View certificate" : "Preview"}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
