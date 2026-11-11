from odoo import Command, fields
from odoo.tests import tagged, new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError, UserError, ValidationError
from psycopg2 import IntegrityError
from lxml import etree
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestOptical(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Accounting's common fixture switches to a non-HR user. Build setup data as
        # administrator; every optical workflow/security assertion uses an explicit staff user.
        cls.env = cls.env(su=True)
        company = cls.env.company
        common = 'base.group_allow_export,sales_team.group_sale_salesman,stock.group_stock_user,purchase.group_purchase_user'
        cls.clinician = new_test_user(cls.env, login='optical_clinician', groups=common + ',popspec_optical.group_clinical,popspec_optical.group_manager,account.group_account_invoice')
        cls.operator = new_test_user(cls.env, login='optical_coordinator', groups=common + ',popspec_optical.group_operator')
        cls.manager = new_test_user(cls.env, login='optical_nonclinical_manager', groups=common + ',popspec_optical.group_manager')
        cls.portal = new_test_user(cls.env, login='optical_portal', groups='base.group_portal,base.group_allow_export')
        for user in cls.clinician | cls.operator | cls.manager:
            cls.env['hr.employee'].create({'name': user.name, 'user_id': user.id, 'company_id': company.id})
        cls.patient = cls.env['res.partner'].create({'name': 'Optical test patient'})
        cls.lab = cls.env['res.partner'].create({'name': 'Optical test laboratory'})
        cls.product = cls.env['product.product'].create({'name': 'Test optical frame', 'type': 'consu',
            'is_storable': True, 'tracking': 'serial', 'optical_frame': True, 'list_price': 500,
            'categ_id': cls.product_category.id, 'invoice_policy': 'order', 'taxes_id': [Command.clear()]})
        cls.service = cls.env['product.product'].create({'name': 'Test lens service', 'type': 'service', 'list_price': 100,
            'categ_id': cls.product_category.id, 'invoice_policy': 'order', 'taxes_id': [Command.clear()]})
        cls.lot = cls.env['stock.lot'].create({'name': 'TEST-SERIAL-01', 'product_id': cls.product.id, 'company_id': company.id})
        cls.Job = cls.env['optical.job'].with_user(cls.clinician)
        cls.Rx = cls.env['optical.prescription'].with_user(cls.clinician)
        cls.sops = {}
        for stage in ('pre_lab', 'incoming', 'dispense'):
            sop = cls.env['optical.sop'].with_user(cls.clinician).create({'name': stage, 'step': stage, 'instructions': 'Approved test checklist'})
            sop.action_approve()
            cls.sops[stage] = sop

    def _rx(self, **extra):
        vals = {'patient_id': self.patient.id, 'right_sphere': -1.25, 'left_sphere': -1.0,
                'change_reason': 'Clinical source entered', 'approval_attestation': True}
        vals.update(extra)
        rx = self.Rx.create(vals)
        rx.action_approve()
        return rx

    def _job(self, customer=True, **extra):
        vals = {'patient_id': self.patient.id, 'frame_source': 'customer' if customer else 'stock',
                'expected_date': fields.Date.today(), 'change_reason': 'Initial pair', 'laboratory_id': self.lab.id}
        if customer:
            vals.update(customer_frame_description='Customer black frame', customer_frame_condition='Checked, intact')
        else:
            vals['frame_id'] = self.lot.id
        vals.update(extra)
        return self.Job.create(vals)

    def _spec(self, job, rx=None):
        return self.env['optical.job.clinical'].with_user(self.clinician).create({
            'job_id': job.id, 'prescription_id': (rx or self._rx()).id,
            'right_lens': 'Single vision, clear', 'left_lens': 'Single vision, clear',
            'right_pd': 31, 'left_pd': 32, 'change_reason': 'Measurements recorded'})

    def _scan(self, job, event):
        return self.env['optical.scan.event'].with_user(self.clinician)._record(job, event, job.name, job.frame_code)

    def _qc(self, job, stage, result='pass'):
        self._scan(job, 'quality')
        return self.env['optical.quality'].with_user(self.clinician).create({
            'job_id': job.id, 'stage': stage, 'sop_id': self.sops[stage].id, 'result': result,
            'identity_checked': True, 'prescription_checked': True,
            'measurements_checked': True, 'condition_checked': True, 'notes': 'Verified against the approved source.'})

    def _order(self, frame=False):
        order = self.env['sale.order'].create({'partner_id': self.patient.id, 'user_id': self.clinician.id, 'order_line': [Command.create({
            'product_id': (self.product if frame else self.service).id, 'product_uom_qty': 1, 'price_unit': 100})]})
        order.action_confirm()
        return order

    def _verified(self):
        job = self._job(sale_order_id=self._order().id)
        self._spec(job)
        self._scan(job, 'reserve')
        self._qc(job, 'pre_lab')
        job.action_verify()
        return job

    def test_01_approved_prescription_is_immutable_and_versioned(self):
        rx = self._rx()
        with self.assertRaises(UserError):
            rx.write({'right_sphere': -2, 'change_reason': 'Attempt overwrite'})
        with self.assertRaises(UserError):
            rx.unlink()
        result = rx.action_new_version()
        revision = self.Rx.browse(result['res_id'])
        self.assertEqual(revision.previous_id, rx)
        self.assertEqual(revision.version, 2)
        self.assertEqual(revision.state, 'draft')
        self.assertEqual(rx.right_sphere, -1.25)
        with self.assertRaises(UserError):
            rx.action_new_version()

    def test_02_clinical_access_separate_from_management(self):
        rx = self._rx()
        for user in self.operator | self.manager | self.portal:
            with self.assertRaises(AccessError):
                rx.with_user(user).read(['right_sphere'])
            with self.assertRaises(AccessError):
                rx.with_user(user).export_data(['right_sphere'])
        with self.assertRaises(AccessError):
            self._job().with_user(self.operator).action_specifications()
        audit = self.env['optical.audit'].search([('clinical', '=', True), ('record_id', '=', rx.id), ('model_name', '=', rx._name)])
        with self.assertRaises(AccessError):
            audit.with_user(self.operator).read(['details'])

    def test_03_direct_state_and_audit_forgery_blocked(self):
        job = self._job()
        for vals in [{'state': 'dispensed'}, {'revision': 999}, {'dispensed_by': self.clinician.id}]:
            with self.assertRaises(UserError):
                job.write(vals)
        with self.assertRaises(UserError):
            self._job(state='dispensed')
        with self.assertRaises(AccessError):
            self.env['optical.audit'].with_user(self.operator).create({'action': 'Forged approval'})
        with self.assertRaises(AccessError):
            self.env['optical.scan.event'].with_user(self.operator).create({'job_id': job.id})

    def test_04_unique_serial_and_active_allocation(self):
        self.assertTrue(self.lot.optical_serial)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env['stock.lot'].create({'name': 'OTHER', 'product_id': self.product.id,
                'company_id': self.env.company.id, 'optical_serial': self.lot.optical_serial})
        self._job(customer=False)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self._job(customer=False)
        with self.assertRaises(UserError):
            self.lot.write({'optical_serial': 'RENUMBERED'})

    def test_05_wrong_and_duplicate_scans(self):
        job = self._job()
        with self.assertRaises(UserError):
            self.env['optical.scan.event'].with_user(self.operator)._record(job.with_user(self.operator), 'reserve', job.name, 'WRONG')
        first = self._scan(job, 'reserve')
        self.assertEqual(first, self._scan(job, 'reserve'))
        with self.assertRaises(UserError):
            self._scan(job, 'collect')

    def test_06_specs_invalidate_checks(self):
        job = self._job(sale_order_id=self._order().id)
        spec = self._spec(job)
        self._scan(job, 'reserve')
        self._qc(job, 'pre_lab')
        job.action_verify()
        before = job.revision
        spec.write({'right_pd': 32, 'change_reason': 'Measurement corrected'})
        self.assertEqual(job.state, 'draft')
        self.assertGreater(job.revision, before)
        with self.assertRaises(UserError):
            job.action_verify()

    def test_07_failed_latest_quality_blocks_progress(self):
        job = self._job(sale_order_id=self._order().id)
        self._spec(job)
        self._scan(job, 'reserve')
        self._qc(job, 'pre_lab')
        self._qc(job, 'pre_lab', 'fail')
        with self.assertRaises(UserError):
            job.action_verify()
        self._qc(job, 'pre_lab')
        job.action_verify()
        self.assertEqual(job.state, 'verified')

    def test_08_customer_owned_lab_flow_and_stage_specific_scans(self):
        job = self._verified()
        po = self.env['purchase.order'].create({'partner_id': self.lab.id, 'order_line': [Command.create({
            'product_id': self.service.id, 'product_qty': 1, 'price_unit': 20})]})
        job.write({'purchase_order_id': po.id, 'change_reason': 'Lab PO linked'})
        po.button_confirm()
        self._scan(job, 'dispatch')
        job.action_dispatch()
        with self.assertRaises(UserError):
            job.clinical_ids.write({'right_pd': 30, 'change_reason': 'Late change'})
        job.write({'supplier_reference': 'ACK-1', 'promised_date': fields.Date.today(), 'change_reason': 'Supplier reply'})
        job.action_acknowledge()
        self._scan(job, 'receive')
        job.action_receive()
        with self.assertRaises(UserError):
            job._require_scan('quality')  # Pre-lab scan must not count as an incoming scan.
        self._qc(job, 'incoming')
        job.action_ready()
        with self.assertRaises(UserError):
            job.action_dispense()
        self.assertFalse(job.frame_id)
        self.assertFalse(job.dispatch_picking_id)
        self.assertEqual(job.state, 'ready')

    def test_09_ticket_snapshot_and_report_access(self):
        job = self._verified()
        action = job.action_lab_ticket()
        ticket = self.env['optical.lab.ticket'].with_user(self.clinician).browse(action['data']['ids']) if action.get('data') else self.env['optical.lab.ticket'].with_user(self.clinician).search([('job_id', '=', job.id)])
        self.assertEqual(ticket.snapshot['prescription']['right_sphere'], -1.25)
        with self.assertRaises(AccessError):
            ticket.write({'snapshot': {}})
        with self.assertRaises(AccessError):
            self.env['report.popspec_optical.lab_ticket_document'].with_user(self.operator)._get_report_values(ticket.ids)
        html, _ = self.env['ir.actions.report'].with_user(self.clinician)._render_qweb_html('popspec_optical.lab_ticket_document', ticket.ids)
        self.assertIn(b'Single vision', html)
        job.clinical_ids.write({'right_lens': 'Revised specification', 'change_reason': 'Authorized correction before dispatch'})
        self.assertEqual(ticket.snapshot['right_lens'], 'Single vision, clear')

    def test_10_patient_and_company_mismatch_rejected(self):
        other = self.env['res.partner'].create({'name': 'Other patient'})
        rx = self._rx(patient_id=other.id)
        job = self._job()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._spec(job, rx)
        company = self.env['res.company'].create({'name': 'Other optical company'})
        self.clinician.write({'company_ids': [Command.link(company.id)]})
        self.env['hr.employee'].create({'name': 'Other branch clinician', 'user_id': self.clinician.id, 'company_id': company.id})
        foreign = self.Rx.with_company(company).create({'patient_id': self.patient.id,
            'change_reason': 'Other branch draft'})
        with self.assertRaises(AccessError):
            foreign.with_context(allowed_company_ids=[self.env.company.id]).read(['right_sphere'])
        with self.assertRaises(UserError):
            self.env['optical.job.clinical'].with_user(self.clinician).create({'job_id': job.id, 'company_id': company.id})

    def test_11_no_clinical_fields_on_shared_contacts(self):
        self.assertNotIn('optical_prescription_ids', self.env['res.partner']._fields)
        job = self._job()
        self._spec(job)
        with self.assertRaises(AccessError):
            job.with_user(self.operator).read(['clinical_ids'])
        with self.assertRaises(AccessError):
            job.with_user(self.portal).read(['name'])
        with self.assertRaises(AccessError):
            self.Job.with_user(self.operator).search_count([('clinical_ids.right_pd', '=', 31)])
        attachment = self.env['ir.attachment'].with_user(self.clinician).create({
            'name': 'Restricted clinical source.txt', 'res_model': 'optical.prescription',
            'res_id': job.clinical_ids.prescription_id.id, 'raw': b'Clinical source fixture'})
        with self.assertRaises(AccessError):
            attachment.with_user(self.operator).read(['raw'])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            attachment.write({'public': True})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            attachment.write({'access_token': 'attempted-share'})
        with self.assertRaises(AccessError):
            attachment.write({'res_model': 'res.partner', 'res_id': self.patient.id})

    def test_12_exception_remake_preserves_original(self):
        job = self._job()
        case = self.env['optical.case'].with_user(self.manager).create({'name': 'Warranty review', 'job_id': job.id,
            'kind': 'warranty', 'description': 'Hinge issue', 'resolution': 'Replace frame after inspection',
            'cost_treatment': 'Use new sales line and supplier claim; no automatic financial entry'})
        with self.assertRaises(UserError):
            case.action_remake()
        case.action_approve()
        case.action_remake()
        self.assertEqual(case.replacement_id.remake_of_id, job)
        self.assertNotEqual(case.replacement_id.name, job.name)
        self.assertFalse(case.replacement_id.frame_id)
        with self.assertRaises(UserError):
            case.action_remake()

    def test_13_sops_require_review_and_become_permanent(self):
        sop = self.env.ref('popspec_optical.sop_pre_lab')
        self.assertEqual(sop.state, 'draft')
        with self.assertRaises(UserError):
            self.sops['pre_lab'].write({'instructions': 'Replace approved text'})
        job = self._job()
        with self.assertRaises(UserError):
            self.env['optical.sop.signoff'].with_user(self.operator).create({'job_id': job.id, 'sop_id': sop.id, 'notes': 'Attempt'})

    def test_14_employee_attribution_required(self):
        user = new_test_user(self.env, login='unmapped_optical_user', groups='popspec_optical.group_operator')
        with self.assertRaises(UserError), self.cr.savepoint():
            self.Job.with_user(user).create({'patient_id': self.patient.id, 'frame_source': 'customer',
                'expected_date': fields.Date.today(), 'change_reason': 'No employee mapping'})

    def test_15_stock_reservation_cannot_be_replaced_by_status(self):
        job = self._job(customer=False, sale_order_id=self._order(frame=True).id)
        self._spec(job)
        self._scan(job, 'reserve')
        self._qc(job, 'pre_lab')
        with self.assertRaises(UserError):
            job.action_verify()
        self.assertEqual(job.state, 'draft')

    def test_16_native_stock_invoice_and_dispensing_flow(self):
        self.product.write({'optical_brand': 'Fixture Brand', 'optical_model': 'F100',
                            'optical_colour': 'Black', 'optical_eye_size': 52,
                            'optical_bridge_size': 18, 'optical_temple_length': 140})
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        stock = warehouse.lot_stock_id
        lab_location = self.env['stock.location'].create({'name': 'Company frames at lab', 'usage': 'internal',
            'location_id': warehouse.view_location_id.id, 'company_id': self.env.company.id})
        self.env['stock.quant']._update_available_quantity(self.product, stock, 1, lot_id=self.lot)
        order = self._order(frame=True)
        delivery = order.picking_ids
        delivery.action_assign()
        self.assertEqual(delivery.state, 'assigned')
        job = self._job(customer=False, sale_order_id=order.id, sale_line_id=order.order_line.id,
                        lab_location_id=lab_location.id, reservation_picking_id=delivery.id)
        self._spec(job)
        self._scan(job, 'reserve')
        self._qc(job, 'pre_lab')
        job.action_verify()
        self.assertEqual(job.frame_snapshot['brand'], 'Fixture Brand')
        self.product.write({'optical_brand': 'Updated catalogue brand'})
        self.assertEqual(job.frame_snapshot['brand'], 'Fixture Brand')
        delivery.move_ids.picked = True
        with self.assertRaises(UserError), self.cr.savepoint():
            delivery.with_user(self.clinician).button_validate()
        delivery.move_ids.picked = False
        delivery.do_unreserve()

        def transfer(source, destination):
            picking = self.env['stock.picking'].create({'picking_type_id': warehouse.int_type_id.id,
                'location_id': source.id, 'location_dest_id': destination.id,
                'move_ids': [Command.create({'product_id': self.product.id, 'product_uom_qty': 1,
                    'product_uom': self.product.uom_id.id, 'location_id': source.id, 'location_dest_id': destination.id})]})
            picking.action_confirm()
            picking.action_assign()
            self.assertEqual(picking.state, 'assigned')
            picking.move_ids.picked = True
            return picking

        dispatch = transfer(stock, lab_location)
        po = self.env['purchase.order'].create({'partner_id': self.lab.id, 'order_line': [Command.create({
            'product_id': self.service.id, 'product_qty': 1, 'price_unit': 20})]})
        job.write({'dispatch_picking_id': dispatch.id, 'purchase_order_id': po.id, 'change_reason': 'Native procurement and dispatch linked'})
        po.button_confirm()
        self._scan(job, 'dispatch')
        dispatch.with_user(self.clinician).button_validate()
        job.action_dispatch()
        self.assertEqual(dispatch.state, 'done')
        receipt = transfer(lab_location, stock)
        job.write({'receipt_picking_id': receipt.id, 'change_reason': 'Lab returned the pair'})
        receipt.with_user(self.clinician).button_validate()
        self._scan(job, 'receive')
        job.action_receive()
        self._qc(job, 'incoming')
        job.action_ready()
        self._qc(job, 'dispense')
        self._scan(job, 'collect')
        job.write({'delivery_picking_id': delivery.id, 'collection_confirmed': True, 'change_reason': 'Customer fitting and identity confirmed'})
        delivery.action_assign()
        delivery.move_ids.picked = True
        delivery.with_user(self.clinician).button_validate()
        self.assertEqual(delivery.state, 'done')
        with self.assertRaises(UserError):
            job.action_dispense()  # Delivery alone cannot substitute for full native invoicing/payment.
        invoice = order._create_invoices()
        invoice.action_post()
        self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'journal_id': self.company_data['default_journal_bank'].id}).action_create_payments()
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        job.action_dispense()
        self.assertEqual(job.state, 'dispensed')
        self.assertEqual(job.dispensed_by, self.clinician)
        self.assertTrue(job.dispensed_at)
        self.assertEqual(self.lot.product_qty, 0)

    def test_17_new_job_selectors_do_not_filter_on_unset_related_company(self):
        job = self._job()
        company_id = job.company_id.id
        for model in ('optical.case', 'optical.sop.signoff', 'optical.quality', 'optical.job.clinical'):
            records = self.env[model].with_user(self.clinician).with_context(allowed_company_ids=[company_id])
            arch = etree.fromstring(records.get_view(view_type='form')['arch'])
            selector = arch.xpath('//field[@name="job_id"]')[0]
            # This is the domain the web form evaluates before it has a job/company.
            domain = safe_eval(selector.get('domain'), {'context': {'allowed_company_ids': [company_id]}, 'company_id': False})
            self.assertIn(job, self.Job.search(domain))
            self.assertNotIn(('company_id', '=', False), domain)
        case = self.env['optical.case'].with_user(self.operator).create({
            'name': 'Intake concern', 'job_id': job.id, 'kind': 'complaint', 'description': 'Fixture concern'})
        self.assertEqual(case.company_id, job.company_id)
        self.assertEqual(job.action_open_cases()['context']['default_job_id'], job.id)
        self.assertEqual(job.open_case_count, 1)
        self.assertEqual(job.action_complete_sop()['context']['default_job_id'], job.id)

    def test_18_operational_prints_exclude_clinical_data_and_do_not_complete_collection(self):
        job = self._job()
        rx = self._rx(clinical_notes='PRIVATE-CLINICAL-MARKER')
        self._spec(job, rx)
        for template in ('job_sheet_document', 'collection_document', 'job_label_document'):
            html, _ = self.env['ir.actions.report'].with_user(self.operator)._render_qweb_html(
                'popspec_optical.' + template, job.ids)
            self.assertIn(job.name.encode(), html)
            self.assertNotIn(b'PRIVATE-CLINICAL-MARKER', html)
            self.assertNotIn(b'Single vision, clear', html)
            if template == 'collection_document':
                self.assertIn(b'Collection is not recorded as complete.', html)
            with self.assertRaises(AccessError):
                self.env['report.popspec_optical.' + template].with_user(self.portal)._get_report_values(job.ids)
        self.assertEqual(job.state, 'draft')
        self.assertFalse(job.collection_confirmed)
        self.assertFalse(job.dispensed_at)

    def test_19_prescription_print_requires_clinical_role_and_labels_drafts(self):
        rx = self.Rx.create({'patient_id': self.patient.id, 'change_reason': 'Print fixture',
                             'clinical_notes': 'PRIVATE-PRESCRIPTION-MARKER'})
        for user in self.operator | self.manager | self.portal:
            with self.assertRaises(AccessError):
                self.env['report.popspec_optical.prescription_document'].with_user(user)._get_report_values(rx.ids)
            with self.assertRaises(AccessError):
                rx.with_user(user).action_print_prescription()
        html, _ = self.env['ir.actions.report'].with_user(self.clinician)._render_qweb_html(
            'popspec_optical.prescription_document', rx.ids)
        self.assertIn(b'DRAFT', html)
        self.assertIn(b'PRIVATE-PRESCRIPTION-MARKER', html)
        self.assertEqual(rx.state, 'draft')
        audit = self.env['optical.audit'].search([('record_id', '=', rx.id),
            ('model_name', '=', rx._name), ('action', '=', 'Prescription printed')])
        self.assertTrue(audit)
        self.assertTrue(all(audit.mapped('clinical')))

    def test_20_prints_and_smart_actions_preserve_company_and_native_access(self):
        company = self.env['res.company'].create({'name': 'Print isolation company'})
        self.clinician.write({'company_ids': [Command.link(company.id)]})
        self.env['hr.employee'].create({'name': 'Print isolation staff', 'user_id': self.clinician.id, 'company_id': company.id})
        foreign_job = self.Job.with_company(company).create({'patient_id': self.patient.id,
            'frame_source': 'customer', 'expected_date': fields.Date.today(), 'change_reason': 'Other company'})
        renderer = self.env['report.popspec_optical.job_sheet_document'].with_user(self.clinician).with_context(allowed_company_ids=[self.env.company.id])
        with self.assertRaises(AccessError):
            renderer._get_report_values(foreign_job.ids)
        job = self._job(sale_order_id=self._order().id)
        action = job.with_user(self.operator).action_open_sale_order()
        self.assertEqual(action['res_model'], 'sale.order')
        self.assertEqual(action['res_id'], job.sale_order_id.id)
        with self.assertRaises(AccessError):
            job.with_user(self.portal).action_open_sale_order()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.product.optical_eye_size = -1
