import unittest
from parsing.api import new_parser
from common.logwriter import LogWriter
from parsing.core_parser_ast import set_DEBUGINFO, DEBUGINFO
from textwrap import dedent
from parsing.parse_source import parse_source
from parsing.dump_pmodel import dump_pmodel


class TestParseTypeAnnotations(unittest.TestCase):
    
    def test_type_annotations_in_method_args(self):
        """
        Detect type annotations in method arguments
        https://github.com/abulka/pynsource/issues/75
        """
        source_code = dedent(
            """
            # Ironically, declaring the Restaurant class will trigger Pynsource to treat
            # self.restaurant as a implicit reference to the Restaurant class - without needing type annotations
            # simply due to the convention that it is the same name with the first letter in uppercase.
            # But let's not rely on this here, so comment out this 'trick'
            # 
            # class Restaurant:
            #     pass

            class Customer:
                def __init__(self, restaurant: Restaurant):
                    self.restaurant = restaurant
        """
        )
        pmodel, debuginfo = parse_source(source_code, options={"mode": 3}, html_debug_root_name="test_type_annotations_in_method_args")
        self.assertEqual(pmodel.errors, "")
        classNames = [classname for classname, classentry in pmodel.classlist.items()]
        # print(classNames)
        # print(dump_pmodel(pmodel))  # very pretty table dump of the parse model
        self.assertIn("Customer", classNames)
        classentry = pmodel.classlist["Customer"]
        # print(classentry)
        self.assertEqual(len(classentry.defs), 1)
        self.assertIn("__init__", classentry.defs)

        # ensure the type annotation dependencies have been detected
        self.assertEqual(len(classentry.classdependencytuples), 1)
        self.assertEqual(classentry.classdependencytuples[0], ('restaurant', 'Restaurant'))

        # make sure the attributes are being created as well
        attrnames = [attr_tuple.attrname for attr_tuple in classentry.attrs]
        assert "restaurant" in attrnames

    def test_type_annotation_outside_class(self):
        # Outside of a class Pynsource can't make a class to class dependency but should parse ok.
        # (but GitUML can make a module dependency since it supports module dependencies and Pynsource currently does not)
        source_code = dedent(
            """

            def func(varin: dict):
                pass
        """
        )
        pmodel, debuginfo = parse_source(source_code, options={"mode": 3}, html_debug_root_name="test_type_annotation_outside_class")
        self.assertIn("had no classes", pmodel.errors)  # not really an error

    def test_type_annotation_in_attr_assignment(self):
        # Ensure attr assignment in class, with type annotation, works
        source_code = dedent(
            """
            class Customer:
                def __init__(self, restaurant):
                    self.restaurant: Restaurant = restaurant
        """
        )
        pmodel, debuginfo = parse_source(source_code, options={"mode": 3}, html_debug_root_name="test_type_annotation_in_attr_assignment")
        self.assertEqual(pmodel.errors, "")
        classNames = [classname for classname, classentry in pmodel.classlist.items()]
        # print(classNames)
        # print(dump_pmodel(pmodel))  # very pretty table dump of the parse model
        self.assertIn("Customer", classNames)
        classentry = pmodel.classlist["Customer"]
        # print(classentry)
        self.assertEqual(len(classentry.defs), 1)
        self.assertIn("__init__", classentry.defs)

        # ensure the type annotation dependencies have been detected
        self.assertEqual(len(classentry.classdependencytuples), 1)
        self.assertEqual(classentry.classdependencytuples[0], ('restaurant', 'Restaurant'))

        # make sure the attributes are being created as well
        attrnames = [attr_tuple.attrname for attr_tuple in classentry.attrs]
        assert "restaurant" in attrnames

    def test_type_annotation_attr_tricky_rhs(self):
        # Handle type annotation parsing where no rhs. expression given, and where rhs. is None
        source_code = dedent(
            """
            class Customer:
                def __init__(self, restaurant):
                    self.restaurant: Restaurant = restaurant
                    self.fred: Fred
                    self.xx: Mary = None
        """
        )
        pmodel, debuginfo = parse_source(source_code, options={"mode": 3}, html_debug_root_name="test_type_annotation_attr_tricky_rhs")
        self.assertEqual(pmodel.errors, "")
        classNames = [classname for classname, classentry in pmodel.classlist.items()]
        # print(classNames)
        # print(dump_pmodel(pmodel))  # very pretty table dump of the parse model
        self.assertIn("Customer", classNames)
        classentry = pmodel.classlist["Customer"]
        # print(classentry)
        self.assertEqual(len(classentry.defs), 1)
        self.assertIn("__init__", classentry.defs)

        # make sure the attributes are being created
        attrnames = [attr_tuple.attrname for attr_tuple in classentry.attrs]
        assert "restaurant" in attrnames
        assert "fred" in attrnames
        assert "xx" in attrnames
        
        # ensure the type annotation dependencies have been detected
        self.assertEqual(len(classentry.classdependencytuples), 3)
        self.assertIn(('restaurant', 'Restaurant'), classentry.classdependencytuples)
        self.assertIn(('fred', 'Fred'), classentry.classdependencytuples)
        self.assertIn(('xx', 'Mary'), classentry.classdependencytuples)


