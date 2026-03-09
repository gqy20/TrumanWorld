import { listRunsResult } from "@/lib/api";
import { HomeView } from "@/components/home-view";

export default async function HomePage() {
  const runsResult = await listRunsResult();
  const runs = runsResult.data ?? [];

  return <HomeView runs={runs} error={runsResult.error} />;
}
