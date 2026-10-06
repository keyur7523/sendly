import type { UnsignedTransactionRequest } from "@privy-io/react-auth";

/** Types mirror services/api/app/gate/routes.py. Integers arrive as decimal strings. */

export type Pinned = {
  chain_id: string;
  sender: string;
  to: string;
  data: string;
  value: string;
  nonce: string;
  gas: string;
  max_fee_per_gas: string;
  max_priority_fee_per_gas: string;
  type: string;
  fee_bound: string;
  digest: string;
};

export type Prepared = {
  prepared_id: string;
  pinned: Pinned;
  wallet_request: {
    chainId: number;
    from: string;
    to: string;
    data: string;
    value: string;
    nonce: number;
    gasLimit: string;
    maxFeePerGas: string;
    maxPriorityFeePerGas: string;
    type: number;
  };
};

export type FieldDifference = { field: string; expected: string; observed: string };

export type Comparison = {
  payload_matches: boolean;
  payload_differences: FieldDifference[];
  sender_matches: boolean;
  field_compliance: "matched" | "mismatched";
  compliance_differences: FieldDifference[];
};

export type Verification = {
  status: "not_found" | "pending" | "included" | "finalized";
  receipt_status: "success" | "reverted" | null;
  block_number: number | null;
  finalized_block_number: number;
  transfer_event_found: boolean | null;
  fee_charged_wei: string | null;
  comparison: Comparison | null;
};

export type WalletInfo = {
  address: string;
  chain_id: number;
  wallet: { wallet_type: "eoa" | "eip7702_delegated" | "contract"; delegated: boolean; delegate?: string };
  native_balance_wei: string;
  token: { address: string | null; symbol: string; decimals: number; balance_base_units: string | null };
  nonce_latest: number;
  nonce_pending: number;
};

export type GateCase = "pinned_send" | "pinned_sign_only" | "explicit_rejection" | "same_nonce_replacement" | "wallet_type";

export function toWalletRequest(p: Prepared): UnsignedTransactionRequest {
  const r = p.wallet_request;
  return {
    chainId: r.chainId,
    from: r.from,
    to: r.to,
    data: r.data,
    value: r.value,
    nonce: r.nonce,
    gasLimit: r.gasLimit,
    maxFeePerGas: r.maxFeePerGas,
    maxPriorityFeePerGas: r.maxPriorityFeePerGas,
    type: r.type,
  };
}

/** Capture everything an SDK error exposes, so rejection results can be classified later. */
export function describeError(error: unknown): Record<string, unknown> {
  if (!(error instanceof Error)) return { thrown: String(error) };
  const e = error as Error & Record<string, unknown>;
  const out: Record<string, unknown> = {
    name: e.name,
    message: e.message,
    constructor: e.constructor?.name,
    ownKeys: Object.getOwnPropertyNames(e),
  };
  for (const key of ["code", "privyErrorCode", "type", "status", "details", "shortMessage", "reason"]) {
    if (key in e) out[key] = safe(e[key]);
  }
  if (e.cause !== undefined) out.cause = e.cause instanceof Error ? describeError(e.cause) : safe(e.cause);
  return out;
}

function safe(value: unknown): unknown {
  try {
    return JSON.parse(JSON.stringify(value, (_k, v) => (typeof v === "bigint" ? v.toString() : v)));
  } catch {
    return String(value);
  }
}

export function formatUnits(baseUnits: string | null, decimals: number): string {
  if (baseUnits === null) return "—";
  const negative = baseUnits.startsWith("-");
  const digits = (negative ? baseUnits.slice(1) : baseUnits).padStart(decimals + 1, "0");
  const whole = digits.slice(0, digits.length - decimals);
  const fraction = decimals > 0 ? digits.slice(-decimals).replace(/0+$/, "") : "";
  return `${negative ? "-" : ""}${whole}${fraction ? `.${fraction}` : ""}`;
}
