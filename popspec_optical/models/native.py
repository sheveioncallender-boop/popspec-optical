from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    optical_frame = fields.Boolean(string='Optical frame', help='Physical units must use serial tracking and a unique optical barcode.')

    @api.constrains('optical_frame', 'tracking', 'is_storable')
    def _check_optical_tracking(self):
        for r in self:
            if r.optical_frame and (r.tracking != 'serial' or not r.is_storable):
                raise ValidationError(_('Optical frames must be storable products tracked by unique serial number.'))


class StockLot(models.Model):
    _inherit = 'stock.lot'
    optical_serial = fields.Char(string='Optical scan code', copy=False, index=True)
    optical_job_ids = fields.One2many('optical.job', 'frame_id', groups='popspec_optical.group_operator')
    _optical_serial_unique = models.Constraint('UNIQUE(optical_serial)', 'Optical scan codes must be unique across all frame SKUs and companies.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product = self.env['product.product'].browse(vals.get('product_id'))
            if product.optical_frame and not vals.get('optical_serial'):
                vals['optical_serial'] = self.env['ir.sequence'].next_by_code('optical.frame')
        return super().create(vals_list)

    @api.constrains('optical_serial', 'product_id')
    def _check_optical_serial(self):
        for r in self:
            if r.product_id.optical_frame and not r.optical_serial:
                raise ValidationError(_('Assign a unique optical scan code to this physical frame.'))
            if r.optical_serial and (r.product_id.tracking != 'serial' or not r.product_id.is_storable):
                raise ValidationError(_('Only storable products tracked by serial number can have an optical scan code.'))
            if r.optical_serial and r.optical_serial != r.optical_serial.strip():
                raise ValidationError(_('Optical scan codes cannot start or end with spaces.'))

    def write(self, vals):
        if set(vals) & {'name', 'optical_serial', 'product_id', 'company_id'}:
            if self.env['optical.job'].sudo().search_count([('frame_id', 'in', self.ids)]):
                raise UserError(_('A frame used in optical job history cannot be reassigned or renumbered.'))
        return super().write(vals)

    def action_assign_optical_codes(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Inventory administration access is required.'))
        for r in self:
            if not r.optical_serial:
                r.optical_serial = self.env['ir.sequence'].next_by_code('optical.frame')


class ResPartner(models.Model):
    _inherit = 'res.partner'
    optical_job_ids = fields.One2many('optical.job', 'patient_id', groups='popspec_optical.group_operator')
    # No prescription fields, clinical related values, counts or chatter on a shared contact.


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    optical_job_ids = fields.One2many('optical.job', 'sale_order_id', groups='popspec_optical.group_operator')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def write(self, vals):
        material = {'product_id', 'product_uom_qty', 'product_uom_id', 'price_unit', 'discount', 'tax_ids'}
        jobs = self.env['optical.job'].sudo().search([('sale_line_id', 'in', self.ids), ('state', '!=', 'cancelled')]) if material & vals.keys() else self.env['optical.job']
        if jobs:
            jobs._lock()
            jobs._require_editable()
        result = super().write(vals)
        if jobs:
            jobs._invalidate_checks()
            jobs._audit('Native frame sale line changed', {'values': vals, 'sale_line_ids': self.ids})
        return result


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    optical_job_ids = fields.One2many('optical.job', 'purchase_order_id', groups='popspec_optical.group_operator')

    def button_confirm(self):
        # Restrict only orders explicitly linked to optical jobs. Native Purchase is otherwise unchanged.
        jobs = self.env['optical.job'].sudo().search([('purchase_order_id', 'in', self.ids), ('state', '!=', 'cancelled')])
        for job in jobs:
            if job.state != 'verified':
                raise UserError(_('Verify the linked optical job before confirming its laboratory purchase order.'))
            job._require_qc('pre_lab')
        return super().button_confirm()


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        jobs = self.env['optical.job'].sudo().search([
            ('state', 'not in', ['cancelled', 'dispensed']),
            '|', ('dispatch_picking_id', 'in', self.picking_id.ids),
                 ('sale_line_id', 'in', self.sale_line_id.ids),
        ])
        if jobs:
            jobs._lock()
        for job in jobs:
            dispatch = self.filtered(lambda m: m.picking_id == job.dispatch_picking_id)
            delivery = self.filtered(lambda m: m.sale_line_id == job.sale_line_id and m.location_dest_id.usage == 'customer')
            if dispatch:
                if job.state != 'verified':
                    raise UserError(_('The optical job must be verified before its lab dispatch is validated.'))
                job._require_qc('pre_lab')
                job._require_scan('dispatch')
                job._stock_evidence(job.dispatch_picking_id, 'dispatch', done=False)
            if delivery:
                if job.state != 'ready':
                    raise UserError(_('Incoming inspection and final fitting must be completed before delivery.'))
                job._require_qc('dispense')
                job._require_scan('collect')
                if delivery.picking_id != job.delivery_picking_id:
                    raise UserError(_('Link this native customer delivery to the optical job before validating it.'))
                job._stock_evidence(job.delivery_picking_id, 'delivery', done=False)
        result = super()._action_done(cancel_backorder=cancel_backorder)
        # Audit stock evidence without copying clinical data into Inventory chatter.
        for job in jobs:
            completed = result.filtered(lambda m: m.state == 'done' and (m.picking_id == job.dispatch_picking_id or m.sale_line_id == job.sale_line_id))
            if completed:
                job._audit('Native stock movement completed', {
                    'move_ids': completed.ids, 'transfer_ids': completed.picking_id.ids})
        return result


CLINICAL_MODELS = ('optical.prescription', 'optical.job.clinical', 'optical.quality', 'optical.lab.ticket')


class ClinicalAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.constrains('res_model', 'public', 'access_token')
    def _check_clinical_sharing(self):
        for attachment in self:
            if attachment.res_model in CLINICAL_MODELS and (attachment.public or attachment.access_token):
                raise ValidationError(_('Clinical attachments cannot be public or shared with access-token links.'))

    def write(self, vals):
        if set(vals) & {'res_model', 'res_id', 'datas', 'raw'}:
            if any(r.res_model in CLINICAL_MODELS for r in self):
                raise AccessError(_('Clinical source attachments are permanent. Add a new document to record a correction.'))
        return super().write(vals)

    def unlink(self):
        if any(r.res_model in CLINICAL_MODELS for r in self):
            raise AccessError(_('Clinical source attachments are permanent.'))
        return super().unlink()
