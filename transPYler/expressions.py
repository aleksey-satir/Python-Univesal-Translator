import ast
from _ast import *
import re
import math
import copy
from . import types
from .types import to_any, to_string, type_translation
from .utils import getvar
from .core import visitor, op_to_str
from .side_effects import side_effects
from itertools import product


@visitor
def un_op(self, tree: UnaryOp):
    """Unary operations(not...)"""
    el = self.visit(tree.operand)
    return self.node(
        tmp='un_op',
        type=el.type,
        parts={
            'op': self.tmpls['operators'][op_to_str(tree.op)],
            'el': el
        }
    )

@visitor
def bin_op(self, tree: BinOp):
    """Math operation(+, -, *, /...)"""
    return _bin_op(
        self,
        self.visit(tree.left),
        self.visit(tree.right),
        op_to_str(tree.op)
    )

@visitor
def bool_op(self, tree: BoolOp):
    """Boolean logic operation(or, and)"""
    els = list(map(self.visit, tree.values))
    op = op_to_str(tree.op)
    expr = _bin_op(self, els[0], els[1], op)
    for el in els[2:]:
        expr = _bin_op(self, expr, el, op)
    return expr

@visitor
def compare(self, tree: Compare):
    """Compare operation(==, !=, >, <, >=, <=...)"""
    f_el = self.visit(tree.left)
    els = list(map(self.visit, tree.comparators))
    ops = list(map(op_to_str, tree.ops))
    expr = _bin_op(self, f_el, els[0], ops[0])
    for l, r, op in zip(els[:-1], els[1:], ops[1:]):
        expr = _bin_op(self, expr, _bin_op(self, l, e, op), 'and')
    return expr

def _bin_op(self, left, right, op):
    lt = left.type
    rt = right.type
    left_types = [to_string(lt)]
    right_types = [to_string(rt)]
    while lt != 'any':
        lt = to_any(lt)
        left_types.append(to_string(lt))
    while rt != 'any':
        rt = to_any(rt)
        right_types.append(to_string(rt))
    for l, r in product(left_types, right_types):
        overload = self.tmpls.get(f'{l}.{op}.{r}')
        if overload:
            tmp = overload.get('code', 'bin_op')
            _type = eval(overload.get(
                'type',
                'None'
            )) or 'None'
            if isinstance(_type, type):
                _type = str(_type)[8:-2]
            break
    else:
        tmp = 'bin_op'
        _type = 'None'
    return self.node(
        parts={
            'left': left,
            'right': right,
            'op': self.tmpls['operators'][op]
        },
        tmp=tmp,
        type=_type
    )

def merge_args(macro, args):
    if 'args' not in macro:
        return {}
    return dict(list(zip(macro['args'], args)))

@visitor
def attribute(self, tree: Attribute, args=None):
    obj = self.visit(tree.value)
    _type = 'None'
    attr = tree.attr
    macro = ''
    parts = {'obj': obj, 'attr': attr, 'args': args}
    if isinstance(obj.type, types.Module):
        macro = self.tmpls[obj.type.name].get(attr)
    if not macro:
        obj_type = obj.type
        macro = self.tmpls.get(f'{to_string(obj_type)}.{attr}')
        while obj_type != 'any' and not macro:
            obj_type = to_any(obj_type)
            macro = self.tmpls.get(f'{to_string(obj_type)}.{attr}')
    if macro:
        _type = type_translation(macro.get('type', _type))
        parts['attr'] = macro.get('alt_name', attr)
        tmp = macro.get('code', 'callmethod')
        parts.update(merge_args(macro, args))
        exec(
            macro.get('side_effect', ''),
            side_effects | parts
        )
    else:
        tmp = 'callmethod' if args else 'attr'
    return self.node(
        type=_type, 
        tmp=tmp,
        parts=parts
    )

@visitor
def function_call(self, tree: Call):
    args = [self.visit(a) for a in tree.args]
    if isinstance(tree.func, Attribute):
        return self.attribute(tree.func, args=args)
    func = self.visit(tree.func)
    named_args = {}
    ret_type = 'None'
    parts = {'func': func, 'args': args}
    if isinstance(tree.func, Name) and tree.func.id in self.tmpls:
        macro = self.tmpls.get(tree.func.id)
        parts.update(merge_args(macro, args))
        ret_type = macro.get('rettype', ret_type)
        tmp = macro.get('code', 'callfunc')
        exec(
            macro.get('side_effect', ''),
            side_effects | parts
        )
    else:
        tmp = 'callfunc'
    return self.node(
        type=ret_type,
        parts=parts | named_args,
        tmp=tmp
    )

@visitor
def _list(self, tree: List):
    elements = list(map(self.visit, tree.elts))
    if len(elements):
        el_type = elements[0].type
    else:
        el_type = 'generic'
    return self.node(
        tmp='List',
        type=types.List(el_type),
        parts={'ls': elements}
    )

@visitor
def _dict(self, tree: Dict):
    keys = list(map(self.visit, tree.keys))
    values = list(map(self.visit, tree.values))
    if len(keys):
        el_type = values[0].type
        key_type = keys[0].type
    else:
        el_type = 'generic'
        key_type = 'generic'
    ren_key_type = self.tmpls.get('types').get(key_type, key_type)
    ren_el_type = self.tmpls.get('types').get(el_type, el_type)
    key_val = [{'key': x[0], 'val': x[1]} for x in zip(keys, values)]
    return {
        'type': {
            'base_type': 'dict',
            'key_type': key_type,
            'el_type': el_type 
        },
        'val': tmp.render(
            key_val=key_val,
            el_type=ren_el_type,
            key_type=ren_key_type
        )
    }

@visitor
def slice(self, tree: Subscript):
    obj = self.visit(tree.value)
    sl = tree.slice
    if type(sl) != Slice:
        return self.node(
            type=getattr(obj, 'el_type', 'None'),
            tmp='index',
            parts={'obj': obj, 'key': self.visit(sl)}
        )
    return self.node(
        tmp = 'slice',
        type = obj.type,
        parts = {
            'obj': obj,
            'low': self.visit(
                sl.lower or ast.Consrant(value=0)
            ),
            'up': self.visit(
                sl.upper or ast.Call(
                    func=ast.Name(id='len', ctx=Load),
                    args=[tree.value]
            )),
            'step': self.visit(
                sl.step or ast.Constant(value=1)
            )
        }
    )

@visitor
def name(self, tree: Name):
    name = tree.id
    _type = 'None'
    ctx = {
        Store: 'store',
        Load: 'load'
    }.get(type(tree.ctx))
    var_info = getvar(self, name)
    if var_info:
        _type = var_info['type'][-1]
        if isinstance(tree.ctx, Store):
            self.variables[var_info['own']]['immut'] = False
    elif isinstance(tree.ctx, Load) and (name in self.tmpls):
        macr = self.tmpls[name]
        _type = macr.get('type', _type)
        if _type == 'module':
            _type = types.Module(name)
        name = macr.get('alt_name', name)
    return self.node(
        type=_type,
        tmp='name',
        parts={
            'name': name,
            'own': var_info.get('own')
        }
    )

@visitor
def const(self, tree: Constant):
    _val = tree.value
    _type = str(type(_val))[8:-2]
    parts={'val': _val}
    if isinstance(_val, float):
        parts |= {'parts': math.modf(_val)}        
    return self.node(
        type=_type,
        tmp=_type.capitalize(),
        parts=parts
    )

@visitor
def none(self, tree: type(None)):
    return self.node(
        tmp='None',
        type='None'
    )
