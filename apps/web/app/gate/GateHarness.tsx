"use client";

import { usePrivy, useSendTransaction, useSignTransaction, useWallets } from "@privy-io/react-auth";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import {
  type Comparison,
  type GateCase,
  type NonceEncoding,
  type Prepared,
  type Verification,
  type WalletInfo,
  describeError,
  formatUnits,
  toWalletRequest,
} from "@/lib/gate";
import styles from "./gate.module.css";

const SDK_PACKAGE = "@privy-io/react-auth";
const SDK_VERSION = process.env.NEXT_PUBLIC_PRIVY_SDK_VERSION ?? "unknown";
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 90_000;
// A wallet call that never settles is an unknown outcome (PRD Section 10.2), never a frozen page.
const WALLET_TIMEOUT_MS = 120_000;

type Call = <T>(path: string, body?: unknown) => Promise<T>;
type LogEntry = { label: string; data: unknown };
type Verdict = boolean | null;

type CaseProps = { call: Call; address: string; onChainChange: () => void };

export default function GateHarness() {
  const { ready, authenticated, login, logout, getAccessToken } = usePrivy();
  const { wallets } = useWallets();
  const embedded = wallets.find((w) => w.walletClientType === "privy");
  const [walletInfo, setWalletInfo] = useState<WalletInfo | null>(null);
  const [walletError, setWalletError] = useState<string | null>(null);

  const call: Call = useCallback(
    async <T,>(path: string, body?: unknown) =>
      api<T>(path, await getAccessToken(), body === undefined ? {} : { method: "POST", body }),
    [getAccessToken],
  );

  const refreshWallet = useCallback(async () => {
    if (!embedded) return;
    try {
      const info = await call<WalletInfo>(`/v1/gate/wallet?address=${embedded.address}`);
      setWalletInfo(info);
      setWalletError(null);
    } catch (e) {
      setWalletError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e));
    }
  }, [call, embedded]);

  const embeddedAddress = embedded?.address;
  useEffect(() => {
    if (!authenticated || !embeddedAddress) return;
    let ignore = false;
    call<WalletInfo>(`/v1/gate/wallet?address=${embeddedAddress}`).then(
      (info) => !ignore && (setWalletInfo(info), setWalletError(null)),
      (e) => !ignore && setWalletError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e)),
    );
    return () => {
      ignore = true;
    };
  }, [authenticated, embeddedAddress, call]);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Signer gate</h1>
          <p className={styles.lead}>
            Measures what the wallet SDK does with a fully pinned transaction. PRD Section 10.4.
          </p>
        </div>
        <div className={styles.row} style={{ margin: 0 }}>
          <span className={styles.badge}>TEST FUNDS · Monad testnet</span>
          {authenticated && (
            <button className={styles.secondary} onClick={() => void logout()}>
              Sign out
            </button>
          )}
        </div>
      </header>

      {!ready && <p>Loading…</p>}
      {ready && !authenticated && (
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>Sign in</h2>
          <p className={styles.muted}>Email login creates an embedded wallet on first sign-in.</p>
          <button className={styles.primary} onClick={() => login()}>
            Sign in with email
          </button>
        </section>
      )}

      {ready && authenticated && !embedded && (
        <section className={styles.card}>
          <p>Waiting for the embedded wallet…</p>
        </section>
      )}

      {ready && authenticated && embedded && (
        <>
          <WalletPanel info={walletInfo} error={walletError} onRefresh={refreshWallet} call={call} />
          <PinnedSendCase call={call} address={embedded.address} onChainChange={refreshWallet} />
          <SignOnlyCase call={call} address={embedded.address} onChainChange={refreshWallet} />
          <RejectionCase call={call} address={embedded.address} onChainChange={refreshWallet} />
          <ReplacementCase call={call} address={embedded.address} onChainChange={refreshWallet} />
        </>
      )}
    </main>
  );
}

