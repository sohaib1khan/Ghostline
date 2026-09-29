import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import LessonPlayer from "../../components/editor/LessonPlayer.jsx";
import { markDemoComplete, withDemoProgress } from "../../demoProgress.js";

export default function DemoLessonPage() {
  const { lessonId } = useParams();
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api(`/api/demo/lessons/${lessonId}`)
      .then((data) => {
        if (!cancelled) {
          setLesson(withDemoProgress(data));
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

  function onPassed(exerciseId) {
    markDemoComplete(exerciseId);
    setLesson((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        exercises: current.exercises.map((item) =>
          item.id === exerciseId ? { ...item, progress: { status: "completed" } } : item,
        ),
      };
    });
  }

  if (error) {
    return <p className="text-sm text-error">{error}</p>;
  }
  if (!lesson) {
    return <p className="text-sm text-muted">Loading…</p>;
  }
  return (
    <LessonPlayer
      key={lesson.id}
      lesson={lesson}
      backTo="/demo"
      checkPath={(id) => `/api/demo/check/${id}`}
      onPassed={onPassed}
      accountXp={false}
      finish={
        <p>
          You finished this demo.{" "}
          <Link to="/signup" className="text-accent">
            Sign up
          </Link>{" "}
          to keep going on the rest of the tracks.
        </p>
      }
    />
  );
}
