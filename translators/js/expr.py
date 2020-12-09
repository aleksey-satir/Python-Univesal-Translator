import _ast


def bin_op(left, right, op):
    return left+op+right

def name(name):
    return name

def const(val):
    return val

def compare(els, ops):
    return els[0]+"".join([ops[els[1:].index(i)]+i for i in els[1:]])

def bool_op():
    pass

def call(name, args):
    return f"{name}({args})"

def attr(obj, attr_name):
    return f"{obj}.{attr_name}"

def arg(arg):
    return arg

def args(args):
    return ", ".join(args)