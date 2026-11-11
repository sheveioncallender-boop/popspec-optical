# Pop Spec optical operations — agreed future scope

Status: requirements retained for the subsequent optical module; not implemented in the website release. Platform: **Odoo 19 Community**. Preserve native Odoo navigation, records and transaction workflows. Extend existing apps with optical-specific records, smart buttons, fields, security and gates. Do not create parallel stock, purchasing, invoicing, payment or employee ledgers. Every client requirement below remains in scope; none is silently removed because an integration needs a provider or a paid/third-party component.

## Business coverage and acceptance

| Requirement | Native foundation and required extension | Acceptance evidence |
|---|---|---|
| Purchasing: supplier orders, landed costs, goods received | Native Purchase, Inventory, vendor bills and landed costs; optical procurement links | Supplier PO → receipt with frame serials → bill → landed cost allocation and valuation |
| Accounting: sales, expenses, taxes, bank reconciliation, financial statements — essential | Native Sales/Invoices/POS as configured; choose and validate Community-compatible reporting and bank reconciliation components before committing to full feature coverage | Sale/refund/tax/expense examples reconcile to ledger, bank and financial reports |
| Customer/patient history, purchases, reminders, warranties — essential | Native contacts and purchases; separate restricted clinical records, prescription versions, follow-up activities and warranty cases | One patient shows permitted purchase/service history; clinical data denied to unauthorized users |
| Scanners, printers, tablets, cash drawers, label printers — essential | Native Inventory/POS/print flows plus validated device interfaces; barcode/serial labels | Receiving, sale, cash drawer, barcode print and scanning work on actual specified hardware |
| HR, clock-in/out, shifts, leave, permissions — important | Native Employees, Attendances and Time Off; Community-compatible shift scheduling and role permissions | Employee attendance, scheduled shifts and approved leave reconcile |
| Security integration — important | Device-specific access-event adapter, employee identity mapping and exception reporting | Real door event maps to employee; duplicate/out-of-order/offline events and exceptions handled |
| Marketing: WhatsApp, SMS, email, loyalty and follow-ups — important | Native activities/email/loyalty where available; approved messaging-provider connectors, consent and suppression | Opt-in campaign, opt-out, delivery result and follow-up trigger verified |
| Laboratory: lens production, edging, QC, machine integration — future-ready | Optical lab jobs linked to native purchasing or manufacturing where appropriate; machine-specific adapters | Acknowledgment, production stages, edging and QC evidence; adapter tested against actual protocol |
| Ecommerce: frames, bookings and payments — future-ready | Current website uses native shop; appointment capacity/confirmation and payment-provider integration configured later | Published catalogue → genuine booking/payment confirmation → Odoo records |
| Social media referral | Native UTM/source/campaign capture on leads and orders; define rewards only if requested | Source survives referral journey and is attributable in reports without exposing clinical data |

## Nine mandatory operational requirements

### 1. Frame identification

Every physical frame needs a unique scannable serial identifier, not merely a SKU barcode. Extend native product variants and serial/lot records to link SKU, brand, model, colour, size, supplier, acquisition cost, selling price, location and stock status. Stock status/location come from native quants/moves. Define barcode uniqueness scope and enforce it. Existing stock requires controlled serial assignment and reconciliation.

### 2. Patient-to-product linking

Maintain permanent links between patient, immutable approved prescription version, selected physical frame/serial, right/left lens specifications, optical job, laboratory order, native sales order/invoice/payment references and final dispensing record. A revised prescription creates a new version; it must not rewrite the version used by an earlier job. Shared contact, messages, portal routes, exports, attachments and reports must not leak clinical details.

### 3. One job per pair

Generate a unique optical job number per pair of spectacles. Multiple pairs belong to separate jobs linked to the same customer/order. Include approved prescription, frame or customer-owned-frame details, right/left lens specifications, optical measurements, lab instructions, financial links, staff approvals and estimated delivery date. Financial balances come from native posted transactions; do not manually maintain an optical payment ledger.

### 4. Barcode-controlled workflow

