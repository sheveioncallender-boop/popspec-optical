from odoo import api, models, _
from odoo.exceptions import AccessError


def report_records(env, model, docids, group, action, clinical=False):
    if not env.user.has_group('popspec_optical.' + group):
        raise AccessError(_('Your optical role does not allow this document to be printed.'))
    docs = env[model].browse(docids)
    docs.check_access('read')
    docs._audit(action, clinical=clinical)
    return {'doc_ids': docs.ids, 'doc_model': model, 'docs': docs}


class JobSheetReport(models.AbstractModel):
    _name = 'report.popspec_optical.job_sheet_document'
    _description = 'Optical Operational Job Sheet'

    @api.model
    def _get_report_values(self, docids, data=None):
        return report_records(self.env, 'optical.job', docids, 'group_operator', 'Operational job sheet printed')


class JobLabelReport(models.AbstractModel):
    _name = 'report.popspec_optical.job_label_document'
    _description = 'Optical Job and Frame Labels'

    @api.model
    def _get_report_values(self, docids, data=None):
        return report_records(self.env, 'optical.job', docids, 'group_operator', 'Job and frame labels printed')


class CollectionReport(models.AbstractModel):
    _name = 'report.popspec_optical.collection_document'
    _description = 'Optical Collection Reference'

    @api.model
    def _get_report_values(self, docids, data=None):
        return report_records(self.env, 'optical.job', docids, 'group_operator', 'Collection reference printed')


class PrescriptionReport(models.AbstractModel):
    _name = 'report.popspec_optical.prescription_document'
    _description = 'Restricted Optical Prescription Print'

    @api.model
    def _get_report_values(self, docids, data=None):
        return report_records(self.env, 'optical.prescription', docids, 'group_clinical', 'Prescription printed', clinical=True)
