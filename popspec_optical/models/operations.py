from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

STAGES = [('draft', 'Preparation'), ('verified', 'Verified for lab'), ('in_lab', 'At laboratory'),
          ('received', 'Received from lab'), ('ready', 'Ready for fitting'),
          ('dispensed', 'Dispensed'), ('cancelled', 'Cancelled')]
CHECKS = [('pre_lab', 'Before laboratory ordering'), ('incoming', 'Incoming inspection'), ('dispense', 'Final fitting')]


class OpticalJob(models.Model):
    _name = 'optical.job'
    _inherit = ['optical.mixin', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Optical Job — One Pair'
    _check_company_auto = True
    _order = 'id desc'
    name = fields.Char(default='New', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, readonly=True)
    patient_id = fields.Many2one('res.partner', required=True, ondelete='restrict', check_company=True)
    state = fields.Selection(STAGES, default='draft', required=True, readonly=True, copy=False, index=True)
    revision = fields.Integer(default=1, readonly=True, copy=False)
    frame_snapshot = fields.Json(readonly=True, copy=False)
    sale_order_id = fields.Many2one('sale.order', check_company=True, ondelete='restrict')
    sale_line_id = fields.Many2one('sale.order.line', string='Frame sale line', check_company=True, ondelete='restrict')
    invoice_ids = fields.Many2many(related='sale_order_id.invoice_ids', string='Native invoices', groups='account.group_account_invoice')
    frame_source = fields.Selection([('stock', 'Company stock'), ('customer', 'Customer-owned frame')], default='stock', required=True)
    frame_id = fields.Many2one('stock.lot', string='Physical frame serial', check_company=True, ondelete='restrict')
    frame_product_id = fields.Many2one(related='frame_id.product_id', string='Frame SKU')
    customer_frame_description = fields.Text()
    customer_frame_condition = fields.Text()
    frame_code = fields.Char(compute='_compute_frame_code')
    reservation_picking_id = fields.Many2one('stock.picking', string='Native reservation', check_company=True, ondelete='restrict')
    dispatch_picking_id = fields.Many2one('stock.picking', string='Transfer to lab', check_company=True, ondelete='restrict')
    receipt_picking_id = fields.Many2one('stock.picking', string='Transfer from lab', check_company=True, ondelete='restrict')
    delivery_picking_id = fields.Many2one('stock.picking', string='Customer delivery', check_company=True, ondelete='restrict')
    lab_location_id = fields.Many2one('stock.location', string='Company-owned stock at lab', check_company=True, ondelete='restrict')
    laboratory_id = fields.Many2one('res.partner', string='Laboratory supplier', check_company=True, ondelete='restrict')
    purchase_order_id = fields.Many2one('purchase.order', string='Native laboratory PO', check_company=True, ondelete='restrict')
    supplier_reference = fields.Char()
    acknowledged_at = fields.Datetime(readonly=True)
    acknowledged_by = fields.Many2one('res.users', readonly=True)
    lab_stage = fields.Selection([('waiting', 'Awaiting acknowledgment'), ('accepted', 'Accepted'),
                                 ('production', 'Lens production'), ('edging', 'Edging'), ('complete', 'Lab complete')],
                                default='waiting', required=True)
    promised_date = fields.Date()
    expected_date = fields.Date(required=True)
    overdue = fields.Boolean(compute='_compute_overdue', search='_search_overdue')
    clinical_ids = fields.One2many('optical.job.clinical', 'job_id', groups='popspec_optical.group_clinical')
    quality_ids = fields.One2many('optical.quality', 'job_id', groups='popspec_optical.group_clinical')
    scan_ids = fields.One2many('optical.scan.event', 'job_id', readonly=True)
    case_ids = fields.One2many('optical.case', 'job_id')
    sop_signoff_ids = fields.One2many('optical.sop.signoff', 'job_id')
    remake_of_id = fields.Many2one('optical.job', check_company=True, ondelete='restrict', readonly=True, copy=False)
    operational_notes = fields.Text(help='Operational information only. Clinical details belong in Restricted specifications.')
    change_reason = fields.Text(required=True)
    dispensed_at = fields.Datetime(readonly=True, copy=False)
    dispensed_by = fields.Many2one('res.users', readonly=True, copy=False)
    warranty_until = fields.Date()
    followup_date = fields.Date()
    collection_confirmed = fields.Boolean(string='Customer identity and receipt of spectacles confirmed')
    cancellation_reason = fields.Text(readonly=True)
    _name_unique = models.Constraint('UNIQUE(name)', 'The optical job number must be unique.')

    def init(self):
        # Serial allocation is exclusive even when two requests arrive together.
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS optical_job_active_frame_uniq
            ON optical_job(frame_id) WHERE frame_id IS NOT NULL AND state NOT IN ('dispensed', 'cancelled')""")

    @api.depends('name', 'frame_source', 'frame_id.optical_serial')
    def _compute_frame_code(self):
        for r in self:
            r.frame_code = r.frame_id.optical_serial if r.frame_source == 'stock' else r.name + '-F'

    @api.depends('expected_date', 'state')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for r in self:
            r.overdue = bool(r.expected_date and r.expected_date < today and r.state not in ('dispensed', 'cancelled'))

    def _search_overdue(self, operator, value):
        if operator not in ('=', '!='):
            return NotImplemented
        domain = [('expected_date', '<', fields.Date.context_today(self)), ('state', 'not in', ['dispensed', 'cancelled'])]
        return domain if (operator == '=') == bool(value) else ['!'] + ['&'] + domain

    @api.constrains('patient_id', 'frame_id', 'frame_source', 'sale_order_id', 'sale_line_id', 'purchase_order_id', 'laboratory_id', 'lab_location_id')
    def _check_links(self):
        for r in self:
            if r.sale_order_id and r.sale_order_id.partner_id.commercial_partner_id != r.patient_id.commercial_partner_id:
                raise ValidationError(_('The sales order must belong to the patient/customer account.'))
            if r.frame_source == 'customer' and r.frame_id:
                raise ValidationError(_('Do not allocate company stock to a customer-owned frame.'))
            if r.frame_id and (r.frame_id.product_id.tracking != 'serial' or not r.frame_id.optical_serial):
                raise ValidationError(_('Choose a serial-tracked optical frame with a unique optical barcode.'))
            if r.sale_line_id and (r.sale_line_id.order_id != r.sale_order_id or r.sale_line_id.product_id != r.frame_product_id):
                raise ValidationError(_('The frame sale line must match the job order and frame SKU.'))
            if r.purchase_order_id and r.purchase_order_id.partner_id != r.laboratory_id:
                raise ValidationError(_('The laboratory PO must belong to the selected laboratory.'))
            if r.lab_location_id and (r.lab_location_id.usage != 'internal' or r.lab_location_id.company_id != r.company_id):
                raise ValidationError(_('The lab stock location must be an internal location of this company.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_group('group_operator')
        protected = {'revision', 'frame_snapshot', 'dispensed_at', 'dispensed_by', 'acknowledged_at', 'acknowledged_by', 'remake_of_id', 'cancellation_reason'}
        for vals in vals_list:
            if protected & vals.keys() or vals.get('state', 'draft') != 'draft':
                raise UserError(_('Use the optical workflow actions.'))
            vals['name'] = self.env['ir.sequence'].next_by_code('optical.job')
        records = super().create(vals_list)
        records._audit('Job created')
        return records

    def _require_editable(self):
        if any(r.state not in ('draft', 'verified') for r in self):
            raise UserError(_('This pair has entered production. Record an exception and create a replacement job for material changes.'))

    def _invalidate_checks(self):
        for r in self:
            super(OpticalJob, r).write({'revision': r.revision + 1, 'state': 'draft'})
            r._audit('Specifications changed; previous checks invalidated')

    def write(self, vals):
        self._require_group('group_operator')
        self._lock()
        protected = {'state', 'name', 'revision', 'frame_snapshot', 'company_id', 'dispensed_at', 'dispensed_by',
                     'acknowledged_at', 'acknowledged_by', 'remake_of_id', 'cancellation_reason'}
        if protected & vals.keys():
            raise UserError(_('Use the optical workflow actions.'))
        # Nested clinical edits apply their own role checks and revision invalidation.
        material = {'patient_id', 'frame_id', 'frame_source', 'sale_order_id', 'sale_line_id',
                    'customer_frame_description', 'customer_frame_condition', 'laboratory_id', 'lab_location_id'}
        if material & vals.keys():
            self._require_editable()
        frozen_evidence = {'reservation_picking_id': ('draft',),
                           'dispatch_picking_id': ('draft', 'verified'),
                           'receipt_picking_id': ('verified', 'in_lab'),
                           'delivery_picking_id': ('draft', 'verified', 'in_lab', 'received', 'ready')}
        for key, stages in frozen_evidence.items():
            if key in vals and any(r.state not in stages for r in self):
                raise UserError(_('Transfer evidence already used by the workflow cannot be replaced.'))
        if any(r.state in ('dispensed', 'cancelled') for r in self):
            raise UserError(_('Completed jobs are permanent. Use an aftercare or exception case.'))
        if not vals.get('change_reason', '').strip():
            raise UserError(_('Enter a reason with each job change.'))
        # Clinical values must never be copied into the operations audit.
        safe = {k: v for k, v in vals.items() if k not in ('clinical_ids', 'quality_ids')}
        before = {r.id: r.read(list(safe), load=None)[0] for r in self}
        result = super().write(vals)
        if material & vals.keys():
            self._invalidate_checks()
        for r in self:
            r._audit('Job updated', {'before': before[r.id], 'after': safe})
        return result

    def unlink(self):
        raise UserError(_('Optical job history cannot be deleted. Cancel the job with a reason.'))

    def _set_stage(self, stage):
        self.ensure_one()
        old = self.state
        super(OpticalJob, self).write({'state': stage})
        self._audit('Workflow transition', {'from': old, 'to': stage})

    def _require_stage(self, stage):
        self.ensure_one()
        if self.state != stage:
            raise UserError(_('This action is not available in the current job stage.'))

    def _require_scan(self, event):
        self.ensure_one()
        if not self.env['optical.scan.event'].search_count([
            ('job_id', '=', self.id), ('revision', '=', self.revision), ('event', '=', event),
            ('workflow_state', '=', self.state)]):
            raise UserError(_('Scan this job and its physical frame for this step first.'))

    def _require_qc(self, stage):
        # Only status is inspected here; clinical detail never leaves its restricted model.
        qc = self.env['optical.quality'].sudo().search([
            ('job_id', '=', self.id), ('revision', '=', self.revision), ('stage', '=', stage)], order='id desc', limit=1)
        if not qc or qc.result != 'pass':
            raise UserError(_('The current revision requires a passed quality check for this step.'))

    def _stock_evidence(self, picking, purpose, done=True):
        self.ensure_one()
        if self.frame_source == 'customer':
            return
        if not picking or picking.company_id != self.company_id:
            raise UserError(_('Link the native stock transfer for this step.'))
        if done and picking.state != 'done':
            raise UserError(_('Complete the stock transfer using Odoo Inventory first.'))
        if not done and picking.state != 'assigned':
            raise UserError(_('Reserve the frame in a native Odoo transfer first.'))
        lines = picking.move_line_ids.filtered(lambda l: l.lot_id == self.frame_id and l.quantity > 0)
        if len(lines) != 1 or lines.quantity != 1 or lines.owner_id:
            raise UserError(_('The transfer must contain exactly this company-owned frame serial, quantity one.'))
        if purpose == 'dispatch' and (lines.location_dest_id != self.lab_location_id or lines.location_id.usage != 'internal'):
            raise UserError(_('Dispatch must move company stock into the configured internal lab location.'))
        if purpose == 'receipt' and (lines.location_id != self.lab_location_id or lines.location_dest_id.usage != 'internal' or lines.location_dest_id == self.lab_location_id):
            raise UserError(_('Receipt must return this serial from the lab to an internal store location.'))
        if purpose == 'delivery':
            if lines.location_dest_id.usage != 'customer' or lines.move_id.sale_line_id != self.sale_line_id:
                raise UserError(_('Collection must use the delivery generated by this frame sale line.'))
        if done and purpose in ('dispatch', 'receipt', 'delivery'):
            field = {'dispatch': 'dispatch_picking_id', 'receipt': 'receipt_picking_id', 'delivery': 'delivery_picking_id'}[purpose]
            if self.search_count([(field, '=', picking.id), ('frame_id', '=', self.frame_id), ('id', '!=', self.id),
                                  ('state', '!=', 'cancelled')]):
                raise UserError(_('This transfer/serial has already been used as evidence for another job.'))

    def action_verify(self):
        self._require_group('group_clinical')
        self._lock()
        for r in self:
            r._require_stage('draft')
            if not r.sale_order_id or r.sale_order_id.state != 'sale':
                raise UserError(_('Confirm the native quotation before laboratory ordering.'))
            if not r.laboratory_id:
                raise UserError(_('Select the laboratory supplier.'))
            if r.frame_source == 'stock':
                if not r.frame_id or not r.sale_line_id or r.sale_line_id.product_uom_qty != 1 or not r.lab_location_id:
                    raise UserError(_('Assign one serial, a frame sale line for one unit, and the internal lab location.'))
                r._stock_evidence(r.reservation_picking_id, 'reservation', done=False)
            elif not (r.customer_frame_description and r.customer_frame_condition):
                raise UserError(_('Record customer-owned frame details and its condition.'))
            if len(r.clinical_ids) != 1:
                raise UserError(_('Record the prescription, both lenses and measurements first.'))
            rx = r.clinical_ids.prescription_id
            if rx.valid_until and rx.valid_until < fields.Date.context_today(r):
                raise UserError(_('The linked prescription has expired. Obtain an approved current version.'))
            r._require_scan('reserve')
            r._require_qc('pre_lab')
            product = r.frame_product_id
            super(OpticalJob, r).write({'frame_snapshot': {
                'code': r.frame_code, 'sku': product.default_code or '', 'name': product.display_name or '',
                'attributes': product.product_template_attribute_value_ids.mapped('name') if product else [],
                'customer_frame': r.customer_frame_description or '', 'condition': r.customer_frame_condition or '',
            }})
            r._set_stage('verified')

    def action_dispatch(self):
        self._require_group('group_operator')
        self._lock()
        for r in self:
            r._require_stage('verified')
            r._require_qc('pre_lab')
            r._require_scan('dispatch')
            if not r.purchase_order_id or r.purchase_order_id.state not in ('purchase', 'done'):
                raise UserError(_('Create and confirm the laboratory order in Odoo Purchase first.'))
            r._stock_evidence(r.dispatch_picking_id, 'dispatch')
            r._set_stage('in_lab')

    def action_acknowledge(self):
        self._require_group('group_operator')
        self._lock()
        for r in self:
            r._require_stage('in_lab')
            if r.acknowledged_at or not r.supplier_reference or not r.promised_date:
                raise UserError(_('Record the supplier reference and promised date. Acknowledgment is recorded once.'))
            super(OpticalJob, r).write({'acknowledged_at': fields.Datetime.now(), 'acknowledged_by': self.env.uid,
                                       'lab_stage': 'accepted'})
            r._audit('Laboratory acknowledged', {'supplier_reference': r.supplier_reference, 'promised_date': str(r.promised_date)})

    def action_receive(self):
        self._require_group('group_operator')
        self._lock()
        for r in self:
            r._require_stage('in_lab')
            r._require_scan('receive')
            r._stock_evidence(r.receipt_picking_id, 'receipt')
            if r.frame_source == 'stock' and r.receipt_picking_id.date_done < r.dispatch_picking_id.date_done:
                raise UserError(_('The lab receipt must follow the dispatch.'))
            r._set_stage('received')

    def action_ready(self):
        self._require_group('group_clinical')
        self._lock()
        for r in self:
            r._require_stage('received')
            r._require_qc('incoming')
            r._set_stage('ready')

    def action_dispense(self):
        self._require_group('group_clinical')
        self._lock()
        for r in self:
            r._require_stage('ready')
            r._require_qc('dispense')
            r._require_scan('collect')
            if not r.collection_confirmed:
                raise UserError(_('Confirm customer identity and receipt of the spectacles.'))
            r._stock_evidence(r.delivery_picking_id, 'delivery')
            # Finance remains native. Require finance access rather than leaking balances with sudo.
            self.env['account.move'].check_access('read')
            invoices = r.sale_order_id.invoice_ids.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted')
            if not invoices or any(m.payment_state not in ('paid', 'in_payment') for m in invoices):
                raise UserError(_('Record payment against the posted customer invoices before collection. Credit-policy exceptions are not enabled in this release.'))
            super(OpticalJob, r).write({'dispensed_at': fields.Datetime.now(), 'dispensed_by': self.env.uid})
            r._set_stage('dispensed')

    def action_cancel(self):
        self._require_group('group_manager')
        self._lock()
        for r in self:
            if r.state in ('dispensed', 'cancelled') or not r.change_reason.strip():
                raise UserError(_('Only an open job can be cancelled, with a documented reason.'))
            # Never cancel native orders or reverse stock implicitly.
            transfers = r.reservation_picking_id | r.dispatch_picking_id | r.receipt_picking_id | r.delivery_picking_id
            if transfers.filtered(lambda p: p.state not in ('done', 'cancel')):
                raise UserError(_('Resolve or cancel outstanding native transfers before cancelling this job.'))
            if r.state == 'in_lab' and r.frame_source == 'stock':
                r._stock_evidence(r.receipt_picking_id, 'receipt')
            super(OpticalJob, r).write({'cancellation_reason': r.change_reason})
            r._set_stage('cancelled')

    def action_scan(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'optical.scan.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_job_id': self.id}}

    def action_specifications(self):
        self.ensure_one()
        self._require_group('group_clinical')
        return {'type': 'ir.actions.act_window', 'res_model': 'optical.job.clinical', 'view_mode': 'form',
                'res_id': self.clinical_ids.id or False, 'context': {'default_job_id': self.id}}

    def action_quality_check(self):
        self.ensure_one()
        self._require_group('group_clinical')
        stage = {'draft': 'pre_lab', 'received': 'incoming', 'ready': 'dispense'}.get(self.state)
        if not stage:
            raise UserError(_('Quality checks are recorded in preparation, at receipt and at final fitting.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'optical.quality', 'view_mode': 'form',
                'context': {'default_job_id': self.id, 'default_stage': stage}}

    def action_lab_ticket(self):
        self.ensure_one()
        self._require_group('group_clinical')
        ticket = self.env['optical.lab.ticket']._issue(self)
        return self.env.ref('popspec_optical.report_lab_ticket').report_action(ticket)


class ScanEvent(models.Model):
    _name = 'optical.scan.event'
    _description = 'Optical Scan Evidence'
    _order = 'id desc'
    job_id = fields.Many2one('optical.job', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='job_id.company_id', store=True)
    revision = fields.Integer(required=True)
    workflow_state = fields.Selection(STAGES, required=True)
    event = fields.Selection([('reserve', 'Frame reservation'), ('dispatch', 'Lab dispatch'),
                              ('receive', 'Lab receipt'), ('quality', 'Quality control'), ('collect', 'Customer collection'),
                              ('return', 'Return inspection')], required=True)
    code = fields.Char(required=True)
    actor_id = fields.Many2one('res.users', required=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    occurred_at = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.model
    def _record(self, job, event, job_code, frame_code):
        job._require_group('group_operator')
        job._lock()
        if job_code.strip() != job.name or frame_code.strip() != job.frame_code or not job.frame_code:
            raise UserError(_('Wrong job or physical frame. Scan the job label and the unique frame label.'))
        allowed = {'reserve': ('draft',), 'dispatch': ('verified',), 'receive': ('in_lab',),
                   'quality': ('draft', 'received', 'ready'), 'collect': ('ready',), 'return': ('dispensed',)}
        if event not in allowed or job.state not in allowed[event]:
            raise UserError(_('This scan does not match the current workflow step.'))
        existing = self.search([('job_id', '=', job.id), ('revision', '=', job.revision), ('event', '=', event),
                                ('workflow_state', '=', job.state)])
        if existing:
            return existing[:1]
        result = super(ScanEvent, self).create({'job_id': job.id, 'revision': job.revision, 'event': event, 'workflow_state': job.state,
             'code': frame_code, 'actor_id': self.env.uid, 'employee_id': job._employee(job.company_id).id})
        job._audit('Barcode verified', {'event': event, 'code': frame_code, 'revision': job.revision})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Use the scan action to record evidence.'))

    def write(self, vals):
        raise AccessError(_('Scan evidence cannot be edited.'))

    def unlink(self):
        raise AccessError(_('Scan evidence cannot be deleted.'))


class QualityCheck(models.Model):
    _name = 'optical.quality'
    _inherit = 'optical.mixin'
    _description = 'Restricted Optical Quality Check'
    _order = 'id desc'
    _check_company_auto = True
    job_id = fields.Many2one('optical.job', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one(related='job_id.company_id', store=True)
    revision = fields.Integer(readonly=True)
    stage = fields.Selection(CHECKS, required=True)
    result = fields.Selection([('pass', 'Pass'), ('fail', 'Fail / hold')], required=True, default='fail')
    identity_checked = fields.Boolean(string='Patient, job and frame identity verified')
    prescription_checked = fields.Boolean(string='Prescription, right/left lenses and instructions verified')
    measurements_checked = fields.Boolean(string='Measurements / lens verification / fitting checked for this stage')
    condition_checked = fields.Boolean(string='Frame and lens condition / safety checked')
    notes = fields.Text(required=True)
    sop_id = fields.Many2one('optical.sop', required=True, ondelete='restrict', check_company=True)
    checked_by = fields.Many2one('res.users', readonly=True)
    employee_id = fields.Many2one('hr.employee', readonly=True)
    checked_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self._require_group('group_clinical')
        for vals in vals_list:
            if 'company_id' in vals:
                raise UserError(_('The company is taken from the optical job.'))
            job = self.env['optical.job'].browse(vals['job_id'])
            job._lock()
            stage = vals.get('stage')
            required_state = {'pre_lab': 'draft', 'incoming': 'received', 'dispense': 'ready'}
            if stage not in required_state or job.state != required_state[stage]:
                raise UserError(_('This check does not match the current workflow stage.'))
            job._require_scan('quality')
            sop = self.env['optical.sop'].browse(vals.get('sop_id'))
            if sop.state != 'active' or sop.step != stage:
                raise UserError(_('Select an approved SOP for this quality-control stage.'))
            if vals.get('result') == 'pass' and not all(vals.get(k) for k in (
                    'identity_checked', 'prescription_checked', 'measurements_checked', 'condition_checked')):
                raise UserError(_('All required checks must be documented before passing.'))
            vals.update(revision=job.revision, checked_by=self.env.uid,
                        employee_id=self._employee(job.company_id).id, checked_at=fields.Datetime.now())
        records = super().create(vals_list)
        records._audit('Quality decision recorded', clinical=True)
        return records

    def write(self, vals):
        raise AccessError(_('Quality decisions are permanent. Record a new check after correction.'))

    def unlink(self):
        raise AccessError(_('Quality decisions cannot be deleted.'))


SOP_STEPS = CHECKS + [(k, v) for k, v in [
    ('registration', 'Customer registration'), ('prescription', 'Clinical prescription'),
    ('frame', 'Frame selection'), ('measurements', 'Measurements'), ('quotation', 'Quotation approval'),
    ('job', 'Job creation'), ('procurement', 'Supplier procurement'), ('dispatch', 'Lab dispatch'),
    ('receipt', 'Goods receipt'), ('remake', 'Remakes'), ('warranty', 'Warranties'),
    ('inventory', 'Inventory management'), ('day_end', 'End-of-day reconciliation')]]


class SOP(models.Model):
    _name = 'optical.sop'
    _inherit = 'optical.mixin'
    _description = 'Optical SOP Version'
    _check_company_auto = True
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    step = fields.Selection(SOP_STEPS, required=True)
    version = fields.Char(required=True, default='1')
    instructions = fields.Text(required=True)
    state = fields.Selection([('draft', 'Awaiting client review'), ('active', 'Approved')], default='draft', readonly=True)
    approved_by = fields.Many2one('res.users', readonly=True)
    approved_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft' or set(vals) & {'approved_by', 'approved_at'}:
                raise UserError(_('Use SOP approval.'))
        return super().create(vals_list)

    def write(self, vals):
        self._lock()
        if any(r.state != 'draft' for r in self) or set(vals) & {'state', 'approved_by', 'approved_at'}:
            raise UserError(_('Approved SOPs are permanent. Create a new version.'))
        return super().write(vals)

    def action_approve(self):
        self._require_group('group_manager')
        self._lock()
        for r in self:
            if r.state != 'draft':
                raise UserError(_('This SOP is already approved.'))
            super(SOP, r).write({'state': 'active', 'approved_by': self.env.uid, 'approved_at': fields.Datetime.now()})
            r._audit('SOP approved')

    def unlink(self):
        raise UserError(_('SOP history cannot be deleted.'))


class SOPSignoff(models.Model):
    _name = 'optical.sop.signoff'
    _inherit = 'optical.mixin'
    _description = 'Optical SOP Completion'
    _check_company_auto = True
    job_id = fields.Many2one('optical.job', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one(related='job_id.company_id', store=True)
    sop_id = fields.Many2one('optical.sop', required=True, check_company=True, ondelete='restrict')
    notes = fields.Text(required=True, help='Operational evidence only; clinical notes belong in the restricted records.')
    actor_id = fields.Many2one('res.users', readonly=True)
    employee_id = fields.Many2one('hr.employee', readonly=True)
    completed_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self._require_group('group_operator')
        for vals in vals_list:
            if 'company_id' in vals:
                raise UserError(_('The company is taken from the optical job.'))
            job = self.env['optical.job'].browse(vals['job_id'])
            job.check_access('read')
            if self.env['optical.sop'].browse(vals['sop_id']).state != 'active':
                raise UserError(_('Approve the SOP before signing it off.'))
            vals.update(actor_id=self.env.uid, employee_id=self._employee(job.company_id).id,
                        completed_at=fields.Datetime.now())
        records = super().create(vals_list)
        records._audit('SOP completed')
        return records

    def write(self, vals):
        raise AccessError(_('SOP completion evidence is permanent.'))

    def unlink(self):
        raise AccessError(_('SOP completion evidence is permanent.'))


class OpticalCase(models.Model):
    _name = 'optical.case'
    _inherit = ['optical.mixin', 'mail.activity.mixin']
    _description = 'Optical Exception and Aftercare Case'
    _check_company_auto = True
    name = fields.Char(required=True)
    job_id = fields.Many2one('optical.job', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one(related='job_id.company_id', store=True)
    kind = fields.Selection([(k, v) for k, v in [
        ('rx_change', 'Prescription change'), ('supplier', 'Supplier error'), ('damage', 'Damaged frame'),
        ('warranty', 'Warranty'), ('uncollected', 'Uncollected job'), ('complaint', 'Customer complaint'),
        ('remake', 'Remake'), ('return', 'Return / refund')]], required=True)
    description = fields.Text(required=True, help='No clinical detail here; use the restricted prescription/specification records.')
    responsibility = fields.Selection([('review', 'Under review'), ('supplier', 'Supplier'), ('store', 'Store'), ('customer', 'Customer')], default='review')
    cost_treatment = fields.Text(help='Reference the native supplier credit, customer credit, purchase or sales order. No separate optical ledger.')
    return_picking_id = fields.Many2one('stock.picking', check_company=True)
    credit_note_id = fields.Many2one('account.move', check_company=True, groups='account.group_account_invoice')
    resolution = fields.Text()
    state = fields.Selection([('open', 'Open'), ('approved', 'Resolution approved'), ('closed', 'Closed')], default='open', readonly=True)
    approved_by = fields.Many2one('res.users', readonly=True)
    approved_at = fields.Datetime(readonly=True)
    replacement_id = fields.Many2one('optical.job', readonly=True, check_company=True, ondelete='restrict')
    due_date = fields.Date()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'open') != 'open' or set(vals) & {'approved_by', 'approved_at', 'replacement_id', 'company_id'}:
                raise UserError(_('Use the exception approval actions.'))
        records = super().create(vals_list)
        records._audit('Exception opened')
        return records

    def write(self, vals):
        self._lock()
        if set(vals) & {'state', 'approved_by', 'approved_at', 'replacement_id', 'job_id', 'company_id'} or any(r.state != 'open' for r in self):
            raise UserError(_('Approved case decisions are permanent. Open a follow-up case for changes.'))
        result = super().write(vals)
        self._audit('Exception updated', {'values': vals})
        return result

    def action_approve(self):
        self._require_group('group_manager')
        self._lock()
        for r in self:
            if r.state != 'open' or not r.resolution or not r.cost_treatment:
                raise UserError(_('Document the resolution and native financial/stock treatment before approval.'))
            super(OpticalCase, r).write({'state': 'approved', 'approved_by': self.env.uid, 'approved_at': fields.Datetime.now()})
            r._audit('Exception resolution approved')

    def action_remake(self):
        self.ensure_one()
        self._require_group('group_manager')
        self._lock()
        if self.state != 'approved' or self.replacement_id:
            raise UserError(_('Approve the exception first. Only one replacement may be created per case.'))
        job = self.env['optical.job'].create({'patient_id': self.job_id.patient_id.id,
            'frame_source': self.job_id.frame_source, 'expected_date': self.due_date or fields.Date.context_today(self),
            'change_reason': self.resolution, 'operational_notes': 'Replacement authorised by case %s' % self.name})
        super(OpticalJob, job).write({'remake_of_id': self.job_id.id})
        super(OpticalCase, self).write({'replacement_id': job.id})
        self._audit('Replacement created', {'replacement_id': job.id, 'original_job_id': self.job_id.id})
        return {'type': 'ir.actions.act_window', 'res_model': 'optical.job', 'res_id': job.id, 'view_mode': 'form'}

    def action_close(self):
        self._require_group('group_manager')
        self._lock()
        for r in self:
            if r.state != 'approved':
                raise UserError(_('Approve the resolution first.'))
            super(OpticalCase, r).write({'state': 'closed'})
            r._audit('Exception closed')

    def unlink(self):
        raise UserError(_('Exception history cannot be deleted.'))
