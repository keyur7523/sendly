# Sendly — UI, UX, and Frontend Design Guide

**Theme:** Quiet White  
**Product:** Voice-first payments on Monad  
**Frontend:** Next.js + React + TypeScript  
**Version:** 1.1  
**Status:** Proposed design direction, ready to guide implementation  
**Date:** October 5, 2026

## 1. The design in one sentence

A bright white interface with crisp charcoal typography, generous spacing, restrained blue accents, and a clear payment card that stays central throughout the conversation.

The product should feel approachable, precise, and composed. A user should understand where their money is going without learning the technical architecture. The sophistication comes from typography, alignment, useful feedback, and complete interaction states.

**Recommended direction:** white canvas, Inter typography, charcoal primary buttons, a small blue listening indicator, thin neutral dividers, and rounded rectangular controls. Use green only for a verified successful payment.

**Signature interaction:** the speaking payment card. While Sendly reads a payment aloud, the card shows which detail is being spoken, and a spoken correction is visible on the card as a change (`50 → 15`). Sendly's character comes from this, not from decoration (Section 9.1).

This is an original direction for Sendly, not a copy of another product's interface.

## 2. Relationship to the PRD

**Ownership.** This guide owns visual layout, presentation, and copy style. The PRD owns behavior, state, and authorization. Where they appear to disagree on behavior, the PRD wins and this guide is corrected.

The behavioral reference is `VOICE_PAYMENTS_PRD.md` in this folder (version 1.4 or later). It is the only copy; confirm its version line before relying on any section reference below.

Important dependencies from the PRD review:

- Payment outcome and signer-field compliance are separate. A successful payment with a fee discrepancy still displays as sent, with a separate notice.
- Unknown transaction outcomes must never show a plain “Send again” action.
- Replacement transactions require their own exact review and approval.
- Every action's availability (confirm, retry in wallet, review replacement, start a new payment) comes from the backend `capabilities` object, which includes a reason when an action is unavailable. The backend still enforces each permission when the action is requested.
- Spending allowance must come from backend accounting, including outstanding reservations.
- A nonce mismatch is an exceptional reconciliation case. If the transfer is independently verified, it is shown as sent with a separate incident notice; in every case no duplicate-send path is offered.

The frontend cannot manufacture success, infer approval from an animation, or infer retry permission from an error message.

## 3. Visual character

### The interface should communicate

| Quality | Visual and interaction expression |
|---|---|
| Clear | One primary task, descriptive actions, material details always visible |
| Calm | White surfaces, quiet borders, modest motion, short messages |
| Human | Contact names, initials, natural language, useful empty states |
| Precise | Aligned amounts, explicit units, reliable state labels |
| Polished | Consistent spacing, complete loading/error states, stable layouts |

Avoid decorative gradients, glass effects, giant glowing voice orbs, floating crypto coins, excessive cards, speculative charts, fake social proof, and an oversized marketing headline inside the authenticated app.

Use subtle surface hierarchy rather than placing every sentence inside a bordered container. Do not remove labels or useful explanations merely to make a screen look empty.

## 4. Color system

### Core palette

| Token | Value | Usage |
|---|---|---|
| `canvas` | `#FFFFFF` | Page background |
| `surface` | `#FFFFFF` | Main payment card, dialogs |
| `surface-subtle` | `#F8FAFC` | Secondary panels, input background, quiet row hover |
| `surface-pressed` | `#F1F5F9` | Pressed secondary controls |
| `text-primary` | `#111827` | Headings, amount, primary content |
| `text-secondary` | `#475569` | Supporting descriptions |
| `text-muted` | `#64748B` | Timestamps, supplementary labels |
| `border` | `#E2E8F0` | Decorative card borders and dividers |
| `control-border` | `#64748B` | Input/control boundaries when needed for identification |
| `action` | `#111827` | Primary button and active microphone control |
| `action-hover` | `#1F2937` | Primary button hover |
| `accent` | `#1D4ED8` | Links, focus ring, listening/active cues |
| `accent-soft` | `#EFF6FF` | Selected informational surface |

