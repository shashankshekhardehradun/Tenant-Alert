async function getNeighborhoods() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/neighborhoods`, { cache: "no-store" });
  if (!response.ok) {
    return [];
  }
  const data = (await response.json()) as { items: Array<{ borough: string; complaints: number }> };
  return data.items;
}

export default async function HomePage() {
  const neighborhoods = await getNeighborhoods();
  return (
    <main style={{ margin: "2rem auto", maxWidth: 920, fontFamily: "sans-serif" }}>
      <h1>Tenant Alert</h1>
      <p>NYC tenant analytics from 311 complaints and building-level data.</p>

      <h2>Neighborhood Explorer (Preview)</h2>
      <ul>
        {neighborhoods.map((row) => (
          <li key={row.borough}>
            {row.borough}: {row.complaints.toLocaleString()} complaints
          </li>
        ))}
      </ul>
    </main>
  );
}
