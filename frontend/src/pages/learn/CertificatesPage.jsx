import { useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import {
  CertificateDocument,
  GhostlineMark,
} from "../../components/certificates/CertificateDocument.jsx";

function ProgressMeter({ label, completed, total, percent }) {
  const safeTotal = total || 0;
  const safeDone = completed || 0;
  const pct = percent ?? (safeTotal ? Math.round((safeDone / safeTotal) * 100) : 0);
  return (
    <div className="cert-meter">
      <div className="cert-meter-row">
        <span>{label}</span>
        <span className="font-mono">
          {safeDone}/{safeTotal || "—"} · {pct}%
        </span>
      </div>
      <div className="home-progress" aria-hidden>
        <div className="home-progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function CertificateCard({ cert }) {
  function printCert() {
    window.print();
  }

  return (
    <div className="certificate-wrap">
      <CertificateDocument cert={cert} />
      <div className="certificate-actions no-print">
        {cert.earned ? (
          <button type="button" className="btn-primary" onClick={printCert}>
            Print / save PDF
          </button>
        ) : (
          <div className="cert-unlock-panel">
            <p className="text-base font-medium text-text">
              Overall completion {cert.percent ?? 0}% — finish the path to unlock your ID
            </p>
            <ProgressMeter
              label="Exercises"
              completed={cert.exercises_completed ?? cert.completed}
              total={cert.exercises_total ?? cert.total}
              percent={cert.exercises_percent}
            />
            {(cert.bosses_total ?? 0) > 0 ? (
              <ProgressMeter
                label="Module bosses"
                completed={cert.bosses_completed}
                total={cert.bosses_total}
                percent={cert.bosses_percent}
              />
            ) : null}
            <p className="mt-2 text-sm text-muted">
              Earn the official award when every published exercise is complete
              {(cert.bosses_total ?? 0) > 0 ? " and every module boss is passed" : ""}.
            </p>
          </div>
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
      <p className="mt-2 max-w-2xl text-base text-muted">
        Certificates use your profile name ({data.learner_name}). Progress tracks your completion
        rate — finish every published exercise
        {data.certificates?.some((item) => (item.bosses_total || 0) > 0)
          ? " and pass each module boss"
          : ""}{" "}
        to remove the watermark and unlock your ID.
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
                {item.earned ? (
                  <p className="mt-1 text-sm text-muted">Official award · ID {item.code}</p>
                ) : (
                  <div className="mt-2 flex flex-col gap-2">
                    <ProgressMeter
                      label="Path completion"
                      completed={item.exercises_completed ?? item.completed}
                      total={item.exercises_total ?? item.total}
                      percent={item.percent}
                    />
                    <p className="text-sm text-muted">
                      Exercises {item.exercises_completed ?? 0}/
                      {item.exercises_total ?? item.total ?? 0}
                      {(item.bosses_total || 0) > 0
                        ? ` · Bosses ${item.bosses_completed || 0}/${item.bosses_total}`
                        : ""}
                    </p>
                  </div>
                )}
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