class TestNoAssignmentShouldStillCreateAttrs(unittest.TestCase):

    def _ensure_attrs_created(self, pmodel):
        # make sure the attributes are being created
        self.assertEqual(pmodel.errors, "")
        classentry = pmodel.classlist["Customer"]
        attrnames = [attr_tuple.attrname for attr_tuple in classentry.attrs]
        assert "restaurant" in attrnames
        assert "fred" in attrnames
        assert "xx" in attrnames

    def test_assignment_rhs_missing(self):
        """
            When rhs entirely missing, the AST contains an 'Expr' node not an 'Assign' node.

            AST:
            body=[
                Expr(
                    lineno=4,
                    col_offset=8,
                    value=Attribute(
                        lineno=4,
                        col_offset=8,
                        value=Name(lineno=4, col_offset=8, id='self', ctx=Load()),
                        attr='restaurant',
                        ctx=Load(),
                    ),
                ),        
        """
        source_code = dedent(
            """
            class Customer:
                def __init__(self, restaurant):
                    self.restaurant
                    self.fred
                    self.xx
        """
        )
        pmodel, debuginfo = parse_source(source_code, options={"mode": 3}, html_debug_root_name="test_assignment_rhs_missing")
        self._ensure_attrs_created(pmodel)

    def test_assignment_rhs_is_None(self):
        """
            Traditional 'Assign' node, attribute create via old rhs/lhs/flush logic.

            AST:
            body=[
                Assign(
                    lineno=4,
                    col_offset=8,
                    targets=[
                        Attribute(
                            lineno=4,
                            col_offset=8,
                            value=Name(lineno=4, col_offset=8, id='self', ctx=Load()),
                            attr='restaurant',
                            ctx=Store(),
                        ),
                    ],
                    value=NameConstant(lineno=4, col_offset=26, value=None),
                    type_comment=None,
                ),        
        """
        source_code = dedent(
            """
            class Customer:
                def __init__(self, restaurant):
                    self.restaurant = None
                    self.fred = None
                    self.xx = None
        """
        )
        pmodel, debuginfo = parse_source(source_code, options={"mode": 3}, html_debug_root_name="test_assignment_rhs_is_None")
        self._ensure_attrs_created(pmodel)

    def test_assignment_has_type_annotation(self):
        """
            'AnnAssign' node instead of traditional 'Assign' - copy the Assign logic but adjust
            since can't have multiple lhs when using type annotations.

            AST:
            body=[
                AnnAssign(
                    lineno=4,
                    col_offset=8,
                    target=Attribute(
                        lineno=4,
                        col_offset=8,
                        value=Name(lineno=4, col_offset=8, id='self', ctx=Load()),
                        attr='restaurant',
                        ctx=Store(),
                    ),
                    annotation=Name(lineno=4, col_offset=25, id='Restaurant', ctx=Load()),
                    value=Name(lineno=4, col_offset=38, id='restaurant', ctx=Load()),
                    simple=0,
                ),
        """
        source_code = dedent(
            """
            class Customer:
                def __init__(self, restaurant):
                    self.restaurant: Restaurant = restaurant
                    self.fred: Fred
                    self.xx: Mary = None
        """
        )
        pmodel, debuginfo = parse_source(source_code, options={"mode": 3}, html_debug_root_name="test_assignment_has_type_annotation")
        self._ensure_attrs_created(pmodel)