function WalletPanel({
  info,
  error,
  onRefresh,
  call,
}: {
  info: WalletInfo | null;
  error: string | null;
  onRefresh: () => Promise<void>;
  call: Call;
}) {
  const verdict: Verdict = info ? info.wallet.wallet_type === "eoa" : null;
  return (
    <section className={styles.card}>
      <h2 className={styles.cardTitle}>Gate check 4 · Wallet</h2>
      <p className={styles.muted}>
        The first release supports undelegated EOAs only (PRD Section 10.3). Fund this address manually with test MON
        and DemoUSD before running the other checks (docs/demo-guide.md).
      </p>
      {error && <p className={styles.fail}>{error}</p>}
      {info && (
        <dl className={styles.grid}>
          <div>
            <dt>Address</dt>
            <dd className="mono">{info.address}</dd>
          </div>
          <div>
            <dt>Wallet type</dt>
            <dd>
              {info.wallet.wallet_type}
              {info.wallet.delegate ? ` → ${info.wallet.delegate}` : ""}
            </dd>
          </div>
          <div>
            <dt>Native balance</dt>
            <dd className="balance">{formatUnits(info.native_balance_wei, 18)} MON</dd>
          </div>
          <div>
            <dt>Token balance</dt>
            <dd className="balance">
              {info.token.address
                ? `${formatUnits(info.token.balance_base_units, info.token.decimals)} ${info.token.symbol}`
                : "DEMO_TOKEN_ADDRESS not configured"}
            </dd>
          </div>
          <div>
            <dt>Nonce (latest / pending)</dt>
            <dd>
              {info.nonce_latest} / {info.nonce_pending}
            </dd>
          </div>
        </dl>
      )}
      <div className={styles.row}>
        <button className={styles.secondary} onClick={() => void onRefresh()}>
          Refresh
        </button>
      </div>
      <Recorder
        call={call}
        gateCase="wallet_type"
        mode="n/a"
        suggested={verdict}
        defaultSummary={info ? `Embedded wallet type: ${info.wallet.wallet_type}` : ""}
        details={info ? { wallet: info.wallet } : null}
      />
    </section>
  );
}

/** Check 1, send mode: does sendTransaction broadcast exactly the pinned fields? */
function PinnedSendCase({ call, address, onChainChange }: CaseProps) {
  const { sendTransaction } = useSendTransaction();
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("0.01");
  const { log, push, reset, busy, run } = useLog();
  const [verification, setVerification] = useState<Verification | null>(null);

  const start = () =>
    run(async () => {
      reset();
      setVerification(null);
      const prepared = await prepareTransfer(call, address, recipient || address, amount);
      push("Prepared (pinned)", prepared.pinned);
      const { hash } = await sendTransaction(toWalletRequest(prepared), { address });
      push("sendTransaction returned hash", hash);
      const final = await pollVerify(call, prepared.prepared_id, hash, (v) => setVerification(v));
      push("Verification", final);
      onChainChange();
    });

  return (
    <CaseCard
      title="Gate check 1 · Pinned fields preserved (send mode)"
      description="Sendly prepares a DemoUSD transfer with nonce, gas limit, maxFeePerGas and maxPriorityFeePerGas pinned. Pass if the broadcast transaction carries exactly those values and reaches finality."
    >
      <TransferInputs recipient={recipient} setRecipient={setRecipient} amount={amount} setAmount={setAmount} />
      <div className={styles.row}>
        <button className={styles.primary} disabled={busy} onClick={start}>
          {busy ? "Running…" : "Prepare and send"}
        </button>
      </div>
      <VerificationSummary v={verification} />
      <Log entries={log} />
      <Recorder
        call={call}
        gateCase="pinned_send"
        mode="send"
        suggested={verdictFor(verification)}
        defaultSummary={summaryFor(verification)}
        details={verification ? { verification, log } : null}
      />
    </CaseCard>
  );
}

