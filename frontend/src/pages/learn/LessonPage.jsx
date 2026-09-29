import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import LessonPlayer from "../../components/editor/LessonPlayer.jsx";

export default function LessonPage() {
  const { lessonId } = useParams();
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api(`/api/learn/lessons/${lessonId}`)
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

  if (error) {
    return <p className="text-sm text-error">{error}</p>;
  }
  if (!lesson) {
    return <p className="text-sm text-muted">Loading…</p>;
  }
  return (
    <LessonPlayer key={lesson.id} lesson={lesson} backTo={`/learn/tracks/${lesson.track_slug}`} />
  );
}
