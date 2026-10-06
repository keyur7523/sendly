import type { Metadata } from "next";
import GateHarness from "./GateHarness";

export const metadata: Metadata = { title: "Signer gate · Sendly" };

export default function GatePage() {
  return <GateHarness />;
}