/** Check 1, sign-only mode: is signTransaction's output a full signed transaction we can verify before broadcast? */
function SignOnlyCase({ call, address, onChainChange }: CaseProps) {
  const { signTransaction } = useSignTransaction();
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("0.01");
  const [nonceOverride, setNonceOverride] = useState("");
  const [nonceEncoding, setNonceEncoding] = useState<NonceEncoding>("hex");
  const [kind, setKind] = useState<"token_transfer" | "self_transfer">("token_transfer");
  const [feeGwei, setFeeGwei] = useState("");
  const { log, push, reset, busy, run } = useLog();
  const [pending, setPending] = useState<{ prepared: Prepared; signed: string } | null>(null);
  const [inspection, setInspection] = useState<{ comparison: Comparison; tx_hash: string } | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [undecodable, setUndecodable] = useState(false);

  const sign = () =>
    run(async () => {
      reset();
      setPending(null);
      setInspection(null);
      setVerification(null);
      setUndecodable(false);
      const prepared = await call<Prepared>("/v1/gate/prepare", {
        sender: address,
        kind,
        ...(kind === "token_transfer" ? { recipient: recipient || address, amount } : {}),
        nonce: nonceOverride === "" ? undefined : Number(nonceOverride),
        max_fee_per_gas_gwei: feeGwei === "" ? undefined : Number(feeGwei),
      });
      push("Prepared (pinned)", prepared.pinned);
      const request = toWalletRequest(prepared, nonceEncoding);
      push("Nonce sent to wallet", { encoding: nonceEncoding, value: request.nonce });
      const { signature } = await signTransaction(request, { address });
      push("signTransaction returned", signature);
      try {
        const inspected = await call<{ comparison: Comparison; tx_hash: string }>("/v1/gate/inspect-signed", {
          prepared_id: prepared.prepared_id,
          signed_transaction: signature,
        });
        push("Decoded before broadcast", inspected);
        setInspection(inspected);
        setPending({ prepared, signed: signature });
      } catch (e) {
        if (e instanceof ApiError && e.code === "UNDECODABLE_SIGNED_TRANSACTION") {
          setUndecodable(true);
          push("Not a full signed transaction", "The SDK returned only a signature; sign-only mode is not usable.");
        } else throw e;
      }
    });

  const broadcast = () =>
    run(async () => {
      if (!pending) return;
      const result = await call<{ tx_hash: string; broadcast: string }>("/v1/gate/broadcast", {
        prepared_id: pending.prepared.prepared_id,
        signed_transaction: pending.signed,
      });
      push("Broadcast", result);
      if (result.broadcast === "accepted") {
        const final = await pollVerify(call, pending.prepared.prepared_id, result.tx_hash, setVerification);
        push("Verification", final);
      }
      setPending(null);
      onChainChange();
    });

  const suggested: Verdict = undecodable ? false : inspection ? verdictFor(verification, inspection.comparison) : null;
  return (
    <CaseCard
      title="Gate check 1b · Sign-only mode"
      description="If signTransaction returns the full signed transaction, Sendly can compute the hash and check every field before broadcasting, and broadcast it itself. This would narrow the crash window in PRD Section 10.5."
    >
      <TransferInputs recipient={recipient} setRecipient={setRecipient} amount={amount} setAmount={setAmount} />
      <div className={styles.row}>
        <label className={styles.field}>
          Nonce override (blank = current nonce; a spent nonce such as 0 is safe because it can never be included)
          <input
            inputMode="numeric"
            value={nonceOverride}
            onChange={(e) => setNonceOverride(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="current"
          />
        </label>
        <label className={styles.field}>
          Transaction
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as "token_transfer" | "self_transfer")}
            style={{ height: 48, borderRadius: "var(--radius-control)", font: "inherit", fontSize: 16 }}
          >
            <option value="token_transfer">DemoUSD transfer (payment)</option>
            <option value="self_transfer">0 MON self-transfer (replacement)</option>
          </select>
        </label>
        <label className={styles.field}>
          maxFeePerGas override in gwei (blank = quote; below base fee keeps it pending)
          <input
            inputMode="numeric"
            value={feeGwei}
            onChange={(e) => setFeeGwei(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="quote"
          />
        </label>
        <label className={styles.field}>
          Nonce encoding sent to the wallet
          <select
            value={nonceEncoding}
            onChange={(e) => setNonceEncoding(e.target.value as NonceEncoding)}
            style={{ height: 48, borderRadius: "var(--radius-control)", font: "inherit", fontSize: 16 }}
          >
            <option value="hex">hex string (e.g. &quot;0x3&quot;)</option>
            <option value="number">number (e.g. 3)</option>
          </select>
        </label>
      </div>
      <div className={styles.row}>
        <button className={styles.primary} disabled={busy} onClick={sign}>
          Prepare and sign (no broadcast)
        </button>
        <button className={styles.secondary} disabled={busy || !pending} onClick={broadcast}>
          Broadcast signed transaction
        </button>
      </div>
      {inspection && <ComparisonView c={inspection.comparison} />}
      <VerificationSummary v={verification} />
      <Log entries={log} />
      <Recorder
        call={call}
        gateCase="pinned_sign_only"
        mode="sign_only"
        suggested={suggested}
        defaultSummary={
          undecodable
            ? "signTransaction returned a bare signature, not a signed transaction; sign-only mode not usable"
            : summaryFor(verification, inspection?.comparison)
        }
        details={{ undecodable, inspection, verification, log }}
      />
    </CaseCard>
  );
}

/** Check 2: is an explicit user rejection distinguishable from other failures? */
type RejectionVariant = "close_button" | "escape_key" | "non_rejection_error";

function RejectionCase({ call, address }: CaseProps) {
  const { sendTransaction } = useSendTransaction();
  const { log, push, reset, busy, run } = useLog();
  const [captured, setCaptured] = useState<Partial<Record<RejectionVariant, Record<string, unknown>>>>({});

  const attempt = (variant: RejectionVariant) =>
    run(async () => {
      if (variant === "close_button") reset();
      // The non-rejection variant reuses nonce 0, which this wallet has already spent: the user
      // approves, and the failure comes from the network, not from a user decision.
      const prepared =
        variant === "non_rejection_error"
          ? await call<Prepared>("/v1/gate/prepare", {
              sender: address,
              kind: "token_transfer",
              recipient: address,
              amount: "0.01",
              nonce: 0,
            })
          : await prepareTransfer(call, address, address, "0.01");
      try {
        const { hash } = await withTimeout(sendTransaction(toWalletRequest(prepared), { address }), WALLET_TIMEOUT_MS);
        push(`${variant}: unexpectedly succeeded`, hash);
      } catch (e) {
        const described = e instanceof WalletTimeout ? { timeout: true, message: e.message } : describeError(e);
        push(`${variant}: error`, described);
        setCaptured((c) => ({ ...c, [variant]: described }));
      }
    });

  const code = (v: RejectionVariant) => captured[v]?.code;
  const suggested: Verdict =
    captured.close_button && captured.escape_key && captured.non_rejection_error
      ? code("close_button") === 4001 && code("escape_key") === 4001 && code("non_rejection_error") !== 4001
      : null;

  return (
    <CaseCard
      title="Gate check 2 · Explicit rejection is distinguishable"
      description="Privy's approval screen has Approve and ✕ only. Variant 1: press ✕. Variant 2: press Esc. Variant 3: press Approve; the transaction reuses a spent nonce, so the network rejects it and nothing moves. Pass only if both refusals give an error that a stable field (not message text) distinguishes from the network failure."
    >
      <div className={styles.row}>
        <button className={styles.secondary} disabled={busy} onClick={() => attempt("close_button")}>
          1. Send, then press ✕
        </button>
        <button className={styles.secondary} disabled={busy} onClick={() => attempt("escape_key")}>
          2. Send, then press Esc
        </button>
        <button className={styles.secondary} disabled={busy} onClick={() => attempt("non_rejection_error")}>
          3. Send at a spent nonce, then Approve
        </button>
      </div>
      <Log entries={log} />
      <Recorder
        call={call}
        gateCase="explicit_rejection"
        mode="send"
        suggested={suggested}
        defaultSummary="Compare the captured error shapes and state which stable field distinguishes rejection"
        details={{ captured }}
      />
    </CaseCard>
  );
}

/** Check 3: will the SDK sign a zero-value self-transfer at a nonce the app specifies? */
function ReplacementCase({ call, address, onChainChange }: CaseProps) {
  const { signTransaction } = useSignTransaction();
  const { sendTransaction } = useSendTransaction();
  const { log, push, reset, busy, run } = useLog();
  const [held, setHeld] = useState<{ prepared: Prepared; signed: string; nonce: number } | null>(null);
  const [replacement, setReplacement] = useState<Verification | null>(null);
  const [paymentBroadcast, setPaymentBroadcast] = useState<string | null>(null);

  const holdPayment = () =>
    run(async () => {
      reset();
      setReplacement(null);
      setPaymentBroadcast(null);
      const prepared = await prepareTransfer(call, address, address, "0.01");
      const { signature } = await signTransaction(toWalletRequest(prepared), { address });
      const nonce = Number(prepared.pinned.nonce);
      push(`Payment signed at nonce ${nonce}, held (not broadcast)`, prepared.pinned);
      setHeld({ prepared, signed: signature, nonce });
    });

  const sendReplacement = () =>
    run(async () => {
      if (!held) return;
      const prepared = await call<Prepared>("/v1/gate/prepare", {
        sender: address,
        kind: "self_transfer",
        nonce: held.nonce,
      });
      push("Replacement prepared", prepared.pinned);
      const { hash } = await sendTransaction(toWalletRequest(prepared), { address });
      push("Replacement hash", hash);
      const final = await pollVerify(call, prepared.prepared_id, hash, setReplacement);
      push("Replacement verification", final);
      onChainChange();
    });

  const broadcastHeldPayment = () =>
    run(async () => {
      if (!held) return;
      const result = await call<{ broadcast: string; rpc_error?: { message: string } }>("/v1/gate/broadcast", {
        prepared_id: held.prepared.prepared_id,
        signed_transaction: held.signed,
      });
      push("Held payment broadcast after replacement", result);
      setPaymentBroadcast(result.broadcast);
    });

  const nonceKept = replacement?.comparison?.compliance_differences.every((d) => d.field !== "nonce");
  const suggested: Verdict =
    replacement && paymentBroadcast
      ? replacement.status === "finalized" && !!nonceKept && paymentBroadcast === "rejected"
      : null;

  return (
    <CaseCard
      title="Gate check 3 · Same-nonce replacement"
      description="Sign a payment at nonce N and hold it unbroadcast (requires sign-only mode), send a zero-value self-transfer at N, then try to broadcast the held payment. Pass if the replacement keeps nonce N and finalizes, and the held payment is then rejected by the network. Limitation: this does not test a payment that is pending in a mempool."
    >
      <ol className={styles.steps}>
        <li>Sign and hold a payment at the current nonce.</li>
        <li>Send the replacement at the same nonce.</li>
        <li>Broadcast the held payment; expect rejection.</li>
      </ol>
      <div className={styles.row}>
        <button className={styles.secondary} disabled={busy} onClick={holdPayment}>
          1. Sign and hold payment
        </button>
        <button className={styles.secondary} disabled={busy || !held} onClick={sendReplacement}>
          2. Send replacement at nonce {held?.nonce ?? "N"}
        </button>
        <button className={styles.secondary} disabled={busy || !held || !replacement} onClick={broadcastHeldPayment}>
          3. Broadcast held payment
        </button>
      </div>
      <VerificationSummary v={replacement} />
      <Log entries={log} />
      <Recorder
        call={call}
        gateCase="same_nonce_replacement"
        mode="send"
        suggested={suggested}
        defaultSummary={
          suggested === null
            ? ""
            : `Replacement ${replacement?.status}, nonce ${nonceKept ? "kept" : "changed"}; held payment ${paymentBroadcast}`
        }
        details={{ held: held?.prepared.pinned ?? null, replacement, paymentBroadcast, log }}
      />
    </CaseCard>
  );
}

/* ---------- shared pieces ---------- */

class WalletTimeout extends Error {}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new WalletTimeout(`No result from the wallet after ${ms / 1000}s; outcome unknown`)),
      ms,
    );
    promise.then(
      (value) => (clearTimeout(timer), resolve(value)),
      (error) => (clearTimeout(timer), reject(error)),
    );
  });
}

