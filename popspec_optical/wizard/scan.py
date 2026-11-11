from odoo import fields, models


class OpticalScan(models.TransientModel):
    _name = 'optical.scan.wizard'
    _description = 'Scan Optical Job and Physical Frame'
    job_id = fields.Many2one('optical.job', required=True, readonly=True)
    event = fields.Selection([
        ('reserve', 'Frame reservation'), ('dispatch', 'Lab dispatch'), ('receive', 'Lab receipt'),
        ('quality', 'Quality control'), ('collect', 'Customer collection'), ('return', 'Return inspection')], required=True)
    job_code = fields.Char(required=True, string='Scan job label')
    frame_code = fields.Char(required=True, string='Scan physical frame label')

    def action_confirm(self):
        self.ensure_one()
        self.env['optical.scan.event']._record(self.job_id, self.event, self.job_code, self.frame_code)
        return {'type': 'ir.actions.act_window_close'}
