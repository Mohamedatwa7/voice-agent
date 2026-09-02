import { PrismaHero } from "@/components/ui/prisma-hero";
import { Studio } from "@/components/studio";

export default function Home() {
  return (
    <main className="bg-black">
      <PrismaHero />
      <Studio />
    </main>
  );
}
