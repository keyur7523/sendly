import Link from "next/link";

export default function Home() {
  return (
    <main style={{ maxWidth: "var(--content-max)", margin: "0 auto", padding: "48px 32px" }}>
      <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.025em" }}>Sendly</h1>
      <p style={{ color: "var(--text-secondary)" }}>
        Phase 1 build. The payment product is not implemented yet; the signer gate harness verifies what the wallet SDK
        does with a fully pinned transaction (PRD Section 10.4).
      </p>
      <p>
        <Link href="/gate">Open the signer gate harness →</Link>
      </p>
    </main>
  );
}
