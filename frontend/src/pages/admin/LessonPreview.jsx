import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import LessonPlayer from "../../components/editor/LessonPlayer.jsx";

export default function LessonPreview() {
  const { lessonId } = useParams();
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api(`/api/admin/lessons/${lessonId}/preview`)
      .then((data) => {
        if (!cancelled) {
          setLesson(data);
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
  }, [lessonId]);

  return (
    <div className="flex flex-col gap-4">
      <Link to="/admin/content" className="text-sm text-accent">
        Back to content
      </Link>
      <p className="text-sm text-muted">
        This is the learner view. Recall and challenge answers stay hidden.
      </p>
      {error ? <p className="text-sm text-error">{error}</p> : null}
      {!lesson && !error ? <p className="text-sm text-muted">Loading…</p> : null}
      {lesson ? <LessonPlayer key={lesson.id} lesson={lesson} /> : null}
    </div>
  );
}
