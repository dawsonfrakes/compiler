class Symbol(str):
    def __repr__(self) -> str: return self
class String(str): pass
class ComptimeInt(int): pass
Atom = Symbol | String | ComptimeInt
class List(list): pass
Exp = Atom | List

def parse_exp(s: list[str]) -> Exp | None:
    stack = []
    level = 0
    while True:
        while True:
            while len(s) > 0 and s[-1].isspace(): s.pop()
            if len(s) == 0: break
            if s[-1] == ';':
                while len(s) > 0 and s[-1] != '\n': s.pop()
                continue
            else:
                break
        if len(s) == 0: break
        c = s.pop()
        if c == '(':
            stack.append(List())
            level += 1
            continue
        if c == ')':
            level -= 1
            x = stack.pop()
            (stack[-1] if len(stack) > 0 else stack).append(x)
        elif c.isdigit():
            while len(s) > 0 and s[-1].isdigit(): c += s.pop()
            (stack[-1] if len(stack) > 0 else stack).append(ComptimeInt(c))
        elif c == '"':
            while len(s) > 0 and ((len(s) > 1 and s[-2] == '\\') or s[-1] != '"'): c += s.pop()
            assert len(s) > 0 and s[-1] == '"'
            c += s.pop()
            (stack[-1] if len(stack) > 0 else stack).append(String(c[1:-1]))
        elif c.isalpha or c in "+-*/_=":
            while len(s) > 0 and (s[-1].isalnum() or s[-1] in "+-*/_="): c += s.pop()
            (stack[-1] if len(stack) > 0 else stack).append(Symbol(c))
        if level == 0 and len(stack) == 1: break
    assert len(stack) <= 1
    return stack[0] if len(stack) != 0 else None

class Env(dict): pass
from dataclasses import dataclass
@dataclass
class Enum:
    names: List[Symbol]
    values: List[ComptimeInt]
@dataclass
class EnumField:
    container_exp: Exp
    name: String

def doeval(x: Exp, env: Env) -> Exp | None:
    if not isinstance(x, List):
        if isinstance(x, Symbol): return env[x]
        if isinstance(x, String | ComptimeInt): return x
        raise NotImplementedError(x)
    op, *args = x
    if op == Symbol("enum"):
        names, values = List(args[0::2]), List(args[1::2])
        assert all([isinstance(name, Symbol) for name in names])
        values = [doeval(value, env) for value in values]
        assert all([isinstance(value, ComptimeInt) for value in values])
        return Enum(names, values)
    elif op == Symbol("field"):
        container_exp, name = args
        container = doeval(container_exp, env)
        assert isinstance(container, Enum)
        name = doeval(name, env)
        assert isinstance(name, String)
        return EnumField(container_exp, name)
    raise NotImplementedError(op)

class Cify:
    def __init__(self) -> None:
        self.env = Env()

    def visit(self, x: Exp, env) -> None:
        if not isinstance(x, List):
            raise NotImplementedError(x)
        op, *args = x
        if op == Symbol("const"):
            name, value = args
            assert isinstance(name, Symbol)
            value = doeval(value, env)
            env[name] = value
            return None
        raise NotImplementedError(op)

    def finalize(self) -> str:
        result = ""
        result += """
/* BEGIN GENERATED SOURCE */
#define Noreturn void

"""
        result += "/* ENUMS */\n"
        for v in self.env:
            if isinstance(self.env[v], Enum):
                for name, value in zip(self.env[v].names, self.env[v].values):
                    result += f"#define {v}_{name} {value}\n"
            elif isinstance(self.env[v], EnumField):
                container = doeval(self.env[v].container_exp, self.env)
                names, values = container.names, container.values
                name = self.env[v].name
                assert name in names
                result += f"#define {v} {self.env[v].container_exp}_{name}"
            else: raise NotImplementedError(self.env[v])
            result += "\n"
        result += f"""/* DEFINES */
#if defined(__x86_64__) || defined(_M_AMD64)
#define CPU CPU_Target_amd64
#else
#define CPU CPU_Target_unknown
#endif

"""
        result += """/* END GENERATED SOURCE */"""
        return result

src = """
(const CPU_Target (enum
 unknown 0
 x64 1
 arm64 2))
(const CallingConvention (enum
 default 0
 c 1
 stdcall 2))
; (proc RawEntryPoint () WINAPI noreturn)
(const WINAPI (field CallingConvention "c"))
"""
src_rev = list(reversed(src))
cify = Cify()
while True:
    exp = parse_exp(src_rev)
    if exp is None: break
    print(exp)
    result = cify.visit(exp, cify.env)
    print(cify.env)
    if result is not None: print(result)
assert len(src_rev) == 0
print(cify.finalize())
