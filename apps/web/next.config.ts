import type { NextConfig } from "next";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// Recorded with every signer gate result (PRD Section 10.4: a qualification is per SDK version).
const privySdkVersion = JSON.parse(
  readFileSync(join(process.cwd(), "node_modules/@privy-io/react-auth/package.json"), "utf8"),
).version as string;

const nextConfig: NextConfig = {
  env: { NEXT_PUBLIC_PRIVY_SDK_VERSION: privySdkVersion },
};

export default nextConfig;