async function prepareTransfer(call: Call, sender: string, recipient: string, amount: string, nonce?: number) {
  return call<Prepared>("/v1/gate/prepare", { sender, kind: "token_transfer", recipient, amount, nonce });
}

async function pollVerify(
  call: Call,
  preparedId: string,
  txHash: string,
  onUpdate: (v: Verification) => void,
): Promise<Verification> {
  const started = performance.now();
  let latest: Verification | null = null;
  while (performance.now() - started < POLL_TIMEOUT_MS) {
    latest = await call<Verification>("/v1/gate/verify", { prepared_id: preparedId, tx_hash: txHash });
    onUpdate(latest);
    if (latest.status === "finalized") return latest;
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
  if (!latest) throw new Error("verification did not run");
  return latest;
}

function verdictFor(v: Verification | null, signed?: Comparison): Verdict {
  if (!v || v.status !== "finalized" || !v.comparison) return null;
  const c = v.comparison;
  const signedOk = signed ? signed.payload_matches && signed.field_compliance === "matched" : true;
  return (
    signedOk &&
    c.payload_matches &&
    c.sender_matches &&
    c.field_compliance === "matched" &&
    v.receipt_status === "success" &&
    v.transfer_event_found === true
  );
}

function summaryFor(v: Verification | null, signed?: Comparison): string {
  if (!v?.comparison) return "";
  const diffs = v.comparison.compliance_differences.map((d) => d.field).join(", ");
  return [
    `status ${v.status}, receipt ${v.receipt_status}`,
    `payload ${v.comparison.payload_matches ? "matched" : "differs"}`,
    `fields ${v.comparison.field_compliance}${diffs ? ` (${diffs})` : ""}`,
    signed ? `signed copy fields ${signed.field_compliance}` : null,
  ]
    .filter(Boolean)
    .join("; ");
}

function useLog() {
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const push = useCallback((label: string, data: unknown) => setLog((l) => [...l, { label, data }]), []);
  const reset = useCallback(() => setLog([]), []);
  const run = useCallback(
    async (fn: () => Promise<void>) => {
      setBusy(true);
      try {
        await fn();
      } catch (e) {
        push("Error", e instanceof ApiError ? { code: e.code, message: e.message } : describeError(e));
      } finally {
        setBusy(false);
      }
    },
    [push],
  );
  return { log, push, reset, busy, run };
}

function CaseCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className={styles.card}>
      <h2 className={styles.cardTitle}>{title}</h2>
      <p className={styles.muted}>{description}</p>
      {children}
    </section>
  );
}

