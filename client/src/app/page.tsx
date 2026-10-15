import App from "@/components/app";
import { CatalogProvider } from "@/lib/catalog";

export default function Home() {
  return (
    <CatalogProvider>
      <App />
    </CatalogProvider>
  );
}