Support scanning during receiving, label printing, reservation, dispatch to laboratory, lab receipt, QC, collection, returns and stocktaking. Use native stock reservations/transfers/moves for inventory ownership and quantity changes. Gate each optical event on the correct job and physical serial. Handle duplicate scans, wrong serials, partial receipts, returns and concurrent reservations. A status change alone cannot count as a stock movement.

### 5. Laboratory integration

Generate a restricted laboratory ticket; record supplier acknowledgment, external status, promised date and overdue flag. Support corrections, cancellation and remakes with explicit references and reasons. Preserve earlier ticket versions. Establish the external lab's API/file/email/manual handoff capabilities and machine protocols before choosing adapters; no universal automatic integration is assumed.

### 6. Mandatory quality controls

Require documented checks (with named staff and timestamps) before lab ordering, at lab receipt and before final fitting/dispensing. Failed checks block onward progression. A material prescription/frame/lens/measurement change invalidates affected earlier approvals and requires rechecking. Define which roles can approve and which overrides require separate authorized approval.

### 7. SOP coverage

Versioned SOPs and workflow checklists must cover customer registration, clinical prescriptions, frame selection, measurements, quotation approval, job creation, supplier procurement, laboratory dispatch, goods receipt, QC, dispensing, remakes, warranties, inventory management and end-of-day reconciliation. Record which SOP version was applied to the job and who completed each required step. End-of-day uses native POS/cash/accounting totals and highlights unresolved differences.

### 8. Exceptions

Explicit workflows for customer-owned frames, multiple pairs, prescription changes, supplier errors, damaged frames, warranty replacements, uncollected jobs and customer complaints. Preserve the original job when creating remakes/replacements. Record reason, responsibility, approval, cost treatment and customer communication. Do not create owned stock or fictitious purchase costs for customer-owned frames. Define uncollected-job reminders and escalation policies with the client.

### 9. Security and accountability

Every material prescription/job/inventory/discount/refund/QC change needs the actual responsible employee, timestamp, before/after values where appropriate, reason and relevant approval. Enforce rules server-side, including imports/RPC; hiding a field or button is insufficient. Shared logins and POS employee identities need explicit attribution. Clinical roles, optical sales, lab coordination, QC/dispensing, inventory, finance and management require least-privilege access and company isolation. Lab staff receive only the clinical data necessary for their task. Chatter alone is not a complete immutable audit design. Define retention, backup/restore and audit export controls.

## Proposed flow within Odoo

Contact/patient registration → prescription version → native quotation and frame selection → quotation approval/payment policy → one optical job per pair → pre-lab verification → native procurement/stock dispatch → lab acknowledgment/progress → native receipt → incoming QC → final fitting/dispensing verification → native delivery/collection and financial completion → aftercare/warranty.

Cancellation, failed QC, corrections and remakes branch from this flow with approvals and preserved history. They never bypass native stock/accounting validations. The client must confirm exact roles, deposit/collection policies, job stages and QC/SOP checklists before those gates are finalized.

## Details needed before implementation/integration

- Branches, locations, staff roles, data migration sources and clinical access matrix.
- Prescription/measurement fields and validation ranges approved by the client's optical professional.
- Lab suppliers, formats, acknowledgment/progress channels, production and edging machines/protocols.
- Scanner, receipt/label printer, cash drawer, tablet and door-access device models.
- Payment/bank services, approved accounting/reporting components and company accounting configuration.
- Messaging providers, consent/opt-out policy, verified WhatsApp/social accounts and campaign rules.
- Scheduling/appointments, shift rules, warranty policy, return/remake approval policy and uncollected-job policy.

## Go-live tests

Test normal completed sale, multiple pairs, customer-owned frame, mid-job prescription revision, wrong serial scan, concurrent frame reservation, supplier error, QC failure/remake, damaged frame, refund/discount approval, warranty replacement, uncollected order, complaint and day-end reconciliation. Test unauthorized clinical access through UI, RPC, export, attachments, portal and reports. Prove device/provider failures, retries and duplicate events cannot silently corrupt stock, finances or patient/job relationships. All mandatory requirements need evidence, not just menu entries.
