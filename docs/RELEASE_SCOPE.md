# Release coverage and remaining acceptance

This is the first operational release, not a declaration that all client requirements are complete. Every original requirement remains in scope.

| Client area | Included now | Remaining before full go-live |
|---|---|---|
| Frame identity | Native SKU/serial + globally unique optical code, active-job uniqueness, frame snapshot | Existing stock reconciliation, supplier/acquisition-cost presentation, actual receiving/count/label hardware tests |
| Patient links | Contact → immutable prescription → clinical specs → job → native sale/PO/transfers/invoices → dispensing | Historical migration, detailed payment/refund allocation per pair on multi-pair orders |
| Job orders | One pair per job, both lenses, measurements, approvals, due dates | Client-approved clinical fields/ranges and credit/deposit policies |
| Scanning | Job/frame checks for reservation, dispatch, receipt, QC, collection, returns; native movement evidence | Physical scanners, printer formats, stocktaking/return scenarios and concurrent multi-user acceptance |
| Laboratories | Native PO link, acknowledgment, manual progress, overdue flag, immutable restricted ticket | Supplier API/file/email handoffs, production/edging machines, retries and device protocols |
| QC | Three immutable checks; failed/latest checks block; changes invalidate approval | Client signoff on checklist criteria and staff separation/override policy |
| SOPs | 16 draft SOPs, immutable approved versions, completion evidence; QC SOP gates | Client review, mandatory gates for other SOPs, end-of-day variance workspace |
| Exceptions | Customer-owned frame flow; complaints, supplier error, damage, warranty, uncollected and remake records | All native return/scrap/refund cost paths, automatic reminder/escalation policy |
| Security/audit | Separate clinical ACLs, company rules, protected reports, actual employee/user attribution, immutable optical audit, native dispatch/delivery evidence | Dedicated approval/audit coverage for every native discount/refund and inventory adjustment, shared POS employee attribution, external audit export, retention/restore tests |
| Purchasing/accounting | Native Purchase/Inventory/Sales/Invoices; landed-cost dependency; native payment gate | Community bank reconciliation/reporting components, taxes, financial statements and accounting acceptance |
| HR | Employee identity links; native HR stays separate | Attendances, leave and shift scheduling configuration/integration; device clock-in testing |
| Door access | Requirement retained | Actual controller/reader identification and event adapter, duplicate/offline handling and exception reports |
| Marketing | Native follow-up activities/dates and UTM/source fields | Opt-in/out model, WhatsApp/SMS/email providers, loyalty, campaign delivery/result validation |
| Ecommerce | Existing separate website catalogue preserved | Capacity-based bookings, payment provider, order-to-job workflow and referral attribution journey tests |

## Tests in this repository

Automated tests target prescription immutability/versioning, clinical access including export/report paths, company isolation, employee attribution, immutable evidence, direct workflow bypass attempts, unique physical allocation, wrong/duplicate scans, check invalidation, latest failed-check blocking, customer-owned lab processing, restricted ticket snapshots and approved remake behavior. Native receiving/dispatch/receipt/delivery and financial paths require additional scenario tests and client acceptance before production.

## Inputs needed for the next implementation stage

- Actual lab suppliers and their order/status formats or APIs; edging and lens-production equipment models.
- Scanner, thermal/receipt printer, cash drawer/tablet and door controller models.
- Staff/branch roles; deposit/credit/collection, warranty, remake and uncollected-job policies.
- Messaging provider accounts and opt-in/out rules; bank/payment configuration and chosen Community accounting/reporting components.
- Booking durations/capacity and whether referrals are reporting-only or have a reward policy.
