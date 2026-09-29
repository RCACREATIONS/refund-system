# RefundDesk demo script (4–5 minutes)

## 0:00–0:20 — What this is

“RefundDesk is a customer-support refund workflow where AI helps interpret language, but deterministic code owns the money decision. The important proof is in the receipt, audit trail, Trust Lab, and policy simulator.”

## 0:20–1:20 — Customer flow

Open the customer chat. Choose `clean-approve`, confirm the customer is Amara, and send it. Show the approved receipt for $89 and its checks. Run `final-sale` to show the hard denial. Run `high-value` to show an escalation because the laptop is above the instant-approval threshold.

## 1:20–1:50 — Prompt injection

Choose `prompt-injection`. Show that the message tries to enter admin mode and suppress logging, but the result is escalated. Explain that the screen flag becomes an input to policy and the reply remains neutral; the customer never sees internal rule IDs.

## 1:50–2:50 — Support console

Open Support console and use the default `admin-demo-token`. Point out the seeded historical queue, outcome rates, pending escalations, and total refunded. Open a request to show the vertical audit timeline. Resolve a pending escalation with Approve or Deny.

## 2:50–3:35 — Trust Lab

Click Run red team. Explain that the same pipeline processes direct overrides, fake role markers, amount inflation, order tampering, and exfiltration attempts. The mock mode should pass every invariant: suspicious attacks do not get approved and customer replies do not disclose internal details.

## 3:35–4:20 — Policy Simulator

Click Simulate change. It replays each stored `policy_input` snapshot without an LLM call. Show how the proposed window, threshold, and repeat-refund limit change outcomes and refund exposure before a policy owner ships a change.

## 4:20–4:50 — Architecture and close

Show the README diagram. Close with: “The trust principle is AI proposes, code disposes. A live OpenAI-compatible provider is optional; the cold-start demo works with no key.”
