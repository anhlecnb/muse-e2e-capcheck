"""Red phase: tests for boq.parsing written BEFORE any implementation exists."""

import csv
import os
import tempfile
import unittest
from decimal import Decimal

from boq.models import (
    BoqRow,
    PriceRow,
    DataError,
    DUPLICATE_CODE,
    INVALID_NUMBER,
    INVALID_ROW,
    NEGATIVE_QUANTITY,
)
from boq.parsing import parse_boq_csv, parse_prices_csv


class CsvTestCase(unittest.TestCase):
    """Base class providing a helper to write temporary CSV files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def write_csv(self, name, content):
        """Write ``content`` to a temp CSV file and return its path."""
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return path


class ParseBoqCsvTest(CsvTestCase):
    def test_parse_boq_csv_valid(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "B1,Concrete C30,m3,12.5,Structure\n"
            "B2,Rebar,kg,100,Structure\n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 2)
        r = rows[0]
        self.assertIsInstance(r, BoqRow)
        self.assertEqual(r.line_number, 2)  # header is line 1
        self.assertEqual(r.code, "B1")
        self.assertEqual(r.description, "Concrete C30")
        self.assertEqual(r.unit, "m3")
        self.assertEqual(r.quantity, Decimal("12.5"))
        self.assertEqual(r.group, "Structure")

    def test_parse_boq_csv_invalid_quantity(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "B1,Concrete C30,m3,abc,Structure\n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(rows, [])
        self.assertEqual(len(errors), 1)
        e = errors[0]
        self.assertIsInstance(e, DataError)
        self.assertEqual(e.line_number, 2)
        self.assertEqual(e.code, INVALID_NUMBER)
        self.assertEqual(e.source, "boq")
        self.assertIn("abc", e.message)

    def test_parse_boq_csv_negative_quantity(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "B1,Concrete C30,m3,-2.5,Structure\n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(rows, [])
        self.assertEqual(len(errors), 1)
        e = errors[0]
        self.assertEqual(e.line_number, 2)
        self.assertEqual(e.code, NEGATIVE_QUANTITY)
        self.assertEqual(e.source, "boq")
        self.assertIn("B1", e.message)

    def test_parse_boq_csv_non_finite_quantity_rejected(self):
        # Decimal("NaN")/Decimal("Infinity") parse without raising, but they
        # are not meaningful quantities -> INVALID_NUMBER
        for bad in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=bad):
                path = self.write_csv(
                    "boq.csv",
                    "code,description,unit,quantity,group\n"
                    f"B1,Concrete C30,m3,{bad},Structure\n",
                )
                rows, errors = parse_boq_csv(path)
                self.assertEqual(rows, [])
                self.assertEqual(len(errors), 1)
                self.assertEqual(errors[0].code, INVALID_NUMBER)

    def test_parse_boq_csv_zero_quantity_is_valid(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "B1,Concrete C30,m3,0,Structure\n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].quantity, Decimal("0"))

    def test_parse_boq_csv_wrong_column_count(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "B1,Concrete C30,m3\n"  # too few columns
            "B2,Rebar,kg,100,Structure,EXTRA\n",  # too many columns
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(rows, [])
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0].code, INVALID_ROW)
        self.assertEqual(errors[0].line_number, 2)
        self.assertEqual(errors[0].source, "boq")
        self.assertEqual(errors[1].code, INVALID_ROW)
        self.assertEqual(errors[1].line_number, 3)

    def test_parse_boq_csv_missing_code(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            ",Concrete C30,m3,10,Structure\n"  # empty code
            "   ,Rebar,kg,5,Structure\n",  # whitespace-only code
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(rows, [])
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(e.code == INVALID_ROW for e in errors))
        self.assertEqual([e.line_number for e in errors], [2, 3])

    def test_parse_boq_csv_skips_blank_lines(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "\n"
            "B1,Concrete C30,m3,10,Structure\n"
            "   \n"
            ",,,\n"  # all fields empty -> also blank, skipped silently
            "B2,Rebar,kg,5,Structure\n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 2)
        # line numbers follow the physical file lines
        self.assertEqual(rows[0].line_number, 3)
        self.assertEqual(rows[0].code, "B1")
        self.assertEqual(rows[1].line_number, 6)
        self.assertEqual(rows[1].code, "B2")

    def test_parse_boq_csv_bad_header_raises(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity\n"  # missing group column
            "B1,Concrete C30,m3,10\n",
        )
        with self.assertRaises(ValueError):
            parse_boq_csv(path)

    def test_parse_boq_csv_header_wrong_order_raises(self):
        path = self.write_csv(
            "boq.csv",
            "description,code,unit,quantity,group\n"  # wrong order
            "Concrete C30,B1,m3,10,Structure\n",
        )
        with self.assertRaises(ValueError):
            parse_boq_csv(path)

    def test_parse_boq_csv_strips_whitespace_and_defaults_group(self):
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "  B1  ,  Concrete C30  ,  m3  ,  12.5  ,   \n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.code, "B1")
        self.assertEqual(r.description, "Concrete C30")
        self.assertEqual(r.unit, "m3")
        self.assertEqual(r.group, "UNGROUPED")  # empty group -> UNGROUPED

    def test_parse_boq_csv_duplicate_codes_are_not_parsing_errors(self):
        # duplicate code detection belongs to validation, not parsing
        path = self.write_csv(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "B1,Concrete C30,m3,10,Structure\n"
            "B1,Concrete C40,m3,20,Structure\n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 2)

    def test_parse_boq_csv_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            parse_boq_csv(os.path.join(self._tmp.name, "does-not-exist.csv"))


class ParsePricesCsvTest(CsvTestCase):
    def test_parse_prices_csv_valid(self):
        path = self.write_csv(
            "prices.csv",
            "code,material_unit_price,labor_unit_price,unit\n"
            "P1,100.50,20,m3\n"
            "P2,0,15.75,kg\n",
        )
        price_map, errors = parse_prices_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(set(price_map.keys()), {"P1", "P2"})
        p = price_map["P1"]
        self.assertIsInstance(p, PriceRow)
        self.assertEqual(p.line_number, 2)
        self.assertEqual(p.code, "P1")
        self.assertEqual(p.material_unit_price, Decimal("100.50"))
        self.assertEqual(p.labor_unit_price, Decimal("20"))
        self.assertEqual(p.unit, "m3")

    def test_parse_prices_csv_duplicate_keeps_first(self):
        path = self.write_csv(
            "prices.csv",
            "code,material_unit_price,labor_unit_price,unit\n"
            "P1,100,20,m3\n"
            "P1,999,888,m3\n",
        )
        price_map, errors = parse_prices_csv(path)
        self.assertEqual(price_map["P1"].material_unit_price, Decimal("100"))
        self.assertEqual(price_map["P1"].labor_unit_price, Decimal("20"))
        self.assertEqual(len(errors), 1)
        e = errors[0]
        self.assertEqual(e.code, DUPLICATE_CODE)
        self.assertEqual(e.source, "prices")
        self.assertEqual(e.line_number, 3)
        self.assertIn("P1", e.message)

    def test_parse_prices_csv_negative_price(self):
        path = self.write_csv(
            "prices.csv",
            "code,material_unit_price,labor_unit_price,unit\n"
            "P1,-5,20,m3\n",
        )
        price_map, errors = parse_prices_csv(path)
        self.assertEqual(price_map, {})
        self.assertEqual(len(errors), 1)
        e = errors[0]
        self.assertEqual(e.code, INVALID_NUMBER)
        self.assertEqual(e.source, "prices")
        self.assertIn("negative", e.message.lower())

    def test_parse_prices_csv_invalid_number(self):
        path = self.write_csv(
            "prices.csv",
            "code,material_unit_price,labor_unit_price,unit\n"
            "P1,xx,20,m3\n",
        )
        price_map, errors = parse_prices_csv(path)
        self.assertEqual(price_map, {})
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, INVALID_NUMBER)
        self.assertEqual(errors[0].source, "prices")

    def test_parse_prices_csv_bad_header_raises(self):
        path = self.write_csv(
            "prices.csv",
            "code,material_unit_price,labor_unit_price\n"  # missing unit
            "P1,100,20\n",
        )
        with self.assertRaises(ValueError):
            parse_prices_csv(path)


if __name__ == "__main__":
    unittest.main()
