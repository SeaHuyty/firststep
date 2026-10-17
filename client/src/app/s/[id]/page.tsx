import { Suspense } from "react";
import { SessionScreen, SessionSkeleton } from "@/components/sprout/session-screen";

// The static shell ships the skeleton; the session (runtime data) streams in behind Suspense,
// as Cache Components requires (node_modules/next/dist/docs/01-app/01-getting-started/08-caching.md).
export default function SessionPage() {
  return (
    <Suspense fallback={<SessionSkeleton />}>
      <SessionScreen />
    </Suspense>
  );
}
