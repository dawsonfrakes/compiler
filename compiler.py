from dataclasses import dataclass

class Symbol(str): pass
class String(str): pass
class EnumLiteral(str): pass
class ComptimeInt(int): pass
class List(list): pass
@dataclass
class Type: pass
@dataclass
class Procedure(Type):
    parameter_names: List[Symbol]
    parameter_types: List[Type]
    callconv: EnumLiteral
    return_type: Type
@dataclass
class CUint(Type): pass
@dataclass
class Noreturn(Type): pass
Atom = Symbol | String | EnumLiteral | ComptimeInt | Type
Exp = Atom | List

class Env(dict): pass

def read(s: list[str]) -> Exp | None:
    stack = []
    level = 0
    while True:
        while True:
            while len(s) > 0 and s[-1].isspace(): s.pop()
            if len(s) == 0 or s[-1] != ';': break
            while len(s) > 0 and s[-1] != '\n': s.pop()
        if len(s) == 0: break
        c = s.pop()
        if c == '(':
            stack.append(List())
            level += 1
            continue
        elif c == ')':
            assert level > 0, "unmatched )"
            level -= 1
            x = stack.pop()
            (stack[-1] if len(stack) != 0 else stack).append(x)
        elif c.isalpha() or c in "+-*/_=":
            while len(s) > 0 and (s[-1].isalnum() or s[-1] in "+-*/_=."): c += s.pop()
            (stack[-1] if len(stack) != 0 else stack).append(Symbol(c))
        elif c.isdigit():
            while len(s) > 0 and s[-1].isdigit(): c += s.pop()
            (stack[-1] if len(stack) != 0 else stack).append(ComptimeInt(c))
        elif c == '"':
            while len(s) > 0 and ((len(s) > 1 and s[-2] == '\\') or s[-1] != '"'): c += s.pop()
            assert len(s) > 0 and s[-1] == '"'
            c += s.pop()
            (stack[-1] if len(stack) != 0 else stack).append(String(c))
        else: raise SyntaxError(c)
        if level == 0 and len(stack) == 1: break
    assert len(stack) <= 1
    return stack[0] if len(stack) > 0 else None

def doeval(x: Exp, env: Env) -> Exp | None:
    if not isinstance(x, List):
        if isinstance(x, Symbol): return env[x]
        elif isinstance(x, String | ComptimeInt | EnumLiteral): return x
        else: raise NotImplementedError(x)
    op, *args = x
    if op == Symbol("if"):
        test, conseq, alt = args
        return doeval(conseq, env) if doeval(test, env) else doeval(alt, env)
    raise NotImplementedError(op)

builtins = {
    Symbol("noreturn"): Noreturn(),
    Symbol("c-uint"): CUint(),
}

global_env = builtins.copy()
while True:
    i = input("> ")
    ri = list(reversed(i))
    while True:
        exp = read(ri)
        if exp is None: break
        print('=>', exp)
        result = doeval(exp, global_env)
        if result is not None: print('==>', result)
