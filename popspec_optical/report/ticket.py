from odoo import api, models, _
from odoo.exceptions import AccessError


class LabTicketReport(models.AbstractModel):
    _name = 'report.popspec_optical.lab_ticket_document'
    _description = 'Restricted Laboratory Ticket Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not self.env.user.has_group('popspec_optical.group_clinical'):
            raise AccessError(_('Clinical authorization is required to print laboratory tickets.'))
        docs = self.env['optical.lab.ticket'].browse(docids)
        docs.check_access('read')
        docs._audit('Laboratory ticket rendered', clinical=True)
        return {'doc_ids': docs.ids, 'doc_model': docs._name, 'docs': docs}
