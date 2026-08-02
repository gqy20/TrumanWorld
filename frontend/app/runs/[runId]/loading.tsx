import { WorldOpeningAnimation } from "@/components/world-opening-animation";

export default function RunLoading() {
  return (
    <div className="flex h-full min-h-screen flex-col overflow-hidden lg:min-h-0">
      <WorldOpeningAnimation />
    </div>
  );
}
