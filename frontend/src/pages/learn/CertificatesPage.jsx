import { useEffect, useRef, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { api } from "../../api/client.js";

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

function CertificateCard({ cert }) {
  const frame = useRef(null);

  function printCert() {
    window.print();
  }

  return (
    <div className="certificate-wrap">
      <div
        ref={frame}
        className={`certificate-frame ${cert.watermarked ? "is-preview" : "is-earned"}`}
        style={{ "--cert-accent": cert.track_color || "var(--accent)" }}
      >
        {cert.watermarked ? (
          <div className="certificate-watermark" aria-hidden="true">
            <span>Preview</span>
            <span>Complete the path to unlock</span>
          </div>
        ) : null}
        <p className="certificate-brand">Ghostline</p>
        <h1 className="certificate-title">{cert.title}</h1>
        <p className="certificate-subtitle">{cert.subtitle}</p>
        <p className="certificate-name">{cert.learner_name}</p>
        <p className="certificate-body">{cert.body}</p>
        <div className="certificate-meta">
          <div>
            <p className="certificate-meta-label">Course</p>
            <p className="certificate-meta-value">{cert.track_name}</p>
          </div>
          <div>
            <p className="certificate-meta-label">{cert.earned ? "Completed" : "Progress"}</p>
            <p className="certificate-meta-value">
              {cert.earned
                ? formatDate(cert.issued_on || cert.completed_at)
                : `${cert.completed}/${cert.total} exercises`}
            </p>
          </div>
          {cert.code ? (
            <div>
              <p className="certificate-meta-label">Certificate ID</p>
              <p className="certificate-meta-value certificate-code">{cert.code}</p>
            </div>
          ) : null}
        </div>
        <div className="certificate-sign">
          <p className="certificate-signer">{cert.signer_name}</p>
          <p className="certificate-signer-title">{cert.signer_title}</p>
        </div>
        <p className="certificate-footer">{cert.footer}</p>
      </div>
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
        {cert.earned ? "Earned certificate" : "Certificate preview"}
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight no-print">
        {cert.track_name}
      </h1>
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
        Certificates use your profile name ({data.learner_name}). You can preview a watermarked
        version anytime; the full certificate unlocks when every published exercise on a path is
        done.
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
              <div className="min-w-0 flex-1">
                <p className="font-medium text-text">{item.track_name}</p>
                <p className="mt-1 text-sm text-muted">
                  {item.earned
                    ? `Completed · ID ${item.code}`
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
