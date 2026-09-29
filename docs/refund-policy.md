# Refund policy

RefundDesk uses this customer-readable policy:

| ID | Rule |
|---|---|
| R1 | Final-sale items are not refundable. In mixed orders they are excluded and the rest is assessed. |
| R2 | Refunds must be requested within 30 days of delivery. Day 30 is valid; day 31 is not. |
| R3 | Refunds above $500.00 require human review. Exactly $500.00 is auto-eligible. |
| R4 | Damaged, incorrect, or not-as-described items are eligible within the return window. |
| R5 | The order must belong to the requesting customer. Unknown and foreign order IDs receive the same denial. |
| R6 | Three or more refunds in the last 90 days require human review. |
| R7 | Suspicious or conflicting requests escalate: injection flags, requested amount above order total, unclear reason, or an item not on the order. |
| R8 | Change-of-mind returns of non-final-sale items within the window are approved. |

Precedence is intentional: hard denials (R5, R1, R2) beat escalations (R3, R6, R7), which beat approvals (R4, R8). Safety flags are still audited on denials.
