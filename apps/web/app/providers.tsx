"use client";

import { PrivyProvider } from "@privy-io/react-auth";
import { monadTestnet } from "viem/chains";

const appId = process.env.NEXT_PUBLIC_PRIVY_APP_ID;

export default function Providers({ children }: { children: React.ReactNode }) {
  if (!appId) {
    return (
      <main style={{ padding: 32 }}>
        <p>
          Set <code>NEXT_PUBLIC_PRIVY_APP_ID</code> in <code>apps/web/.env.local</code> (see <code>.env.example</code>).
        </p>
      </main>
    );
  }
  return (
    <PrivyProvider
      appId={appId}
      config={{
        loginMethods: ["email"],
        defaultChain: monadTestnet,
        supportedChains: [monadTestnet],
        embeddedWallets: { ethereum: { createOnLogin: "users-without-wallets" } },
      }}
    >
      {children}
    </PrivyProvider>
  );
}
