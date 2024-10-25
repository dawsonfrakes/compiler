class List(list):
    def __repr__(self) -> str: return '(' + " ".join([repr(member) for member in self]) + ')'
class Symbol(str):
    def __repr__(self) -> str: return self
class Number(float): pass
class EnumLiteral(str):
    def __repr__(self) -> str: return self
Atom = Symbol | EnumLiteral | Number
Exp = List | Atom

def read(s: list) -> Exp | None:
    stack = []
    level = 0
    while True:
        while len(s) != 0 and s[-1].isspace(): s.pop()
        if len(s) == 0: break
        c = s.pop()
        if c == '(':
            stack.append(List())
            level += 1
            continue
        if c == ')':
            level -= 1
            x = stack.pop()
            (stack[-1] if len(stack) != 0 else stack).append(x)
        elif c == '.':
            while len(s) > 0 and (s[-1].isalnum() or s[-1] in "+-*/_="): c += s.pop()
            (stack[-1] if len(stack) != 0 else stack).append(EnumLiteral(c))
        elif c.isdigit():
            while len(s) > 0 and (s[-1].isdigit() or s[-1] in "."): c += s.pop()
            (stack[-1] if len(stack) != 0 else stack).append(Number(c))
        elif c.isalpha() or c in "+-*/_=":
            while len(s) > 0 and (s[-1].isalnum() or s[-1] in "+-*/_="): c += s.pop()
            (stack[-1] if len(stack) != 0 else stack).append(Symbol(c))
        else: raise NotImplementedError(c)
        if level == 0 and len(stack) == 1: break
    assert len(stack) <= 1
    return stack[0] if len(stack) != 0 else None

from dataclasses import dataclass

@dataclass
class Enum:
    names: list[Symbol]
    values: list[Exp]

@dataclass
class EnumField:
    type_: Exp
    field: Symbol

@dataclass
class Proto:
    params: list[Exp]
    callconv: Exp
    ret_type: Exp

@dataclass
class Integer:
    bits: int
    signed: bool

@dataclass
class Noreturn:
    pass

@dataclass
class CUint:
    pass

env = {"c-uint": CUint(), "noreturn": Noreturn(), "CPU_Endianness": Enum([Symbol("x86")], [0.0]), "CPU": EnumField(Symbol("CPU_Endianness"), Symbol("x86"))}
def doeval(x: Exp) -> Exp | bool | None:
    if not isinstance(x, List):
        if isinstance(x, Symbol):
            result = env[x]
            return result
        return x
    op, *args = x
    if op == Symbol("const"):
        name, value = args
        assert isinstance(name, Symbol)
        assert name not in env
        value = doeval(value)
        env[name] = value
        return None
    elif op == Symbol("proto"):
        params, callconv, ret_type = args
        params = [doeval(param) for param in params]
        callconv = doeval(callconv)
        ret_type = doeval(ret_type)
        return Proto(params, callconv, ret_type)
    elif op == Symbol("if"):
        test, conseq, alt = args
        return doeval(conseq) if doeval(test) else doeval(alt)
    elif op == Symbol("enum"):
        names, values = args[::2], args[1::2]
        assert all([isinstance(name, Symbol) for name in names])
        values = [doeval(value) for value in values]
        return Enum(names, values)
    elif op == Symbol("=="):
        lhs, rhs = args
        lhs = doeval(lhs)
        rhs = doeval(rhs)
        return lhs == rhs
    raise NotImplementedError(op)

def cify_callconv(x: EnumLiteral) -> str:
    if x == EnumLiteral(".c"):
        return "__cdecl"
    if x == EnumLiteral(".stdcall"):
        return "__stdcall"

def cify_function(type_: Exp, name: str) -> str:
    type_ = doeval(type_)
    arg_list = ", ".join([cify(param) for param in type_.params]) if len(type_.params) > 0 else "void"
    return cify(type_.ret_type) + " " + cify_callconv(type_.callconv) + " " + repr(name) + "(" + arg_list + ")"

cify_env = {}
def cify(x: Exp) -> str:
    if not isinstance(x, List):
        if isinstance(x, Noreturn): return "Noreturn"
        if isinstance(x, CUint): return "unsigned int"
        if x in cify_env: return cify_env[x]
        if isinstance(x, Number): return x
        raise NotImplementedError(x)
    op, *args = x
    if op == Symbol("const"):
        name, value = args
        assert isinstance(name, Symbol)
        # value = doeval(value)
        doeval(x)
        return None
        # return f"// #define {name} {value}"
    elif op == Symbol("extern"):
        name, type_ = args
        assert isinstance(name, Symbol)
        cify_env[name] = repr(name)
        return cify_function(type_, name) + ";\n"
    elif op == Symbol("enum"):
        names, values = args[::2], args[1::2]
        return f"enum {{ {names} {values} }};"
    elif op == Symbol("proto"):
        name, type_ = args
        assert isinstance(name, Symbol)
        return cify_function(type_, name)
    elif op == Symbol("proc"):
        name, params, callconv, ret_type, *body = args
        assert isinstance(name, Symbol)
        fn = cify_function(Proto([doeval(param) for param in params], doeval(callconv), doeval(ret_type)), name)
        body = [cify(statement) for statement in body]
        return f"{fn} {{{"\n\t" + ";\n\t".join(body) + ";\n"}}}"
    elif op == Symbol("if"):
        test, conseq, alt = args
        test = cify(test)
        conseq = cify(conseq)
        alt = cify(alt)
        return f"{test} ? {conseq} : {alt}"
    elif op == Symbol("=="):
        lhs, rhs = args
        lhs = cify(lhs)
        rhs = cify(rhs)
        return f"{lhs} == {rhs}"
    else:
        proc, *pargs = x
        proc = cify(proc)
        pargs = [cify(arg) for arg in pargs]
        return f"{proc}({", ".join([repr(arg) for arg in pargs])})"
    raise NotImplementedError(op)

src = """
(const CallingConvention (enum
    default 0
    c 1
    stdcall 2))
(const WINAPI (if (== CPU .x86) (field CallingConvention .stdcall) .c))
(extern ExitProcess (proto (c-uint) WINAPI noreturn))
(proc RawEntryPoint () WINAPI noreturn
 (ExitProcess 0))
"""

cify_preamble = """
#define Noreturn void
"""
print(cify_preamble)

src_rev = list(reversed(src))
while True:
    exp = read(src_rev)
    if exp is None: break
    # print(exp)
    result = cify(exp)
    if result is not None: print(result)
