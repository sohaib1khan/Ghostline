import { Link } from "react-router-dom";
import MarkdownView from "./MarkdownView.jsx";

export default function LessonRead({ lesson, backTo }) {
  return (
    <article className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      {backTo ? (
        <Link to={backTo} className="text-sm text-accent">
          {lesson.track_name}
        </Link>
      ) : (
        <p className="text-sm text-muted">{lesson.track_name}</p>
      )}
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{lesson.title}</h1>
      <p className="mt-2 text-sm text-muted">
        {lesson.status}
        {lesson.is_demo ? " · demo" : ""}
        {lesson.module_title ? ` · ${lesson.module_title}` : ""}
      </p>
      {lesson.summary ? <p className="mt-2 text-sm text-muted">{lesson.summary}</p> : null}
      <div className="mt-6">
        <MarkdownView text={lesson.body_markdown} />
      </div>
      <ol className="mt-6 flex flex-col gap-4">
        {lesson.exercises.map((exercise, index) => (
          <li key={exercise.id || index} className="rounded-xl border border-muted/20 p-4">
            <p className="text-sm text-muted">
              {index + 1}. {exercise.type}
              {exercise.time_limit_seconds ? ` · ${exercise.time_limit_seconds}s` : ""}
            </p>
            <p className="mt-2">{exercise.prompt}</p>
            {exercise.code ? (
              <pre className="mt-3 overflow-x-auto rounded-xl bg-bg p-3 font-mono text-sm">
                {exercise.code}
              </pre>
            ) : null}
            {exercise.hints?.length ? (
              <p className="mt-2 text-sm text-muted">{exercise.hints.length} hints available</p>
            ) : null}
          </li>
        ))}
      </ol>
    </article>
  );
}
