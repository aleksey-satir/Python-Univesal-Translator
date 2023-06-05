from inspect import getsource
from .type_conversion import type_conversion
from .js import JS
from .lua import Lua
from .py import Py


langs = [Py(), JS(), Lua()]

def check_exprs(exprs):
    expected_results = list(map(eval, exprs))
    for lang in langs:
        for i, e in enumerate(exprs):
            checked_expr = lang.gen_expr(e)
            fact_result = type_conversion(lang.eval(checked_expr))
            lang.clear()
            assert expected_results[i] == fact_result

def check_func(func):
    expected_results = func()
    src = getsource(func)
    for lang in langs:
        target_src = lang.gen_func(src)
        lang.load_func(target_src)
        fact_result = type_conversion(lang.call_func(func.__name__))
        lang.clear()
        assert expected_results == fact_result
