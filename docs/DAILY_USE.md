# Daily operation and client walkthrough

## Starting a pair

Open **Optical** from Odoo's app switcher. The job board shows every stage; cards identify the customer, frame, due date, lab and order. Use **Overdue**, **At laboratory**, **Awaiting incoming QC**, **Customer-owned frames** and **Open aftercare** filters to focus the work.

The **Optical jobs** button on a native Contact or quotation/sales order opens the related jobs. Creating a job there pre-fills the customer and, from Sales, the order. Create a separate job for every pair and choose its quantity-one frame line. No quotation, purchase, stock transfer or payment is silently confirmed by these shortcuts.

Each job has a **Next step** panel, restricted-specification/QC buttons, native order links and an aftercare shortcut. The guidance describes the required work; it is not a replacement for the server's actual stock, QC and payment checks.

On frame products, maintain verified brand, model, colour and dimensions under **Optical identification**. Keep actual saleable choices in native variants, suppliers in Purchase, prices in native pricing and quantities/locations in Inventory. A verified job preserves a snapshot of the frame metadata. Unknown supplier details should stay blank rather than be guessed.

## Print documents

| Document | Who can print | Purpose |
|---|---|---|
| Job sheet | Optical coordinator, manager or clinician | Operational reference with job/customer/frame/native document links and current stage. No prescription or lens details. |
| Job + frame labels | Optical staff | Two distinct Code128 identifiers; the product SKU alone does not identify a physical frame. Generic A4 output until the actual label printer is configured. |
| Collection reference | Optical staff | Customer-facing job reference with status, estimate and any recorded dispensing/warranty/follow-up dates. Not an invoice or proof of payment; printing does not complete collection. |
| Prescription | Authorized clinical staff | Restricted prescription version, approval details and clinical notes. Drafts are visibly marked as unapproved. |
| Laboratory ticket | Authorized clinical staff after verification | Immutable issue snapshot with right/left prescription, lens specifications and measurements for the lab. |

Use native Sales/Accounting print actions for quotations, invoices, credits and receipts. Use native Purchase/Inventory reports for POs, stock receipts and transfers. Do not put clinical notes into those shared descriptions.

## Exceptions and SOPs

Open **Aftercare cases** on the job, then **New**, to retain the original pair reference. Record the issue, responsibility, planned resolution and native stock/financial treatment. The manager approves the resolution before a replacement job is created. Approval does not itself issue a credit, scrap stock or refund a payment.

Use **Record SOP completion** on the job to select an approved procedure. Supplied SOPs remain client-review drafts until the responsible client personnel approve their wording. For QC, scan **Quality control** and select the approved checklist for that exact stage. A failed decision remains visible; record a new decision after correction.

## Walkthrough acceptance

- Confirm separate jobs for two pairs on one native order, with the correct patient, quantity-one line and unique frame per pair.
- Verify a customer-owned frame records identity/condition and never creates company stock.
- Reject a wrong job/frame code and a product SKU used as a physical-frame code. Confirm correct scans record user/time/revision.
- Verify that an unconfirmed quotation, missing native stock reservation, missing prescription, expired prescription, missing scan or failed/missing QC prevents the next step.
- Review aftercare/SOP selectors and their links; approve an actual policy only after client review.
- Preview and print every document. Verify barcode readability, margins, long text, correct right/left values and draft/status warnings on the actual printer.
- Check that a coordinator and a nonclinical manager cannot open or print restricted prescriptions/lab tickets, and that company boundaries remain enforced.
- Reconcile the end-to-end stock, invoicing/payment and exception scenarios in a staging database before live use.

The website's illustrative catalogue prices/specifications and the clearly named walkthrough records must not be mistaken for received stock, genuine patient prescriptions, posted transactions or client-approved policies. Full go-live gaps remain listed in **RELEASE_SCOPE.md** and **CLIENT_REQUIREMENTS.md**.
