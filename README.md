# Pop Spec Optical Operations — Odoo 19

Version **19.0.1.1.0** · Spxcorp Limited · LGPL-3

First operational release for controlled spectacle jobs. This is separate from `popspec_website` and extends native Odoo Sales, Purchase, Inventory, Accounting and Employees. It does not create a second stock, invoice, payment or HR ledger.

## Implemented

- One optical job per pair, permanent patient/order/frame links, exclusive active allocation of physical frame serials and native UTM referral fields.
- Restricted prescription records, approval, immutable versions, right/left lens specifications and measurements.
- Company stock and customer-owned frames; customer frames never generate company stock.
- Paired job/frame scanning with wrong-scan protection, stage-specific evidence and duplicate-scan handling.
- Native transfer/reservation evidence; pre-lab, incoming and final-fitting QC gates. Specification changes invalidate checks; production-stage changes require an exception/replacement.
- Lab supplier/PO links, manual acknowledgment/progress, promised dates, overdue jobs and immutable restricted lab-ticket versions.
- Dispensing attribution, native delivery/payment checks, warranty/follow-up dates and activities.
- Approved exception/remake cases, draft SOP library, versioned approved SOPs, signoffs and immutable application-level audit records.
- Native list, form and Kanban views with stage guidance, overdue/aftercare filters and direct links from Contacts and Sales.
- Visible print actions for operational job sheets, job/frame labels, collection references, restricted prescriptions and restricted lab tickets. Operational documents exclude prescription and lens details.
- Structured frame brand/model/colour/dimensions, preserved in the verified frame snapshot; native product variants, suppliers, pricing and stock remain authoritative.
- Job selectors in aftercare, SOP completion and clinical/QC forms work before a related company has been populated, with company rules still enforced.

## Installation on CloudPepper

1. Add this repository to the Pop Spec instance's custom addons, branch `main`. The addon folder is `popspec_optical` at the repository root.
2. Pull/build the addons, then update the Odoo Apps list and install **Pop Spec Optical Operations**. Existing website products and pages are not rewritten by this module.
3. Follow [SETUP.md](docs/SETUP.md) before entering real patient records or live jobs. In particular, assign roles, map each staff login to an employee, approve the client's SOPs and configure native stock/accounting.
4. Use a staging database and the acceptance checklist before production. Installation alone is not clinical, financial, hardware or integration acceptance.

For an existing installation, pull branch `main` in CloudPepper, rebuild/restart its addons as required, then upgrade **Pop Spec Optical Operations** to **19.0.1.1.0**. Refresh the browser after upgrading. Existing jobs and approved evidence are preserved; this update does not approve SOPs or create inventory, payments or patient records.

[DAILY_USE.md](docs/DAILY_USE.md) explains the operating screens, print documents and walkthrough checks.

## Scope and acceptance

[CLIENT_REQUIREMENTS.md](docs/CLIENT_REQUIREMENTS.md) retains every client requirement. [RELEASE_SCOPE.md](docs/RELEASE_SCOPE.md) distinguishes implemented controls from remaining work. This initial release is **not the full optical go-live**. No hardware, door-controller, WhatsApp/SMS, machine, bank or laboratory API connection is claimed without provider/device validation.

## Tests

`python scripts/validate.py` checks source and XML. GitHub Actions installs this addon on a pinned Odoo 19 Community source, runs business/security/report tests and then upgrades the installed database. The test suite uses fictional fixtures only. Test log artifacts are retained by CI.

The audit is immutable through ordinary Odoo ORM/API actions. Database administrators and server code retain administrative power; external tamper-evident audit export and retention/backup validation are additional deployment work.
