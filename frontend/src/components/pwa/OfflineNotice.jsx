import { useEffect, useState } from "react";
import { OFFLINE_NOTICE } from "../../offline.js";

export default function OfflineNotice() {
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    function online() {
      setOffline(false);
    }
    function off() {
      setOffline(true);
    }
    window.addEventListener("online", online);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("offline", off);
    };
  }, []);

  if (!offline) {
    return null;
  }
  return (
    <p
      role="status"
      className="rounded-xl border border-muted/30 bg-surface px-3 py-2 text-sm text-muted"
    >
      {OFFLINE_NOTICE}
    </p>
  );
}
