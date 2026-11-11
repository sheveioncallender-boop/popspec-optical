from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class Prescription(models.Model):
    _name = 'optical.prescription'
    _inherit = 'optical.mixin'
    _description = 'Restricted Optical Prescription Version'
    _check_company_auto = True
    _order = 'id desc'
    name = fields.Char(default='New', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, readonly=True)
    patient_id = fields.Many2one('res.partner', required=True, check_company=True, ondelete='restrict')
    previous_id = fields.Many2one('optical.prescription', readonly=True, copy=False, check_company=True, ondelete='restrict')
    version = fields.Integer(default=1, readonly=True, copy=False)
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved')], default='draft', readonly=True)
    examination_date = fields.Date(required=True, default=fields.Date.context_today)
    valid_until = fields.Date()
    right_sphere = fields.Float(digits=(6, 2))
    right_cylinder = fields.Float(digits=(6, 2))
    right_axis = fields.Integer()
    right_add = fields.Float(digits=(6, 2))
    right_prism = fields.Char()
    left_sphere = fields.Float(digits=(6, 2))
    left_cylinder = fields.Float(digits=(6, 2))
    left_axis = fields.Integer()
    left_add = fields.Float(digits=(6, 2))
    left_prism = fields.Char()
    clinical_notes = fields.Text()
    approval_attestation = fields.Boolean(string='I have checked this prescription against the clinical source')
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    change_reason = fields.Text(required=True)

    @api.constrains('right_axis', 'left_axis', 'examination_date', 'valid_until')
    def _check_values(self):
        for record in self:
            if not (0 <= record.right_axis <= 180 and 0 <= record.left_axis <= 180):
                raise ValidationError(_('Axes must be between 0 and 180 degrees.'))
            if record.valid_until and record.valid_until < record.examination_date:
                raise ValidationError(_('Validity cannot end before the examination date.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_group('group_clinical')
        for vals in vals_list:
            if set(vals) & {'approved_by', 'approved_at', 'previous_id', 'version'} or vals.get('state', 'draft') != 'draft':
                raise UserError(_('Use prescription approval or revision actions.'))
            vals['name'] = self.env['ir.sequence'].next_by_code('optical.prescription')
        records = super().create(vals_list)
        records._audit('Prescription created', clinical=True)
        return records

    def write(self, vals):
        self._require_group('group_clinical')
        self._lock()
        if any(r.state != 'draft' for r in self):
            raise UserError(_('Approved prescriptions are permanent. Create a new version.'))
        if set(vals) & {'state', 'name', 'version', 'previous_id', 'approved_by', 'approved_at', 'company_id'}:
            raise UserError(_('Use the prescription workflow actions.'))
        if not vals.get('change_reason', '').strip():
            raise UserError(_('Enter a change reason with the prescription edit.'))
        before = {r.id: r.read(list(vals), load=None)[0] for r in self}
        result = super().write(vals)
        for r in self:
            r._audit('Prescription edited', {'before': before[r.id], 'after': vals}, clinical=True)
        return result

    def unlink(self):
        raise UserError(_('Prescription history is permanent. Keep unused drafts for audit.'))

    def action_approve(self):
        self._require_group('group_clinical')
        self._lock()
        for record in self:
            if record.state != 'draft' or not record.approval_attestation:
                raise UserError(_('Verify the clinical source before approval.'))
            super(Prescription, record).write({'state': 'approved', 'approved_by': self.env.uid,
                                              'approved_at': fields.Datetime.now()})
            record._audit('Prescription approved', clinical=True)

    def action_new_version(self):
        self.ensure_one()
        self._require_group('group_clinical')
        self._lock()
        if self.state != 'approved':
            raise UserError(_('Approve the current version before creating a revision.'))
        if self.search_count([('previous_id', '=', self.id)]):
            raise UserError(_('A revision already exists. Continue from that version.'))
        values = self.copy_data()[0]
        for key in ['previous_id', 'version', 'approved_by', 'approved_at']:
            values.pop(key, None)
        values.update(state='draft', approval_attestation=False,
                      change_reason='New version of %s; record the clinical reason before approval.' % self.name)
        new = self.create(values)
        super(Prescription, new).write({'previous_id': self.id, 'version': self.version + 1})
        new._audit('Revision linked', {'previous_id': self.id}, clinical=True)
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': new.id, 'view_mode': 'form'}


class JobClinical(models.Model):
    _name = 'optical.job.clinical'
    _inherit = 'optical.mixin'
    _description = 'Restricted Lens Specifications and Measurements'
    _check_company_auto = True
    _rec_name = 'job_id'
    job_id = fields.Many2one('optical.job', required=True, ondelete='restrict', check_company=True)
    company_id = fields.Many2one(related='job_id.company_id', store=True)
    prescription_id = fields.Many2one('optical.prescription', required=True, check_company=True, ondelete='restrict')
    right_lens = fields.Text(required=True)
    left_lens = fields.Text(required=True)
    right_pd = fields.Float(string='Right monocular PD (mm)', required=True)
    left_pd = fields.Float(string='Left monocular PD (mm)', required=True)
    right_height = fields.Float(string='Right fitting height (mm)')
    left_height = fields.Float(string='Left fitting height (mm)')
    lab_instructions = fields.Text()
    change_reason = fields.Text(required=True)
    _job_unique = models.Constraint('UNIQUE(job_id)', 'Each pair has one current specification record.')

    @api.constrains('prescription_id', 'job_id', 'right_pd', 'left_pd', 'right_height', 'left_height')
    def _check_clinical(self):
        for r in self:
            if r.prescription_id.state != 'approved' or r.prescription_id.patient_id != r.job_id.patient_id:
                raise ValidationError(_('Choose an approved prescription belonging to this patient.'))
            if r.right_pd <= 0 or r.left_pd <= 0 or r.right_height < 0 or r.left_height < 0:
                raise ValidationError(_('Record positive monocular PDs and nonnegative fitting heights.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_group('group_clinical')
        if any('company_id' in v for v in vals_list):
            raise UserError(_('The company is taken from the optical job.'))
        jobs = self.env['optical.job'].browse([v['job_id'] for v in vals_list])
        jobs._lock()
        jobs._require_editable()
        records = super().create(vals_list)
        jobs._invalidate_checks()
        records._audit('Lens specifications recorded', clinical=True)
        return records

    def write(self, vals):
        self._require_group('group_clinical')
        if set(vals) & {'job_id', 'company_id'}:
            raise UserError(_('A specification record cannot be moved to another job.'))
        self.job_id._lock()
        self.job_id._require_editable()
        if not vals.get('change_reason', '').strip():
            raise UserError(_('Record the reason for changing lens specifications.'))
        before = {r.id: r.read(list(vals), load=None)[0] for r in self}
        result = super().write(vals)
        self.job_id._invalidate_checks()
        for r in self:
            r._audit('Lens specifications edited', {'before': before[r.id], 'after': vals}, clinical=True)
        return result

    def unlink(self):
        raise UserError(_('Clinical job history cannot be deleted.'))


class LabTicket(models.Model):
    _name = 'optical.lab.ticket'
    _inherit = 'optical.mixin'
    _description = 'Immutable Restricted Laboratory Ticket'
    _check_company_auto = True
    name = fields.Char(required=True, readonly=True)
    job_id = fields.Many2one('optical.job', required=True, check_company=True, ondelete='restrict', readonly=True)
    company_id = fields.Many2one(related='job_id.company_id', store=True)
    revision = fields.Integer(required=True, readonly=True)
    snapshot = fields.Json(required=True, readonly=True)
    issued_by = fields.Many2one('res.users', readonly=True)
    issued_at = fields.Datetime(readonly=True)
    _job_revision_unique = models.Constraint('UNIQUE(job_id, revision)', 'A job revision has one permanent laboratory ticket.')

    @api.model
    def _issue(self, job):
        job._require_group('group_clinical')
        job._lock()
        job._require_qc('pre_lab')
        if job.state in ('draft', 'cancelled'):
            raise UserError(_('Verify this job before producing a laboratory ticket.'))
        existing = self.search([('job_id', '=', job.id), ('revision', '=', job.revision)], limit=1)
        if existing:
            return existing
        spec = job.clinical_ids
        rx = spec.prescription_id
        rx_values = rx.read(['name', 'version', 'right_sphere', 'right_cylinder', 'right_axis', 'right_add', 'right_prism',
                             'left_sphere', 'left_cylinder', 'left_axis', 'left_add', 'left_prism'], load=None)[0]
        snapshot = {'prescription': rx_values, 'frame': job.frame_snapshot,
                    'right_lens': spec.right_lens, 'left_lens': spec.left_lens,
                    'right_pd': spec.right_pd, 'left_pd': spec.left_pd,
                    'right_height': spec.right_height, 'left_height': spec.left_height,
                    'lab_instructions': spec.lab_instructions or '', 'laboratory': job.laboratory_id.display_name,
                    'due_date': str(job.expected_date)}
        ticket = super(LabTicket, self).create({'name': '%s / R%s' % (job.name, job.revision),
            'job_id': job.id, 'revision': job.revision, 'snapshot': snapshot,
            'issued_by': self.env.uid, 'issued_at': fields.Datetime.now()})
        ticket._audit('Laboratory ticket issued', clinical=True)
        return ticket

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Use the restricted laboratory ticket action on the job.'))

    def write(self, vals):
        raise AccessError(_('Issued laboratory tickets are permanent.'))

    def unlink(self):
        raise AccessError(_('Issued laboratory tickets are permanent.'))
