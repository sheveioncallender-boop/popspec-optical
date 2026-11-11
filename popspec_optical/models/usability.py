from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class OpticalJobUsability(models.Model):
    _inherit = 'optical.job'

    state = fields.Selection(group_expand=True)
    next_step = fields.Char(compute='_compute_next_step')
    open_case_count = fields.Integer(compute='_compute_open_case_count')

    @api.depends('state')
    def _compute_next_step(self):
        instructions = {
            'draft': _('Prepare the quotation, frame and restricted lens details. Reserve the frame in Inventory, scan both labels and complete pre-lab QC before verification.'),
            'verified': _('Print the restricted lab ticket. Confirm the linked lab purchase order, scan dispatch and complete the native transfer to the laboratory.'),
            'in_lab': _('Record the supplier acknowledgment and promised date. On return, scan receipt and complete the native transfer from the laboratory.'),
            'received': _('Scan for quality control and record the incoming inspection. Resolve any failed check before marking the pair ready for fitting.'),
            'ready': _('Complete final fitting QC, scan collection and confirm customer receipt. Complete native delivery and invoice/payment before dispensing.'),
            'dispensed': _('This dispensing record is complete. Use an aftercare case for complaints, warranty requests, returns or a replacement.'),
            'cancelled': _('This job is cancelled. Review its native stock, purchasing and accounting documents separately.'),
        }
        for job in self:
            job.next_step = instructions[job.state]

    @api.depends('case_ids.state')
    def _compute_open_case_count(self):
        for job in self:
            job.open_case_count = len(job.case_ids.filtered(lambda case: case.state != 'closed'))

    def _open_native_document(self, record, title):
        self.ensure_one()
        self._require_group('group_operator')
        self.check_access('read')
        if not record:
            raise UserError(_('Link the native document on the job first.'))
        record.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': title, 'res_model': record._name,
                'res_id': record.id, 'view_mode': 'form'}

    def action_open_sale_order(self):
        return self._open_native_document(self.sale_order_id, _('Quotation / sales order'))

    def action_open_purchase_order(self):
        return self._open_native_document(self.purchase_order_id, _('Laboratory purchase order'))

    def action_open_cases(self):
        self.ensure_one()
        self._require_group('group_operator')
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': _('Exceptions and aftercare'),
                'res_model': 'optical.case', 'view_mode': 'list,form',
                'domain': [('job_id', '=', self.id)], 'context': {'default_job_id': self.id}}

    def action_complete_sop(self):
        self.ensure_one()
        self._require_group('group_operator')
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': _('Record SOP completion'),
                'res_model': 'optical.sop.signoff', 'view_mode': 'form',
                'context': {'default_job_id': self.id}}

    def _print_operational_report(self, xmlid):
        self._require_group('group_operator')
        self.check_access('read')
        return self.env.ref('popspec_optical.' + xmlid).report_action(self)

    def action_print_job_sheet(self):
        return self._print_operational_report('report_job_sheet')

    def action_print_labels(self):
        if any(not job.frame_code for job in self):
            raise UserError(_('Select the physical frame before printing its label.'))
        return self._print_operational_report('report_job_label')

    def action_print_collection(self):
        return self._print_operational_report('report_collection')


class ClinicalSpecificationUsability(models.Model):
    _inherit = 'optical.job.clinical'

    patient_id = fields.Many2one(related='job_id.patient_id', readonly=True)


class PrescriptionUsability(models.Model):
    _inherit = 'optical.prescription'

    def action_print_prescription(self):
        self._require_group('group_clinical')
        self.check_access('read')
        return self.env.ref('popspec_optical.report_prescription').report_action(self)


class ProductOpticalIdentity(models.Model):
    _inherit = 'product.template'

    optical_brand = fields.Char(string='Frame brand')
    optical_model = fields.Char(string='Frame model')
    optical_colour = fields.Char(string='Frame colour', help='Use native product variants for saleable colour options. This is a catalogue reference.')
    optical_eye_size = fields.Float(string='Lens width (mm)', digits=(5, 1))
    optical_bridge_size = fields.Float(string='Bridge width (mm)', digits=(5, 1))
    optical_temple_length = fields.Float(string='Temple length (mm)', digits=(5, 1))

    @api.constrains('optical_eye_size', 'optical_bridge_size', 'optical_temple_length')
    def _check_optical_dimensions(self):
        for product in self:
            if min(product.optical_eye_size, product.optical_bridge_size, product.optical_temple_length) < 0:
                raise ValidationError(_('Frame dimensions cannot be negative. Leave unknown dimensions at zero until verified with the supplier.'))


def optical_job_action(record, patient, order=None):
    record.ensure_one()
    if not record.env.user.has_group('popspec_optical.group_operator'):
        raise AccessError(_('Optical access is required.'))
    record.check_access('read')
    context = dict(record.env.context, default_patient_id=patient.id)
    domain = [('patient_id', '=', patient.id)]
    if order:
        domain = [('sale_order_id', '=', order.id)]
        context.update(default_sale_order_id=order.id, default_company_id=order.company_id.id)
    return {'type': 'ir.actions.act_window', 'name': _('Optical jobs'), 'res_model': 'optical.job',
            'view_mode': 'list,kanban,form', 'domain': domain, 'context': context}


class PartnerOpticalNavigation(models.Model):
    _inherit = 'res.partner'

    def action_view_optical_jobs(self):
        return optical_job_action(self, self)


class SaleOpticalNavigation(models.Model):
    _inherit = 'sale.order'

    def action_view_optical_jobs(self):
        return optical_job_action(self, self.partner_id, self)