function TransferInputs(props: {
  recipient: string;
  setRecipient: (v: string) => void;
  amount: string;
  setAmount: (v: string) => void;
}) {
  return (
    <div className={styles.row}>
      <label className={styles.field}>
        Recipient (blank = your own address)
        <input value={props.recipient} onChange={(e) => props.setRecipient(e.target.value.trim())} placeholder="0x…" />
      </label>
      <label className={styles.field}>
        Amount (DemoUSD)
        <input inputMode="decimal" value={props.amount} onChange={(e) => props.setAmount(e.target.value.trim())} />
      </label>
    </div>
  );
}

function VerificationSummary({ v }: { v: Verification | null }) {
  if (!v) return null;
  return (
    <div className={styles.row} aria-live="polite">
      <span className={v.status === "finalized" ? styles.pass : styles.pending}>{v.status}</span>
      {v.receipt_status && (
        <span className={v.receipt_status === "success" ? styles.pass : styles.fail}>receipt {v.receipt_status}</span>
      )}
      {v.comparison && <ComparisonBadges c={v.comparison} />}
      {v.fee_charged_wei && <span className="fee">fee charged {formatUnits(v.fee_charged_wei, 18)} MON</span>}
    </div>
  );
}

function ComparisonView({ c }: { c: Comparison }) {
  return (
    <div className={styles.row}>
      <ComparisonBadges c={c} />
    </div>
  );
}

