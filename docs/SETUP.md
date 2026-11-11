# Configuration and operator flow

## Roles and staff identity

Assign native permissions separately; the optical groups do not silently grant Inventory, Sales, Purchase, Accounting or HR administration.

| Role | Optical permissions | Additional native access |
|---|---|---|
| Coordinator | Jobs, scans, SOP completions, operational exceptions and nonclinical audit | Contacts/Sales; Inventory and Purchase only as required |
| Authorized clinician / dispenser | Restricted prescriptions, specifications, quality decisions and laboratory tickets | Native records needed for their duties; invoicing access is required by the current collection payment check |
| Optical manager | SOP approval, exception resolution and cancellation | Native management permissions only where required; **does not grant clinical access** |

Create one employee per user/company and link Related User in Employees. Every optical actor must use their own login; a shared terminal login cannot identify who actually performed a clinical or approval action. Configure allowed companies. No optical/clinical rights are auto-granted to ordinary internal users.

Review the proposed clinical fields, prescription validity, PD/fitting units, quality criteria, payment/collection policy, warranty terms, retention and access matrix with the client's responsible optical professional. The software does not determine a prescription or clinical suitability.

## Stock and existing catalogue

Native frame products must be storable and tracked by serial. Mark appropriate products as Optical frame. Each newly received serial gets a unique `PSF-` optical scan code; on existing serial records use **Assign optical scan code** after reconciling real physical stock. The six website catalogue samples have no opening quantity and must not be treated as received stock.

The SKU barcode identifies the product type. The optical scan code identifies one physical unit. Use native serial labels/stock operations for receiving, stocktaking and returns; optical job labels are for the paired job/frame workflow. Validate the actual scanner and label stock before deployment. The generic PDF labels are not a configured thermal-printer template.

Configure a dedicated **internal** company stock location for company-owned frames at an external laboratory. An external lab does not take ownership of that stock. Use native internal transfers out and back. Laboratory lens/service procurement stays on a native PO, receipt and vendor bill, with landed costs where configured.

## Normal pair

1. Register the patient as a native Contact. A clinician records and approves the prescription in Optical → Prescriptions.
2. Create/confirm the native quotation. Use a separate frame sale line of quantity one for each pair. For customer-owned frames, sell the required lens/service lines; record frame identity/condition on the job instead of allocating company stock.
3. Create one optical job per pair; link the order, frame line/serial and internal lab location. Link a native assigned transfer containing the selected frame as reservation evidence. Record restricted lens specifications and measurements.
4. Print the job/frame labels. Scan Reservation and Quality control. Complete the approved pre-lab checklist, then Verify for lab. An initial draft SOP must first be reviewed/approved by a manager.
5. Create the native lab PO and link it to the job before confirming it. Issue the restricted lab ticket for manual delivery through the lab's approved channel. No automatic email is sent.
6. Link the native transfer to the lab and scan Dispatch. If the customer delivery already reserves the frame, release that reservation in native Inventory so the internal lab transfer can reserve the same serial. Validate the transfer in Inventory, then record lab dispatch on the job.
7. Record the supplier acknowledgment/reference/promised date and manual production/edging progress. Use the Overdue filter and native activities for follow-up.
8. Link/validate the internal transfer back from the lab, scan Receipt and record lab receipt. Scan Quality control again and record incoming inspection. A failed check blocks readiness.
9. Mark ready for fitting. Scan Quality control again, complete the fitting check and scan Collection. Record customer identity/collection confirmation. Reserve the frame on the native customer delivery, validate it, record native invoice/payment and complete dispensing.
10. Record warranty/follow-up dates before final completion. Use native activities and aftercare cases for later contact. Completed jobs cannot be overwritten.

This first release requires posted invoices with payment status Paid or In Payment before final optical dispensing. Credit terms, deposit thresholds and special collection overrides are not yet configurable. Native physical delivery is gated by final QC; native payment timing remains separately checked at optical dispensing. The client must approve or replace this policy before live use.

## Exceptions

Record failures with a new quality decision; prior decisions stay visible. Change specifications only before lab dispatch; changes invalidate earlier checks and scans. After production starts, open an exception, resolve native stock/procurement, obtain manager approval and create a fresh replacement job. Allocate the replacement's actual stock and prescription rather than silently copying the original.

Cancellation does not cancel a sale, PO, payment or return inventory automatically. Resolve those documents in their native apps. A damaged/unrecoverable frame and supplier compensation need the corresponding native scrap/claim/credit flow and acceptance testing before use.

## SOP approval

The supplied 16 SOPs are review drafts, not client-approved operating policies. Managers may refine drafts and approve them; approved text is immutable. For changes, create a new version. Quality checks require an approved matching SOP. The other SOP signoffs are supported records, but are not yet all mandatory transition gates. End-of-day totals remain in native POS/Accounting; an optical day-end reconciliation screen is not part of this release.
