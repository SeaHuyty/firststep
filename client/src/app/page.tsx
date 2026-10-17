import { Welcome } from "@/components/sprout/welcome";
import { AppShell } from "@/components/ui/shell";

export default function Home() {
  return (
    <AppShell step={null}>
      <Welcome />
    </AppShell>
  );
}