### Semantic palette

| State | Foreground | Background | Use |
|---|---|---|---|
| Success | `#166534` | `#F0FDF4` | Finalized successful payment |
| Caution | `#92400E` | `#FFFBEB` | Unknown outcome, fee discrepancy, time-sensitive review |
| Error | `#B91C1C` | `#FEF2F2` | Input failure or finalized failed transfer |
| Informational | `#1D4ED8` | `#EFF6FF` | Listening, submitted, included, helpful notices |
| Neutral | `#475569` | `#F8FAFC` | Not started, cancelled, timestamps |

Rules:

- White occupies most of each screen; do not mechanically enforce a percentage.
- Use charcoal for the main action and blue for supporting interactive cues.
- Never use green to imply safety before the payment succeeds.
- Pair every semantic color with text and, where useful, a simple icon.
- Quiet decorative borders are not sufficient boundaries for an otherwise invisible control. Use the stronger control border where required.
- Test actual text/background pairs, focus indicators, hover states, and disabled states in the rendered app. Tokens alone do not establish accessibility conformance.

## 5. Typography

### Primary font: Inter

Use **Inter** throughout the product, including the wordmark. It supports interface typography and tabular numbers, allowing payment amounts to align cleanly. Use its real 400, 500, and 600 weights rather than synthetic bold. Font reference: [Inter](https://rsms.me/inter/).

One family is sufficient. Do not introduce a decorative headline font or a second font for ordinary numbers. Use the system monospace stack only for expanded wallet addresses and transaction hashes.

Prefer self-hosted font files with appropriate license notices. Use the project's Next.js font-loading mechanism, reserve appropriate fallback metrics, and avoid blocking the app on a third-party font stylesheet.

### Type scale

| Role | Desktop | Mobile | Weight / line height |
|---|---|---|---|
| Public landing headline | 48px | 36px | 600 / 1.12 |
| App page title | 28px | 24px | 600 / 1.25 |
| Payment amount | 48px | 40px | 600 / 1.1 |
| Section heading | 18px | 18px | 600 / 1.4 |
| Body / input | 16px | 16px | 400 / 1.5 |
| Button / navigation | 14px | 14px | 500 / 1.4 |
| Supporting text | 14px | 14px | 400 / 1.5 |
| Small metadata | 12px | 12px | 500 / 1.5 |

Use 12px only for nonessential metadata. Amount units, recipient information, fee details, and actions must remain comfortably readable. Keep browser form text at 16px on mobile.

Use slightly tighter tracking for large headings, approximately `-0.025em`; normal tracking for body text. Avoid uppercase labels except short environmental indicators such as “TEST FUNDS.”

### Numeric formatting

- Use `font-variant-numeric: tabular-nums lining-nums` for amounts, balances, and fees.
- Show token units explicitly: `15.00 DemoUSD`, not an unexplained `$15`.
- Use the backend's exact decimal strings. Do not round payment values through JavaScript floating-point arithmetic.
- For long amounts, wrap the unit or reduce the amount font within a documented minimum; do not truncate the value.
- Never round a positive fee down to a displayed zero. Show appropriate precision and offer exact details.
- Animate neither the balance nor amount like a slot machine.

## 6. Spacing, shape, and depth

Use a 4px base spacing system:

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.

| Element | Specification |
|---|---|
| Desktop page gutters | 32px minimum |
| Mobile page gutters | 16px |
| Main content maximum width | 1120px |
| Main card padding | 32px desktop, 20px mobile |
| Secondary card padding | 20–24px |
| Related label/content gap | 6–8px |
| Form field gap | 20px |
| Section gap | 32–40px |
| Input/button radius | 10px |
| Main card radius | 16px |
| Badge radius | 999px |
| Standard control height | 48px |
| Icon-only hit target | At least 44 × 44px |

Use one light main-card shadow: `0 4px 20px rgb(15 23 42 / 0.04)`. Most surfaces need only a border. Reserve stronger shadows for floating menus/dialogs. Avoid nested shadows.

Rounded corners should soften controls without making every element a pill. The round microphone button is a deliberate exception.

## 7. App shell and navigation

Use a **simple top navigation**, not a permanent dashboard sidebar. The app has a small set of destinations and one primary task.

Desktop header, approximately 72px tall:

- Left: Sendly wordmark, optional small static mark.
- Middle: Send, Activity, Contacts.
- Right: test-network indicator and account menu.

Receive is not a top-level destination in the first release. When the receive page ships (PRD UX-03), it appears in the account menu as “Receive” and as a link on the empty-balance state.

Active navigation uses darker text and a short underline or subtle background; hover must not move layout. Account menu contains wallet information, settings, and sign out.

On mobile, keep the header compact and provide three labeled navigation items. A bottom navigation is acceptable on resting screens, but hide or reposition it while the software keyboard is open so it cannot overlap payment controls. Settings remain in the account menu.

The environment label must remain available during payment review and wallet handoff. Do not hide test-fund status solely in a tooltip.

## 8. Main payment workspace

### Desktop composition

Use a two-column layout: flexible payment workspace on the left, approximately 320px supporting panel on the right. The payment card gets visual priority; the conversation remains compact.

```text
Sendly              Send   Activity   Contacts         Test funds   Account
──────────────────────────────────────────────────────────────────────────

Send a payment
Choose a contact or tell us who and how much.

┌─────────────────────────────────────────┐   Available balance
│ To                                      │   100.00 DemoUSD
│ [M] Mom                  Saved address  │   Monad testnet
│     0x1a2b3c…4821         View address  │
│                                         │   Recent activity
│ 15.00 DemoUSD                           │   Mom       10.00  Sent
│                                         │   Alex       5.00  Sent
│ Network                 Monad testnet   │
│ Fee up to                 0.00… MON     │   All activity →
│                                         │
│ [Edit details]          [Cancel]        │
│ [          Confirm 15 DemoUSD          ]│
└─────────────────────────────────────────┘

  Assistant: Send 15 DemoUSD to the address you saved for Mom…
  ( mic, outlined )  Tap to speak          Type instead
  Say “confirm payment” or press Confirm.
```

The fee shown in this wireframe is a layout placeholder, never shipped copy. Display the real validated fee bound with enough precision.

### Resting state

Heading: **“Send a payment”**.

Payment area: “Who would you like to send to?” with a small list of saved contacts and a clear amount field. Voice and manual entry are both discoverable. A compact microphone control reads “Tap to speak.”

Example helper: “Try: ‘Send Mom fifteen DemoUSD.’” Use examples only when the named contact exists; otherwise use a generic instruction.

No fake transcript, fabricated recent transactions, sample balance, or green checkmark appears in an authenticated empty account.

### Payment review

Visual order:

1. Recipient name and assurance label.
2. Address preview with full-address access.
3. Amount and unit, largest text on the card.
4. Network and maximum network fee.
5. Edit/cancel controls.
6. Explicit confirmation action.

**Confirm button by review state.** The PRD's state machine decides when button approval is possible; the button reflects it and never decides it.

| Review state (PRD) | Confirm button | Nearby text |
|---|---|---|
| Read-back playing (`REVIEWING`) | Visible, disabled | “Available after read-back” with a **Stop read-back** control |
| Read-back finished (`AWAITING_CONFIRMATION`) | Enabled if `capabilities.confirm.allowed` | “Say ‘confirm payment’ or press Confirm” |
| Read-back stopped or TTS failed (`REVIEW_PAUSED`) | Enabled if `capabilities.confirm.allowed` | “Replay read-back” link |
| Challenge expired | Replaced by **Review again** | “This review expired. Review the details again to continue.” |
| Any other reason `confirm.allowed` is false | Disabled | The backend reason, in plain language (Section 10) |

**Expiry.** Show nothing about expiry until roughly 15 seconds remain, then one static line: “Review expires soon.” Do not show a ticking countdown; it adds pressure and floods screen readers. On expiry, switch the card to the expired state above. Animations never change expiry timing.

**Position.** Confirm lives inside the payment card. The microphone lives in the conversation dock. Both keep stable positions across states, so a tap aimed at one can never land on the other; on mobile, Confirm must never appear where the microphone was.

**Accidental-tap guard.** After any field on the card changes, Confirm ignores activation for about 600ms. This guard only ever delays; it never enables Confirm. Whether Confirm is enabled still depends on the current revision, the review state, and `capabilities.confirm`.

Show the complete destination during contact creation. In routine review, use a prefix and suffix with accessible full-address expansion and Copy. Copied feedback says “Address copied”; it does not imply verification.

### Conversation presentation

Use a compact conversation log below or beside the payment card. User and assistant labels are more important than large chat bubbles. The current response gets emphasis; older turns can collapse behind “Conversation history.”

Interim transcription is marked “Hearing…” and has a provisional visual treatment. Final text becomes normal body text. Do not announce every interim word to a screen reader.

A correction is shown on the card as a change (Section 9.1) and announced once: “Amount changed from 50 to 15 DemoUSD.” Clear any old approved state immediately. Do not represent a corrected payment as already approved.

## 9. Voice controls

Use a 56px circular button with a simple microphone icon, plus an adjacent readable state label. The button is an input control, not the payment authorization button. It is solid charcoal when it is the main way forward (resting and clarifying) and **outlined** (white fill, charcoal border and icon) whenever a payment card is under review, so Confirm is the only solid primary action on screen.

| State | Visual treatment | Label / action |
|---|---|---|
| Idle | Charcoal mic | “Tap to speak” |
| Recording | Small blue indicator, restrained audio bars | “Listening…” / “Stop recording” |
| Processing | Small progress indicator | “Checking your request…” |
| Speaking | Playback icon and text response | “Reading payment details” / “Stop read-back” |
| Ready to confirm | Outlined mic; no success color; review card remains visible | “Say ‘confirm payment’ or press Confirm” |
| Unavailable | Neutral disabled mic and inline explanation | “Voice unavailable. You can type instead.” |

Use measured input amplitude for recording bars when available. Do not show a moving waveform that falsely suggests the microphone is active. An animation must stop as soon as capture stops.

In the first release, the mic is unavailable during read-back. Provide a separate Stop read-back button; stopping audio does not silently activate voice approval. Users can replay or confirm through the permitted button path.

No always-listening mode, hidden hotkey capture, or automatic recording after refresh. Keyboard shortcuts must not fire while the user types in an input.

### 9.1 The speaking payment card

This is Sendly's signature interaction. It is an enhancement layered on a card that is already fully readable; nothing depends on it.

**Follow-along read-back.** While the read-back plays, the card marks the detail currently being spoken: amount, then recipient and assurance label, then address suffix, network, and fee. The mark is a 2px accent underline plus a slightly darker text color, never a background flash.

- **Timing source.** Use real playback timings: word or segment timestamps from the TTS provider, or one audio segment per field played in sequence. Align to the audio element's actual playback position, not to a timer started when playback was requested.
- **Fallback.** If timing data is missing, late, or drifts beyond a small tolerance, stop tracking fields and give the whole card a quiet “being read” outline until playback ends. Never pretend to track individual words.
- **Always available:** captions for the spoken text, and the payment details themselves, regardless of highlighting.
- **Reduced motion:** no moving underline; a static whole-card outline during playback.
- **Screen readers:** the highlight is visual only. Do not move focus or announce each field; the read-back captions and the card content already carry the information.

**Visible correction.** When a correction changes a field, show the change in place for about 2 seconds: the old value struck through in muted text, an arrow, and the new value at full weight (`50 → 15 DemoUSD`). Then settle to the new value alone. The new value is never smaller, lighter, or less prominent than the old one at any point.

- Announce once through a polite live region: “Amount changed from 50 to 15 DemoUSD” (or “Recipient changed from Mom to Dad”).
- Corrections to several fields show each change; announce them in one sentence.
- Reduced motion: no transition; the new value appears with a static “Changed from 50” note that remains until the next read-back starts.
- The new read-back's follow-along starts only after the change has settled, so the two effects never overlap.

## 10. Transaction status presentation

Display user-facing descriptions rather than internal enums. Preserve the approved recipient and amount while status changes.

| Backend meaning | Heading | Supporting copy / action |
|---|---|---|
| Signing | Approve in your wallet | “Complete the wallet prompt to continue.” |
| Submitted | Payment submitted | “Waiting for network confirmation.” |
| Included, not finalized | Payment included | “Waiting for it to be finalized.” |
| Succeeded, finalized | Payment sent | Amount, recipient, receipt, explorer link |
| Succeeded + fee-field mismatch | Payment sent | Separate caution notice: “Your wallet used different network-fee settings than approved. Fee charged: [amount]. We've flagged this for review.” No send-again action |
| Succeeded at an unexpected nonce (incident) | Payment sent | Separate caution notice: “Your wallet handled this payment unusually. The transfer is verified; we're checking your wallet before you send more.” New payments from this wallet unavailable until resolved |
| Explicitly rejected in wallet | You declined in your wallet | “Nothing was sent.” Offer **Try wallet again** only if `capabilities.retry_wallet.allowed`; otherwise **Review again** |
| Reverted, finalized | Payment failed | “The transfer failed. A network fee may have been charged.” |
| Unknown / reconciling | Checking payment status | “Don't send again yet. We're checking what happened.” Status refresh and details; replacement review only if `capabilities.review_replacement.allowed` |
| Nonce consumed by another transaction | Payment wasn't made as approved | “A different transaction from your wallet used its place. Check it before sending again.” Link to that transaction |
| Payload mismatch | Payment needs review | Show the verified transaction facts; no send-again or retry action |
| Review expired | Review expired | “Review the details again to continue.” **Review again** |
| Wallet busy (open reservation) | Finish your earlier payment first | “Sendly is still confirming a payment from this wallet.” Link to that payment |
| Limit exceeded | Over your limit | “You can send up to [remaining] DemoUSD more today.” Keep the draft editable |
| Reserve-balance risk | Try again in a few seconds | “Your wallet has recent activity. We'll be able to check this payment shortly.” |
| Unsupported wallet type | This wallet can't send yet | “Sendly doesn't support this wallet type in the test release.” |
| Sending unavailable (signer not qualified) | Sending is unavailable | “You can review payments, but sending is turned off right now.” Review remains usable; Confirm disabled |

Copy in this table is illustrative; the central status module (Section 17) holds the shipped strings and maps every backend state and capability reason to exactly one entry.

Use a small vertical status timeline with text labels. Do not show a made-up percentage or completion countdown. Duration estimates must not become promises.

Unknown state uses a persistent inline caution panel, not an alarming red full-screen error. Offer receipt/details access and safe status refresh. Replacement recovery appears only when the backend explicitly enables it and opens a separate review with its own fee ceiling.

**Success must preserve context:** amount, recipient, network, time, and receipt action. An animated checkmark is optional; a clear sentence is mandatory. Use “Make another payment” to begin a new draft, not a replay of the completed action.

## 11. Supporting screens

### Activity

Desktop uses a simple aligned table; mobile uses rows with stacked metadata. Columns: contact/direction, amount/unit, status, and date. Avoid financial charts without a user need.

Each row opens the receipt. Long-pending items remain easy to find. Incoming activity appears only when that capability is implemented. Unknown senders are labeled by address; do not infer identity or automatically save them as contacts.

### Contacts

Search field, clear Add contact action, restrained initial avatars, name, address preview, and assurance label. Neither label claims a verified real-world person, and neither uses a checkmark or green.

| PRD level | Card and list label | Spoken in read-back | Explanation (shown on tap/expand) |
|---|---|---|---|
| `user_confirmed` | Saved address | “the address you saved for Mom, ending 4821” | “You entered and confirmed this address. Sendly can't tell who controls it.” |
| `ownership_proven` | Linked Sendly wallet | “Mom's Sendly wallet, ending 4821” | “This address belongs to the Sendly account that shared its link code with you. Sendly can't confirm who uses that account.” |
| `pending_confirmation` | Needs confirmation | Not read back (not payable) | “Review the full address to finish adding this contact.” |

Creation is a short form: name, address, network, then full-address review. Pasted address errors appear beneath the field. Contact names are rendered as text, never HTML.

### Receive

Network, asset guidance, address, Copy, and QR. The QR must encode the actual supported destination format. Label it clearly; scanning should not imply support for every asset or network. Link-code creation appears only when implemented.

### Onboarding

One step at a time: sign in → wallet ready → funding status → add a contact → send. Keep clear progress through required setup. Test-funding instructions should be actionable and honest; do not create a decorative “Get started” button that leads to an unfunded dead end.

### Settings

Group by account/wallet, voice preferences, and data controls. Explain audio retention in plain language. Do not claim data stays on-device when hosted providers process it.

## 12. Component standards

### Buttons

- Primary: charcoal background, white text, 48px height, 10px radius.
- Secondary: white background, visible border, charcoal label.
- Quiet action: text with underline on hover/focus where appropriate.
- Destructive action: red text and explicit verb; do not style normal cancellation as a dangerous deletion.
- Loading: retain label and width; add a small spinner, prevent duplicate activation.
- Disabled: explain why nearby when the reason affects progress. Do not rely on an inaccessible tooltip.

One primary action per active decision. When payment review is active, confirming payment is the primary action; opening the mic is secondary.

### Inputs

Persistent visible label, 48px minimum height, 16px text, useful placeholder, and inline validation. Errors identify the fix: “Enter an amount greater than zero” rather than “Invalid value.” Do not clear entered values after an error.

Use `inputMode="decimal"` as a keyboard hint for amounts, while validating exact decimal strings. Locale formatting must not change the underlying monetary value unexpectedly.

### Dialogs and sheets

Use dialogs for distinct decisions such as replacement review, not for every stage of the happy path. Keep ordinary payment review inline.

On mobile, a bottom sheet can host recipient selection; a full-height view is preferable if a long form would be obscured by the keyboard. Dialogs manage focus, have a visible close action, return focus to their trigger, and preserve unfinished input as appropriate.

### Toasts

Use for minor feedback such as “Address copied.” Never make a toast the only location for a payment result, fee discrepancy, or unknown-outcome warning.

### Icons

Use one consistent outlined icon family, approximately 20px with a consistent stroke. Candidates include microphone, stop, check, clock, arrow, copy, and external link. Use labels for ambiguous icons. Decorative icons are hidden from assistive technology.

## 13. Responsive behavior

| Width | Layout |
|---|---|
| Under 768px | Single column; main payment card first; balance compact; recent activity below |
| 768–1023px | Single column with a wider maximum content width; optional compact supporting row |
| 1024px and above | Two-column workspace with roughly 320px supporting panel |

Keep the confirmation controls close to the payment details. Do not make a sticky footer cover recipient, amount, fee, errors, or keyboard input. If the action area is sticky, reserve its space and respect safe-area insets.

Test at 320px, 375px, 768px, 1024px, and 1440px, with long names, long amounts, zoom, software keyboard, and expanded address details. No core action should require horizontal scrolling.

Use responsive reflow rather than hiding meaningful information to fit a screen.

## 14. Motion and feedback

- Hover/focus transitions: 120–160ms.
- Expand/collapse and short state changes: 160–220ms.
- Animate opacity and small transforms, not layout-critical numeric values.
- Preserve component height during loading to avoid jumping controls.
- Show immediate local recording feedback; wait for backend evidence before showing payment progress.
- Respect reduced-motion preferences with static state changes and no pulsing waveform.
- Do not use confetti, repeated attention pulses, spinning coins, or dramatic full-screen transitions.

No animation changes the timing or semantics of approval expiry.

## 15. Accessibility and trust checks

These are implementation targets; passing a checklist is not a substitute for testing.

- All core interactions work without speaking or hearing.
- Target at least 4.5:1 contrast for normal text and 3:1 for qualifying large text and necessary UI boundaries.
- Focus is visible, has sufficient contrast, and is not hidden under a sticky element.
- Use real buttons, inputs, headings, lists, tables, and landmarks.
- Announce finalized transcript changes and material payment states through carefully scoped live regions.
- Do not announce every audio frame, token, timer tick, or polling response.
- No information depends only on color or hover.
- The user can expand, select, and copy a full wallet address.
- Display approval expiration and provide a clear “Review again” path; do not auto-approve or auto-resend.
- Successful transfers and compliance warnings remain separate visually and semantically.
- Follow-along highlighting is never the only cue; captions and card content carry the same information, and reduced-motion users get the static alternative.
- Correction announcements fire once per change, not per animation frame.
- Permission denial, provider failure, and loss of connection have useful text fallbacks.
- Screen reader order follows visual review order.
- Support 200% text zoom and narrow-screen reflow without loss of controls.

Reference for implementation validation: [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

## 16. CSS foundation

These are proposed design tokens, not an installed stylesheet.

```css
:root {
  --font-sans: "Inter", ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Consolas, monospace;

  --canvas: #ffffff;
  --surface: #ffffff;
  --surface-subtle: #f8fafc;
  --surface-pressed: #f1f5f9;
  --text-primary: #111827;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --border: #e2e8f0;
  --control-border: #64748b;
  --action: #111827;
  --action-hover: #1f2937;
  --accent: #1d4ed8;
  --accent-soft: #eff6ff;
  --success: #166534;
  --success-soft: #f0fdf4;
  --warning: #92400e;
  --warning-soft: #fffbeb;
  --danger: #b91c1c;
  --danger-soft: #fef2f2;

  --radius-control: 10px;
  --radius-card: 16px;
  --shadow-card: 0 4px 20px rgb(15 23 42 / 0.04);
  --content-max: 1120px;
}

body {
  margin: 0;
  font-family: var(--font-sans);
  color: var(--text-primary);
  background: var(--canvas);
  line-height: 1.5;
}

.amount,
.balance,
.fee {
  font-variant-numeric: tabular-nums lining-nums;
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}

.payment-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 20px;
  box-shadow: var(--shadow-card);
}

@media (min-width: 768px) {
  .payment-card { padding: 32px; }
}

@media (prefers-reduced-motion: reduce) {
  .voice-bars,
  .status-pulse { animation: none; }

  .payment-card,
  .status-panel { transition: none; }
}
```

Map these tokens into the project's selected CSS/Tailwind version. Keep semantic names in components; do not scatter arbitrary hex codes throughout JSX.

## 17. Frontend implementation guidance

- Use reusable components: `AppHeader`, `EnvironmentBadge`, `PaymentReviewCard`, `AmountDisplay`, `RecipientSummary`, `VoiceControls`, `TranscriptFeed`, `PaymentStatus`, `Receipt`, and `InlineNotice`.
- Use an accessible component primitive library where it helps keyboard/focus behavior; customize its visual defaults to these tokens.
- Keep authoritative payment status in server-state queries/subscriptions. A separate reducer may manage recording and playback UI.
- Render the backend `capabilities` object (PRD Section 13): each action has `allowed` and, when false, a `reason` such as `review_expired`, `readback_in_progress`, `wallet_busy`, or `signer_not_qualified`. Map reasons to copy in the central status module. Never derive permissions from button history, and remember the backend enforces them again when the action is requested.
- Scope mutations to revision and attempt IDs. Disable stale action controls as soon as a correction occurs.
- Cancel stale audio playback and ignore stale asynchronous responses when the active revision changes.
- Never optimistically update a payment to sent or fabricate an incoming receipt.
- When wallet UI opens, preserve the review card underneath and restore focus coherently on return.
- Route-level skeletons preserve layout. A skeleton is not an invented balance.
- Escape text content and render addresses/labels safely; do not use raw HTML for transcripts or contact names.
- Protect private receipts and account data from unintended caching and public rendering.
- Derive copy and status mapping from one central module so every screen uses the same meaning for submitted, included, and sent.
- Drive follow-along highlighting from the audio element's playback position and the provider's timings; fall back to the whole-card outline when timings are missing or drift.
- Dark mode is out of scope for the first release. Keep colors in semantic tokens so it can be added later without touching components.

## 18. Design review checklist

Before considering the frontend ready:

1. Can a first-time tester identify recipient, amount, asset, network, and maximum fee before approving?
2. Is it obvious when the microphone is recording, stopped, or unavailable?
3. Does a correction remove the old approval and show the changed value clearly?
4. Does a successful payment remain visibly successful when a separate fee warning exists?
5. Does unknown status block duplicate-send actions while explaining what happens next?
6. Can the whole supported flow be completed with text and keyboard?
7. Are loading, empty, expired, rejected, failed, and disconnected states designed rather than improvised?
8. Do long contact names, long decimals, and full addresses fit without truncating critical data?
9. Are test funds clearly identified everywhere a payment can be approved?
10. Does the rendered interface still feel simple after all meaningful details are present?
11. During read-back, does the card show which detail is being spoken, and fall back to a whole-card outline when timings are unavailable?
12. Is a spoken correction visible as a change on the card and announced once?
13. Is Confirm the only solid primary action during review, with the microphone outlined and positioned apart from it?
14. Does every state in the Section 10 table, including expiry, wallet busy, limits, and sending unavailable, have designed copy and a safe next action?

## 19. Compact implementation brief

> Build Sendly as a white, minimal payments interface using Next.js, React, and TypeScript. Use Inter, charcoal headings and primary buttons, restrained blue focus/listening cues, thin neutral borders, 16px card radii, and generous spacing. Make the recipient and payment amount the focal point. The signature interaction is the speaking payment card: it marks each detail as it is read aloud (using real playback timings, else a whole-card outline) and shows spoken corrections as a visible change. Use a compact, outlined-during-review voice control and conversation log supporting a persistent payment review card. Show explicit units, network, and fee bounds. Use green only for finalized success, and keep unknown outcomes visibly unresolved. Keep every action accessible by keyboard and text. Implement complete states and responsive layouts without decorative gradients, glowing AI orbs, fabricated activity, or extra dashboard clutter. Follow the PRD for all payment authorization and recovery behavior.

## 20. Revision history

**1.1 (October 5, 2026).** Speaking payment card added as the signature interaction (follow-along read-back with timing fallback; visible corrections). Status table completed (expired review, wallet busy, limit exceeded, reserve risk, unsupported wallet, sending unavailable, nonce consumed by another transaction, nonce incident shown as sent). Contact assurance labels unified (“Saved address,” “Linked Sendly wallet”) with spoken equivalents. Confirm button states by review state; outlined microphone during review; stable separate positions; accidental-tap guard that only delays. Quiet expiry. Backend `capabilities` with reasons. Ownership split: this guide owns layout, the PRD owns behavior. Inter remains the only typeface.
