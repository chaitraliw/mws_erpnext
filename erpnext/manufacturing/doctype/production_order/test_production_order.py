# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


from __future__ import unicode_literals
import unittest
import frappe
from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import set_perpetual_inventory
from erpnext.manufacturing.doctype.production_order.production_order import make_stock_entry
from erpnext.stock.doctype.stock_entry import test_stock_entry

class TestProductionOrder(unittest.TestCase):
	def test_planned_qty(self):
		set_perpetual_inventory(0)

		planned0 = frappe.db.get_value("Bin", {"item_code": "_Test FG Item", "warehouse": "_Test Warehouse 1 - _TC"}, "planned_qty") or 0

		pro_doc = frappe.copy_doc(test_records[0])
		pro_doc.insert()
		pro_doc.submit()

		# add raw materials to stores
		test_stock_entry.make_stock_entry(item_code="_Test Item",
			target="Stores - _TC", qty=100, incoming_rate=100)
		test_stock_entry.make_stock_entry(item_code="_Test Item Home Desktop 100",
			target="Stores - _TC", qty=100, incoming_rate=100)

		# from stores to wip
		s = frappe.get_doc(make_stock_entry(pro_doc.name, "Material Transfer", 4))
		for d in s.get("mtn_details"):
			d.s_warehouse = "Stores - _TC"
		s.insert()
		s.submit()

		# from wip to fg
		s = frappe.get_doc(make_stock_entry(pro_doc.name, "Manufacture", 4))
		s.insert()
		s.submit()

		self.assertEqual(frappe.db.get_value("Production Order", pro_doc.name,
			"produced_qty"), 4)
		planned1 = frappe.db.get_value("Bin", {"item_code": "_Test FG Item", "warehouse": "_Test Warehouse 1 - _TC"}, "planned_qty")
		self.assertEqual(planned1 - planned0, 6)

		return pro_doc

	def test_over_production(self):
		from erpnext.manufacturing.doctype.production_order.production_order import StockOverProductionError
		pro_doc = self.test_planned_qty()

		test_stock_entry.make_stock_entry(item_code="_Test Item",
			target="_Test Warehouse - _TC", qty=100, incoming_rate=100)
		test_stock_entry.make_stock_entry(item_code="_Test Item Home Desktop 100",
			target="_Test Warehouse - _TC", qty=100, incoming_rate=100)

		s = frappe.get_doc(make_stock_entry(pro_doc.name, "Manufacture", 7))
		s.insert()

		self.assertRaises(StockOverProductionError, s.submit)

	def test_make_time_log(self):
		prod_order = frappe.get_doc({
			"doctype":"Production Order",
			"production_item": "_Test FG Item 2",
			"bom_no": "BOM/_Test FG Item 2/002",
			"qty": 1
		})


		prod_order.get_production_order_operations()
		prod_order.production_order_operations[0].update({
			"planned_start_time": "2014-11-25 00:00:00",
			"planned_end_time": "2014-11-25 10:00:00" 
		})

		prod_order.insert()
		
		d = prod_order.production_order_operations[0]

		from erpnext.manufacturing.doctype.production_order.production_order import make_time_log
		from frappe.utils import cstr
		from frappe.utils import time_diff_in_hours
		
		time_log = make_time_log( prod_order.name, cstr(d.idx) + ". " + d.operation, \
			d.planned_start_time, d.planned_end_time, prod_order.qty - d.qty_completed)

		self.assertEqual(prod_order.name, time_log.production_order)
		self.assertEqual((prod_order.qty - d.qty_completed), time_log.qty)
		self.assertEqual(time_diff_in_hours(d.planned_end_time, d.planned_start_time),time_log.hours)

		time_log.save()
		time_log.submit()

		prod_order.load_from_db()
		self.assertEqual(prod_order.production_order_operations[0].status, "Completed")
		self.assertEqual(prod_order.production_order_operations[0].qty_completed, prod_order.qty)

		self.assertEqual(prod_order.production_order_operations[0].actual_start_time, time_log.from_time)
		self.assertEqual(prod_order.production_order_operations[0].actual_end_time, time_log.to_time)

		time_log.cancel()

		prod_order.load_from_db()
		self.assertEqual(prod_order.production_order_operations[0].status,"Pending")
		self.assertEqual(prod_order.production_order_operations[0].qty_completed,0)

		time_log2 = frappe.copy_doc(time_log)
		time_log2.update({
			"qty": 10,
			"from_time": "2014-11-26 00:00:00",
			"to_time": "2014-11-26 00:00:00",
			"docstatus": 0
		})
		self.assertRaises(frappe.ValidationError, time_log2.save)
		
test_records = frappe.get_test_records('Production Order')