function ComparisonBadges({ c }: { c: Comparison }) {
  return (
    <>
      <span className={c.payload_matches ? styles.pass : styles.fail}>
        payload {c.payload_matches ? "matches" : "differs"}
      </span>
      <span className={c.field_compliance === "matched" ? styles.pass : styles.fail}>
        fields {c.field_compliance}
        {c.compliance_differences.length > 0 && `: ${c.compliance_differences.map((d) => d.field).join(", ")}`}
      </span>
      {!c.sender_matches && <span className={styles.fail}>sender differs</span>}
    </>
  );
}

function Log({ entries }: { entries: LogEntry[] }) {
  if (entries.length === 0) return null;
  return (
    <details open>
      <summary>Log ({entries.length})</summary>
      <pre className={styles.pre}>
        {entries.map((e) => `${e.label}\n${JSON.stringify(e.data, null, 2)}`).join("\n\n")}
      </pre>
    </details>
  );
}

function Recorder(props: {
  call: Call;
  gateCase: GateCase;
  mode: "send" | "sign_only" | "n/a";
  suggested: Verdict;
  defaultSummary: string;
  details: Record<string, unknown> | null;
}) {
  const [summary, setSummary] = useState("");
  const [recorded, setRecorded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const record = async (passed: Verdict) => {
    try {
      setError(null);
      await props.call("/v1/gate/results", {
        case: props.gateCase,
        mode: props.mode,
        passed,
        sdk_package: SDK_PACKAGE,
        sdk_version: SDK_VERSION,
        summary: summary || props.defaultSummary || "(no summary)",
        details: props.details ?? {},
      });
      setRecorded(passed === null ? "inconclusive" : passed ? "pass" : "fail");
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  if (!props.details) return null;
  return (
    <div>
      <p className={styles.muted} style={{ marginTop: 16, marginBottom: 8 }}>
        Suggested verdict:{" "}
        {props.suggested === null ? "needs your judgment" : props.suggested ? "pass" : "fail"} · SDK {SDK_PACKAGE}@
        {SDK_VERSION}
      </p>
      <div className={styles.row}>
        <label className={styles.field}>
          Summary
          <input value={summary} placeholder={props.defaultSummary} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <button className={styles.secondary} onClick={() => void record(true)}>
          Record pass
        </button>
        <button className={styles.secondary} onClick={() => void record(false)}>
          Record fail
        </button>
        <button className={styles.secondary} onClick={() => void record(null)}>
          Inconclusive
        </button>
      </div>
      {recorded && <p className={styles.recorded}>Recorded as {recorded} in docs/signer-gate/results.jsonl</p>}
      {error && <p className={styles.fail}>{error}</p>}
    </div>
  );
}
